#!/usr/bin/env python3
"""Label every unique RecipeNLG ingredient string with TypeSafe Jev, in batches. This is the only script that calls the API.

Resumable: each batch's raw Jev probabilities are cached in labeled/ and skipped on re-run.
Batches already hand-labeled in labeled_manual/ are skipped. Turning probabilities into flags and
CSVs is classify_ingredients.py's job.

Usage (from this folder):
  pip install typesafe-sdk
  put TYPESAFE_API_KEY=... in ../.env (or export it)
  python label_ingredients.py --limit 2     # smoke test: first 2 batches only
  python label_ingredients.py               # all batches (resumes if interrupted)
  python label_ingredients.py --dry-run     # show batch count, no API calls

Output:
  labeled/batch_NNNNN.json      cached per-batch raw Jev probabilities
"""
import argparse
import csv
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "unique_values.csv"
CACHE = HERE / "labeled"

MANUAL = HERE / "labeled_manual"  # hand-labeled batches; same 28-column schema, never re-sent to the API

MODEL = "jev-latest"  # pin e.g. "jev-1.14.0" once thresholds below are tuned
BATCH = 200
WORKERS = 16  # batches in flight; each batch is BATCH sequential Jev calls

DEFINITE = [
    "tree_nut", "peanut", "dairy", "gluten", "egg", "soy", "fish",
    "shellfish", "sesame", "meat", "pork", "beef",
]
FLAGS = DEFINITE + ["protein_source", "unclear"]
MAYBE = ["maybe_" + f for f in DEFINITE]
ALL_FLAGS = FLAGS + MAYBE  # 26 values per row, in CSV column order
HEADER = ["ingredient"] + ALL_FLAGS + ["note"]  # 28 columns

QUESTIONS = {
    "tree_nut": "Contains or is derived from tree nuts (almond, walnut, cashew, pecan, pistachio, hazelnut, macadamia, pine nut, brazil nut, chestnut, praline, marzipan, nut flours/butters/oils, generic 'nuts'). Coconut, nutmeg, mace and water chestnut are NOT tree nuts.",
    "peanut": "Is peanuts or peanut-derived (peanut butter, peanut oil).",
    "dairy": "Is milk or milk-derived (butter, cheese, cream, yogurt, whey, ghee, casein, buttermilk, custard). Plant milks and non-dairy 'butters' (coconut milk, almond milk, cocoa butter, peanut butter) are NOT dairy.",
    "gluten": "Contains wheat, barley, rye or derivatives (flour, bread, pasta, soy sauce, couscous, beer).",
    "egg": "Is eggs or egg-derived.",
    "soy": "Is soy or soy-derived (tofu, tempeh, soy sauce, edamame, miso, soy milk).",
    "fish": "Is fish or fish-derived (anchovy, fish sauce, salmon, tuna).",
    "shellfish": "Is shellfish (shrimp, crab, lobster, clams, mussels, oysters, scallops, squid).",
    "sesame": "Is sesame or sesame-derived (sesame seeds, tahini, sesame oil).",
    "meat": "Is mammal or poultry flesh, including bacon, ham and sausage. Fish and shellfish are NOT meat.",
    "pork": "Is pork-derived (pork, bacon, ham, pork sausage, lard).",
    "beef": "Is beef-derived (beef, steak, ground beef, beef broth).",
    "protein_source": "Is a main protein source (meat, poultry, fish, shellfish, eggs, tofu, tempeh, legumes, protein powder, Greek yogurt, cottage cheese).",
    "unclear": "Is not a recognizable food ingredient (garbled text, a bare unit, a non-food phrase like 'happiness').",
}
FLAG_PREFIX = "Recipe ingredient. Answer for this ingredient by its meaning, interpreting typos as the intended ingredient. "


def load_ingredients():
    """Every row of unique_values.csv after the header, including blanks (never skipped)."""
    with SRC.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        next(reader)
        return [row[0] if row else "" for row in reader]


