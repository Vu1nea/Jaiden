# Ingredient labeling: process and decisions

Goal: a lookup table that maps every unique ingredient string in the RecipeNLG dataset to allergen and diet
flags by *meaning*, not by substring matching ("coconut milk" is not dairy, "nutmeg" is not a tree nut).
Result: **234,059 rows** in `labeled_ingredients.csv`, 28 columns (12 definite flags, `protein_source`,
`unclear`, 12 `maybe_*` twins, `note`).

## 1. Pipeline overview

```mermaid
flowchart TD
    A["RecipeNLG_dataset.csv<br/>2.2M recipes, 2.3 GB"] --> B["export.py<br/>explode NER lists, unique, keep first-seen order"]
    B --> C["unique_values.csv<br/>234,059 strings"]
    C --> D["Split into 1,171 batches of 200 rows"]

    D --> E["Batches 0-106<br/>Claude Haiku via Claude Code"]
    D --> F["85 batches<br/>Gemini flash-lite"]
    D --> G["979 batches<br/>TypeSafe Jev"]

    E --> H[("labeled_manual/<br/>CSV, final flags")]
    F --> I[("labeled/*.json<br/>final flags")]
    G --> J[("labeled/*.json<br/>raw probabilities")]

    H --> K["classify_ingredients.py"]
    I --> K
    J --> K
    K --> L["labeled_ingredients.csv<br/>28 columns, 0/1 flags"]

    classDef paid fill:#fde8c8,stroke:#b8741a,color:#222;
    classDef free fill:#d6f0dc,stroke:#2f7a45,color:#222;
    class E,F,G paid;
    class K,B free;
```

Orange = costs money (LLM calls). Green = free to re-run.

Batch *n* covers data rows `n*200 .. n*200+199` of `unique_values.csv`. Because batch numbers are positional,
`export.py` must keep first-seen order; sorting it would silently misalign every cached batch.

## 2. How labeling evolved

```mermaid
flowchart LR
    S1["Stage 1<br/>Claude Haiku via Claude Code<br/>batches 0-106, ~21k rows"] --> S2["Stage 2<br/>Gemini flash-lite API script<br/>85 batches"]
    S2 --> S3["Stage 3<br/>TypeSafe Jev API script<br/>979 batches"]
```

| Stage | Source | Output | Notes |
|---|---|---|---|
| 1 | Claude Haiku, run through Claude Code reading the batch files | `labeled_manual/batch_*.csv` | The folder name says "manual" but these are model labels, not human labels. Treat them as a strong reference, not ground truth. |
| 2 | Gemini `gemini-3.5-flash-lite`, 200 ingredients per request, JSON array out | `labeled/*.json` with final flags, confidence, notes | No probabilities, so these rows cannot be re-thresholded. |
| 3 | TypeSafe Jev, one call per ingredient | `labeled/*.json` with raw probabilities | Cheap and returns a probability per flag (not calibrated), so thresholds are tunable for free. |

## 3. Model choice

```mermaid
flowchart TD
    S(["Label 234k short ingredient strings<br/>with allergen and diet flags"]) --> H["Step 1: Claude Haiku via Claude Code<br/>batches 0-106, ~21k rows"]
    H --> HR["Worked for the first batches.<br/>Labeling by hand-feeding batches does not scale to 234k rows."]
    HR -->|"automate with an API script"| G["Step 2: Gemini flash-lite, free-text JSON out"]
    G --> GR["Worked for 85 batches, but output is final 0/1 only.<br/>Thresholds cannot be changed afterwards."]
    GR -->|"switched"| J["Step 3: TypeSafe Jev, typed yes/no questions"]
    J ==> JR["CHOSEN.<br/>979 batches. Probability per question,<br/>no output tokens to parse."]

    classDef question fill:#e8eefc,stroke:#3b5bdb,color:#222;
    classDef step fill:#f4f4f4,stroke:#888,color:#222;
    classDef chosen fill:#d6f0dc,stroke:#2f7a45,stroke-width:3px,color:#222;
    classDef used fill:#fde8c8,stroke:#b8741a,color:#222;
    class S question;
    class H,G,J step;
    class HR,GR used;
    class JR chosen;
```

## 4. How a Jev call works

One ingredient is the *state*. The 14 flags (12 allergen/diet flags, `protein_source`, `unclear`) are 14
yes/no (`Noul`) questions, each with the labeling rules written into its instructions.

