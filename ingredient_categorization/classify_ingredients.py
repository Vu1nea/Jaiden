#!/usr/bin/env python3
"""Turn cached Jev probabilities into flags and write the CSV outputs. Never calls the API.

Reads labeled/batch_*.json (written by label_ingredients.py) plus the hand-labeled batches in
labeled_manual/, applies the thresholds below, and writes the combined lookup table.

Usage (from this folder):
  python classify_ingredients.py
  python classify_ingredients.py --t-definite 0.9 --t-maybe 0.5   # re-threshold; free, takes seconds

Outputs:
  labeled_ingredients.csv       combined lookup table (28 columns, 0/1 flags)
  ingredient_scores.csv         raw Jev probability per flag; blank for hand-labeled/Gemini rows
  least_sure_20.csv             20 Jev rows whose least-decided flag is closest to 0.5
"""
import argparse
import csv
import json
import sys

from label_ingredients import (
    ALL_FLAGS, BATCH, CACHE, DEFINITE, FLAGS, HEADER, HERE, batches, blank_probs,
    load_ingredients, manual_path,
)

OUT = HERE / "labeled_ingredients.csv"
REVIEW = HERE / "least_sure_20.csv"
SCORES = HERE / "ingredient_scores.csv"

# Jev answers each yes/no question with a probability. Probability >= T_DEFINITE sets the
# flag; T_MAYBE <= p < T_DEFINITE sets the maybe_ twin (definite flags only). Tune on the
# hand-labeled batches; raw probabilities are cached so re-thresholding needs no API calls.
T_DEFINITE = 0.85
T_MAYBE = 0.35


def probs_to_row(probs, t_definite=T_DEFINITE, t_maybe=T_MAYBE):
    """Turn per-question probabilities into the 26 flags.
    """
    row = {f: int(probs[f] >= t_definite) for f in FLAGS}
    for f in DEFINITE:
        row["maybe_" + f] = int(t_maybe <= probs[f] < t_definite)
    if row["pork"] or row["beef"]:
        row["meat"] = 1
    if (row["maybe_pork"] or row["maybe_beef"]) and not row["meat"]:
        row["maybe_meat"] = 1
    for f in DEFINITE:  # a definite flag overrides its maybe_ twin
        if row[f]:
            row["maybe_" + f] = 0
    row["note"] = ""
    return row


def combine(t_definite=T_DEFINITE, t_maybe=T_MAYBE):
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

    # Hand-labeled batches take precedence; Jev cache fills the rest, in source order.
    out_rows = []     # CSV rows, 28 columns
    score_rows = []   # [ingredient] + 14 probabilities, blank when the row has none
    jev_probs = []    # (item, probs) for the least-sure review
    for n, _ in batches(items):
        if n in manual:
            with manual_path(n).open(newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                if next(reader) != HEADER:
                    raise ValueError(f"{manual_path(n)} header does not match the 28-column schema")
                for row in reader:
                    out_rows.append(row)
                    score_rows.append([row[0]] + [""] * len(FLAGS))
        elif n in cached:
            result = cached[n]
            if "probs" in result:  # Jev: raw probabilities, re-thresholded here
                probs = [p if item.strip() else blank_probs() for item, p in zip(result["items"], result["probs"])]
                rows = [probs_to_row(p, t_definite, t_maybe) for p in probs]
            else:  # older Gemini caches hold final rows and no probabilities
                probs, rows = [None] * len(result["items"]), result["rows"]
            for item, p, row in zip(result["items"], probs, rows):
                out_rows.append([item] + [row[k] for k in ALL_FLAGS] + [row["note"]])
                score_rows.append([item] + ([""] * len(FLAGS) if p is None else [round(p[f], 2) for f in FLAGS]))
                if p is not None:
                    jev_probs.append((item, p))

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(out_rows)

    with SCORES.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ingredient"] + FLAGS)
        writer.writerows(score_rows)

    def least_decided(pair):  # (flag, probability) closest to 0.5
        return min(pair[1].items(), key=lambda kv: abs(kv[1] - 0.5))

    ranked = sorted(jev_probs, key=lambda pair: abs(least_decided(pair)[1] - 0.5))
    with REVIEW.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ingredient", "flag", "probability"])
        for pair in ranked[:20]:
            flag, p = least_decided(pair)
            writer.writerow([pair[0], flag, round(p, 2)])

    print(f"wrote {len(out_rows)} labeled rows to {OUT}")
    print(f"wrote {len(score_rows)} score rows to {SCORES}")
    print(f"wrote 20 least-sure rows to {REVIEW}")
    return not missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--t-definite", type=float, default=T_DEFINITE, help="probability that sets a flag")
    parser.add_argument("--t-maybe", type=float, default=T_MAYBE, help="probability that sets a maybe_ flag")
    args = parser.parse_args()
    return 0 if combine(args.t_definite, args.t_maybe) else 1


if __name__ == "__main__":
    sys.exit(main())
