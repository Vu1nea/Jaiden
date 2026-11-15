#!/usr/bin/env python3
"""Label every unique RecipeNLG ingredient string with Gemini, in batches.

Resumable: each batch's model output is cached in labeled/ and skipped on re-run.
Batches already hand-labeled in labeled_manual/ are skipped and reused as-is in the
combined output (same 28-column schema, including the maybe_* columns).

Usage (from this folder):
  pip install google-genai
  export GEMINI_API_KEY=...
  python label_ingredients.py --limit 2     # smoke test: first 2 batches only
  python label_ingredients.py               # all batches (resumes if interrupted)
  python label_ingredients.py --combine     # rebuild outputs from cache only
  python label_ingredients.py --dry-run     # show batch count, no API calls

Outputs:
  labeled/batch_NNNNN.json      cached per-batch labels
  labeled_ingredients.csv       combined lookup table (required header)
  least_sure_20.csv             20 rows the model was least confident about
"""
import argparse
import csv
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "unique_values.csv"
CACHE = HERE / "labeled"
OUT = HERE / "labeled_ingredients.csv"
REVIEW = HERE / "least_sure_20.csv"

MANUAL = HERE / "labeled_manual"  # hand-labeled batches; same 28-column schema, never re-sent to the API

MODEL = "gemini-3.8-flash"
BATCH = 200
WORKERS = 4
MAX_ATTEMPTS = 5

DEFINITE = [
    "tree_nut", "peanut", "dairy", "gluten", "egg", "soy", "fish",
    "shellfish", "sesame", "meat", "pork", "beef",
]
FLAGS = DEFINITE + ["protein_source", "unclear"]
MAYBE = ["maybe_" + f for f in DEFINITE]
ALL_FLAGS = FLAGS + MAYBE  # 26 values per row, in CSV column order
HEADER = ["ingredient"] + ALL_FLAGS + ["note"]  # 28 columns
CONF_RANK = {"l": 0, "m": 1, "h": 2}

