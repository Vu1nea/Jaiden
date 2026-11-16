# Semantic Recipe Search

Search a large recipe dataset ([RecipeNLG](https://recipenlg.cs.put.poznan.pl/)) using natural language, with hard dietary filters for allergens and ingredients.

Example queries:

- `spicy ground beef skillet meal`
- `dim sum without peanut oil`
- `high-protein dinner, no dairy, no nuts`

## How it works

Semantic search is good at matching what a recipe *is* ("spicy beef skillet") but unreliable at *exclusion* ("without peanuts"), because embeddings place "with peanuts" and "without peanuts" close together. So the project splits the job in two:

1. **Semantic ranking (fuzzy).** Each recipe is embedded as `title + ingredient list` with a sentence-transformer model. A query is embedded the same way and the nearest recipes are retrieved.
2. **Ingredient filtering (exact).** Every ingredient is labeled once offline (tree nut, peanut, dairy, gluten, egg, soy, fish, shellfish, sesame, meat, pork, beef, protein source). Recipe-level flags are derived from those labels, and exclusions are applied as exact set lookups, never by similarity.

```
unique ingredients --(LLM labeling, offline)--> ingredient -> flags
recipes            --(lookup per ingredient)--> recipe -> flags
query --> parse ("without X") --> semantic search --> candidates --> exact flag filter --> results
```

## Dataset

RecipeNLG CSV (~2.14 GB, ~2M recipes). **Not included in the repo.** Download it from the RecipeNLG page or Kaggle and place it at `data/recipes.csv`.

Columns: `id`, `title`, `ingredients` (JSON list of raw lines), `directions` (JSON list), `link`, `source`, `NER` (JSON list of cleaned ingredient names).

The `ingredients`, `directions` and `NER` columns are JSON strings and must be parsed with `json.loads`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install pandas sentence-transformers numpy anthropic
```

Work on a sample first (e.g. `nrows=50_000`) before running on the full dataset.

## Build steps

1. **Count ingredients.** Normalize every NER term and count occurrences; export `ingredients_all.csv` (or a frequency-thresholded `ingredients_top.csv`).
2. **Label ingredients.** Label each unique ingredient with allergen/diet flags (via LLM batches) into `labels.jsonl`. Terms that are unlabeled count as *unknown* and are excluded by strict filters.
3. **Tag recipes.** For each recipe, take the max of each flag across its ingredients.
4. **Embed recipes.** Embed `title + ": " + NER` with `all-MiniLM-L6-v2`; store the vectors in `embeddings/`.
5. **Search.** Parse the query into semantic text plus exclude/include terms, retrieve the top ~100 by cosine similarity, then apply the filters.

## Project layout (planned)

```
data/                  # raw dataset (git-ignored)
embeddings/            # generated vectors/indexes (git-ignored)
ingredients_all.csv    # unique ingredients + counts
labels.jsonl           # ingredient -> flags
src/
  build_vocab.py       # step 1
  label_ingredients.py # step 2
  tag_recipes.py       # step 3
  embed.py             # step 4
  search.py            # step 5
```

## Running the UI

The search UI lives in `web/` (static HTML/CSS/JS, no build step). It currently runs on a 16-recipe mock set (`web/mock/recipes.json`) with flags taken from the real ingredient labels; the API is not wired up yet.

```bash
python -m http.server 8000 -d web
# open http://localhost:8000
```

UI tests: `node --test "tests/web/*.test.mjs"`

## Roadmap

- [ ] Baseline semantic search on a 50k-recipe sample
- [ ] Ingredient labeling and recipe tagging
- [ ] Query parser for "without X" / "no X" / "free of X"
- [ ] Evaluation set (~20 queries) including an allergen-leak check: no result may violate a stated exclusion
- [ ] Hybrid search (BM25 + vectors) and a cross-encoder reranker
- [ ] High-protein ranking (ingredient heuristic, then USDA FoodData Central)
- [ ] UI (Streamlit or Gradio)

## Disclaimer

Allergen and diet tags are heuristic and generated automatically. They are **not medical-grade**. Do not rely on this tool for serious allergies; always check the original recipe and ingredient labels.