```mermaid
sequenceDiagram
    participant S as label_ingredients.py
    participant J as Jev API
    participant C as labeled/batch_N.json
    loop each ingredient in the batch (200)
        S->>J: state = ingredient text, 14 Noul questions
        J-->>S: 14 probabilities (0 to 1)
    end
    S->>C: items + probs for the whole batch
    Note over S,J: 16 batches run in parallel.<br/>SDK retries 429/5xx, 400/401/403/404 abort.
```

Why one call per ingredient: a Jev call evaluates questions against a single state. Packing 200 ingredients
into one state would need 2,800 questions that each point at an index, which is fragile.

## 5. Probabilities to flags

```mermaid
flowchart TD
    P["probability p for flag X"] --> D{"p >= 0.85 ?"}
    D -- yes --> F1["X = 1"]
    D -- no --> M{"p >= 0.35 ?"}
    M -- yes --> F2["maybe_X = 1"]
    M -- no --> F3["X = 0, maybe_X = 0"]
    F1 --> R["Consistency rules"]
    F2 --> R
    F3 --> R
    R --> R1["pork or beef implies meat"]
    R --> R2["maybe_pork or maybe_beef implies maybe_meat if meat is 0"]
    R --> R3["definite X overrides maybe_X"]
    R --> R4["blank ingredient: unclear = 1"]
```

The thresholds `0.85` and `0.35` are untuned guesses. They live in `classify_ingredients.py` and can be changed
with `--t-definite` and `--t-maybe`. Re-running never calls the API.

## 6. Output design decisions

```mermaid
flowchart TD
    Q["How do we keep the model's confidence?"]
    Q --> A["Add source and confidence columns<br/>to the main CSV"]
    Q --> B["Drop maybe_ columns, store raw<br/>probabilities in the main CSV"]
    Q --> C["Write the probability into the<br/>flag cell instead of 1"]
    Q --> D["Keep the main CSV as clean 0/1,<br/>put probabilities in a second file"]

    A --> RA["Rejected: not needed in the final output"]
    B --> RB["Rejected: changes the schema and mixes<br/>model scores with 1/0.5/0 conventions"]
    C --> RC["Considered: keeps schema, but floats<br/>in a 0/1 column surprise consumers"]
    D --> RD["CHOSEN: ingredient_scores.csv<br/>blank for rows without probabilities"]
```

## 7. Script split

```mermaid
flowchart LR
    U["unique_values.csv"] --> L["label_ingredients.py<br/>only script that calls the API"]
    L --> CACHE[("labeled/*.json")]
    CACHE --> CL["classify_ingredients.py<br/>free, re-runnable"]
    MAN[("labeled_manual/*.csv")] --> CL
    CL --> OUT["labeled_ingredients.csv"]
```

`label_ingredients.py` is resumable: cached and `labeled_manual/` batches are skipped, so re-running only does
what is missing. `TYPESAFE_API_KEY` is read from `../.env`.

## 8. Numbers

| Item | Value |
|---|---|
| Unique ingredient strings | 234,059 |
| Batches | 1,171 (200 rows each) |
| Claude Haiku batches | 107 (0-106), ~21.4k rows |
| Gemini batches | 85 |
| Jev batches | 979, ~196k rows |
| Jev model | `jev-latest`, price 0.042 USD per million input tokens |
| Smoke test | 2 batches (400 calls) in about 19 s |
| Cost of the Jev run | Estimated about ~ 9CAD |

## 9. Known limits and open items

- Jev thresholds are untuned. We skipped evaluation on purpose: this is a test project, and the only labels to
  compare against are Haiku's, so agreement would not mean correctness anyway.
- Jev tends to over-flag `maybe_*` (for example `maybe_meat` on "Florida eggs"). Raising `--t-maybe` trims it.
- Jev rows have an empty `note`; Haiku and Gemini rows keep theirs.
- Gemini rows are frozen (no probabilities), so threshold changes only affect the Jev rows.
- `least_sure_20.csv` was not useful: with about 196k Jev rows, the top 20 closest to 0.5 were all exact ties.

## 10. Files that were generated and then deleted

These existed during the work and were removed to save space or because they were derivable. None is needed
to reproduce the main table.

| File | What it was | How to get it back |
|---|---|---|
| `ingredient_scores.csv` | Raw Jev probability per flag, blank for Haiku and Gemini rows | `python classify_ingredients.py` |
| `least_sure_20.csv` | 20 Jev rows with a flag closest to 0.5 | `python classify_ingredients.py` (output was all ties) |
| `labeled_manual_combined.csv` | The Haiku batches concatenated | concatenate `labeled_manual/*.csv` |
| `least_sure_20_manual.csv` | Review sample from the Haiku phase | not needed |

Note: `classify_ingredients.py` still writes `ingredient_scores.csv` and `least_sure_20.csv` on every run.