SYSTEM = """You label ingredient strings from recipes for an allergen and diet lookup table.
Label each ingredient by its MEANING, not by substring matching. Output 0 or 1 for each flag.

Flags:
- tree_nut: contains or is derived from tree nuts (almond, walnut, cashew, pecan, pistachio, hazelnut, macadamia, pine nut, brazil nut, chestnut, praline, marzipan, nut flours/butters/oils, generic "nuts").
- peanut: peanuts and peanut-derived items (peanut butter, peanut oil).
- dairy: milk and milk-derived items (butter, cheese, cream, yogurt, whey, ghee, casein, buttermilk, custard). Plant milks and non-dairy "butters" (coconut milk, almond milk, cocoa butter, peanut butter) are NOT dairy.
- gluten: wheat, barley, rye and derivatives (flour, bread, pasta, soy sauce, couscous, beer).
- egg: eggs and egg-derived items.
- soy: soy and soy-derived items (tofu, tempeh, soy sauce, edamame, miso, soy milk).
- fish: fish and fish-derived items (anchovy, fish sauce, salmon, tuna).
- shellfish: shrimp, crab, lobster, clams, mussels, oysters, scallops, squid, etc.
- sesame: sesame seeds, tahini, sesame oil.
- meat: any mammal or poultry flesh, including bacon, ham and sausage. Fish and shellfish are NOT meat.
- pork: pork-derived (pork, bacon, ham, sausage made of pork, lard).
- beef: beef-derived (beef, steak, ground beef, beef broth).
- protein_source: 1 if the ingredient is a main protein source (meat, poultry, fish, shellfish, eggs, tofu, tempeh, legumes, protein powder, Greek yogurt, cottage cheese, etc.), else 0.
- unclear: 1 if you cannot tell what the ingredient is or it is not really an ingredient (e.g. "bite", "c.", garbled text, blank, a non-food phrase).

"Maybe" flags (maybe_tree_nut, maybe_peanut, maybe_dairy, maybe_gluten, maybe_egg, maybe_soy, maybe_fish, maybe_shellfish, maybe_sesame, maybe_meat, maybe_pork, maybe_beef):
- Set maybe_X=1 when the ingredient plausibly or usually contains X but it is not certain (assumed, usually, typically, may contain, unspecified type, brand/mix/prepared food whose recipe varies). Set the definite flag X=1 only when the ingredient certainly contains X.
- Never set both X and maybe_X to 1; if X=1 then maybe_X=0.
- Examples: sausage with unspecified type -> meat=1, maybe_pork=1, maybe_beef=1. Gelatin, marshmallows, gummies, jello -> maybe_meat, maybe_pork, maybe_beef (animal-derived but source varies). Stock, broth, bouillon -> maybe_meat (and maybe_beef/maybe_pork when named or implied). Canned cream soup -> maybe_gluten, maybe_dairy. Pie crust, pastry, cake or cookie mix -> gluten=1 plus maybe_dairy, maybe_egg. Chocolate -> maybe_dairy, maybe_soy. Dry pasta -> gluten=1, maybe_egg. Mixed nuts -> tree_nut=1, maybe_peanut=1.

Rules:
- Be conservative for allergens: if an ingredient plausibly contains an allergen (e.g. "mixed nuts", "chocolate bar", "pesto", "worcestershire sauce" for fish/anchovy, "curry paste" for shellfish), flag it (definite if certain, otherwise the maybe_ flag) and explain briefly in note.
- For real-world ambiguity, use the real-world answer and explain in note. Nutmeg, mace and water chestnut are not tree nuts (tree_nut=0). Coconut in any form is NOT a tree nut (tree_nut=0, note "coconut is a drupe not a nut"). Chestnut, pecan, almond, walnut, cashew, pistachio, hazelnut, pine nut and generic "nuts" are tree nuts.
- pork=1 or beef=1 implies meat=1. maybe_pork=1 or maybe_beef=1 with meat=0 implies maybe_meat=1.
- Typos: label the intended ingredient and say so in note (e.g. "aigs" -> egg, note "typo for eggs").
- Non-food phrases ("happiness", "patience", "not an ingredient") and fragments you cannot interpret: unclear=1, all other flags 0.
- Keep note empty ("") unless it explains an allergen call, a maybe flag, a typo, or a real-world clarification. Max 15 words.
- confidence: "h" (high), "m" (medium), or "l" (low) for the whole row.

Output format: return ONLY a JSON array, no prose, no code fence. One entry per input line, in order, each entry an array of 29 values:
[i, tree_nut, peanut, dairy, gluten, egg, soy, fish, shellfish, sesame, meat, pork, beef, protein_source, unclear, maybe_tree_nut, maybe_peanut, maybe_dairy, maybe_gluten, maybe_egg, maybe_soy, maybe_fish, maybe_shellfish, maybe_sesame, maybe_meat, maybe_pork, maybe_beef, confidence, note]
where i is the input index (integer), flags are integers 0 or 1, confidence is "h"/"m"/"l", note is a string.
"""


def load_ingredients():
    """Every row of unique_values.csv after the header, including blanks (never skipped)."""
    with SRC.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        next(reader)
        return [row[0] if row else "" for row in reader]


def batches(items):
    for start in range(0, len(items), BATCH):
        yield start // BATCH, items[start:start + BATCH]


def build_user_message(items):
    lines = [f"{i}: {json.dumps(text, ensure_ascii=False)}" for i, text in enumerate(items)]
    return f"Label these {len(items)} ingredients (index: text):\n" + "\n".join(lines)


def parse_response(text, n):
    """Validate the model's JSON. Returns one dict per input index, 0..n-1."""
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise ValueError("no JSON array in response")
    data = json.loads(m.group(0))
    by_index = {}
    for entry in data:
        if not isinstance(entry, list) or len(entry) != 29:
            raise ValueError(f"bad entry: {entry!r}")
        i = int(entry[0])
        flags = [int(v) for v in entry[1:27]]
        if any(v not in (0, 1) for v in flags):
            raise ValueError(f"non-binary flag at index {i}")
        conf = str(entry[27]).strip().lower()[:1]
        if conf not in CONF_RANK:
            raise ValueError(f"bad confidence at index {i}: {entry[27]!r}")
        row = dict(zip(ALL_FLAGS, flags))
        row["note"] = str(entry[28]).strip()
        row["confidence"] = conf
        by_index[i] = row
    if set(by_index) != set(range(n)):
        raise ValueError(f"expected {n} rows, got {len(by_index)}")
    rows = [by_index[i] for i in range(n)]
    for row in rows:
        if row["pork"] or row["beef"]:
            row["meat"] = 1
        if (row["maybe_pork"] or row["maybe_beef"]) and not row["meat"]:
            row["maybe_meat"] = 1
        for f in DEFINITE:  # a definite flag overrides its maybe_ twin
            if row[f]:
                row["maybe_" + f] = 0
    return rows