def batches(items):
    for start in range(0, len(items), BATCH):
        yield start // BATCH, items[start:start + BATCH]


def blank_probs():
    """A blank ingredient is certainly not a recognizable food."""
    return {**{f: 0.0 for f in FLAGS}, "unclear": 1.0}


def label_item(client, text):
    from typesafe_sdk import Noul  # imported here so classify_ingredients.py works without the SDK
    """One Jev call: the ingredient is the state, each flag is a Noul question."""
    if not text.strip():
        return blank_probs()
    resp = client.system_one(
        state=text,
        questions={f: Noul(instructions=FLAG_PREFIX + q) for f, q in QUESTIONS.items()},
    )
    return {f: resp.nouls[f].noul for f in QUESTIONS}


def label_batch(client, batch_no, items):
    from typesafe_sdk import TypeSafeAPIError
    probs = []
    for text in items:
        try:
            p = label_item(client, text)
        except TypeSafeAPIError as e:
            if e.status in FATAL_CODES:  # bad key / bad request: retrying cannot help
                raise FatalAPIError(f"HTTP {e.status} from Jev for model {MODEL!r}: {e}") from e
            raise  # the SDK already retried 429/5xx; fail the batch, it reruns next time
        probs.append(p)
    return {"batch": batch_no, "model": MODEL, "items": items, "probs": probs}


FATAL_CODES = {400, 401, 403, 404}


class FatalAPIError(RuntimeError):
    """A Jev error that retrying will not fix (key, model name, permissions, bad request)."""


def load_env():
    """Put KEY=value lines from ../.env into os.environ (existing variables win)."""
    path = HERE.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def make_client():
    from typesafe_sdk import TypeSafeClient
    load_env()
    return TypeSafeClient(model=MODEL)  # reads TYPESAFE_API_KEY


def preflight(client):
    """One tiny request, so a bad key or model name fails once with the real error."""
    try:
        label_item(client, "milk")
    except Exception as e:
        print(f"preflight failed for model {MODEL!r}: {type(e).__name__}: {e}", file=sys.stderr)
        return False
    print(f"preflight ok: {MODEL}", flush=True)
    return True


def cache_path(batch_no):
    return CACHE / f"batch_{batch_no:05d}.json"


def manual_path(batch_no):
    return MANUAL / f"batch_{batch_no:05d}.csv"


def write_cache(result):
    CACHE.mkdir(exist_ok=True)
    path = cache_path(result["batch"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def label_all(limit):
    items = load_ingredients()
    todo = [
        (n, chunk) for n, chunk in batches(items)
        if not cache_path(n).exists() and not manual_path(n).exists()
    ]
    if limit is not None:
        todo = todo[:limit]
    print(f"{len(items)} ingredients, {len(todo)} batches to label with {MODEL}", flush=True)

    client = make_client()
    if todo and not preflight(client):
        return False
    failed = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(label_batch, client, n, chunk): n for n, chunk in todo}
        for done, fut in enumerate(as_completed(futures), 1):
            n = futures[fut]
            try:
                write_cache(fut.result())
            except Exception as e:  # keep going; failed batches rerun next time
                failed.append(n)
                print(f"[error] {e}", file=sys.stderr, flush=True)
            if done % 10 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)} batches done", flush=True)
    if failed:
        print(f"{len(failed)} batches failed; re-run the script to retry them: {sorted(failed)}", file=sys.stderr)
    return not failed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="label at most this many batches")
    parser.add_argument("--dry-run", action="store_true", help="print batch counts, no API calls")
    args = parser.parse_args()

    if args.dry_run:
        items = load_ingredients()
        print(f"{len(items)} ingredients -> {len(list(batches(items)))} batches of {BATCH}")
        return 0
    ok = label_all(args.limit)
    print("done; run classify_ingredients.py to build the CSVs")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