def label_batch(client, batch_no, items):
    from google.genai import errors, types

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        max_output_tokens=32000,
        temperature=0,
        response_mime_type="application/json",
    )
    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = client.models.generate_content(
                model=MODEL, contents=build_user_message(items), config=config
            )
            return {
                "batch": batch_no,
                "model": MODEL,
                "items": items,
                "rows": parse_response(resp.text or "", len(items)),
            }
        except errors.APIError as e:  # rate limit / overload: back off and retry
            last_error = e
            print(f"[retry] batch {batch_no} attempt {attempt + 1}/{MAX_ATTEMPTS}: {e}", file=sys.stderr, flush=True)
            time.sleep(min(60, 5 * 2 ** attempt))
        except (ValueError, KeyError, json.JSONDecodeError) as e:  # bad model output: retry
            last_error = e
            print(f"[retry] batch {batch_no} attempt {attempt + 1}/{MAX_ATTEMPTS}: bad output: {e}", file=sys.stderr, flush=True)
    raise RuntimeError(f"batch {batch_no} failed after {MAX_ATTEMPTS} attempts: {last_error}")


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
    from google import genai
    from google.genai import types  # imported here so --combine / --dry-run work without the SDK

    items = load_ingredients()
    todo = [
        (n, chunk) for n, chunk in batches(items)
        if not cache_path(n).exists() and not manual_path(n).exists()
    ]
    if limit is not None:
        todo = todo[:limit]
    print(f"{len(items)} ingredients, {len(todo)} batches to label with {MODEL}", flush=True)

    # reads GEMINI_API_KEY from the environment; 3-minute timeout so a hung request fails visibly
    client = genai.Client(http_options=types.HttpOptions(timeout=180_000))
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


def combine():
    items = load_ingredients()
    expected = {n for n, _ in batches(items)}
    cached = {}
    for path in sorted(CACHE.glob("batch_*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        cached[result["batch"]] = result

    manual = {n for n, _ in batches(items) if manual_path(n).exists()}
    missing = sorted(expected - set(cached) - manual)
    if missing:
        print(f"warning: {len(missing)} batches not labeled yet (first few: {missing[:5]})", file=sys.stderr)

    # Hand-labeled batches take precedence; Gemini cache fills the rest, in source order.
    out_rows = []   # CSV rows, 28 columns
    gemini_rows = []  # (item, row dict) for the least-sure review
    for n, _ in batches(items):
        if n in manual:
            with manual_path(n).open(newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                if next(reader) != HEADER:
                    raise ValueError(f"{manual_path(n)} header does not match the 28-column schema")
                out_rows.extend(reader)
        elif n in cached:
            for item, row in zip(cached[n]["items"], cached[n]["rows"]):
                out_rows.append([item] + [row[k] for k in ALL_FLAGS] + [row["note"]])
                gemini_rows.append((item, row))

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(out_rows)
    all_rows = out_rows

    ranked = sorted(gemini_rows, key=lambda pair: (CONF_RANK[pair[1]["confidence"]], -len(pair[1]["note"])))
    with REVIEW.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ingredient", "confidence", "note"])
        for item, row in ranked[:20]:
            writer.writerow([item, row["confidence"], row["note"]])

    print(f"wrote {len(all_rows)} labeled rows to {OUT}")
    print(f"wrote 20 least-sure rows to {REVIEW}")
    return not missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="label at most this many batches")
    parser.add_argument("--combine", action="store_true", help="only rebuild outputs from cache")
    parser.add_argument("--dry-run", action="store_true", help="print batch counts, no API calls")
    args = parser.parse_args()

    if args.dry_run:
        items = load_ingredients()
        print(f"{len(items)} ingredients -> {len(list(batches(items)))} batches of {BATCH}")
        return 0
    if args.combine:
        return 0 if combine() else 1
    ok = label_all(args.limit)
    combine()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
