# Search UI — design (draft)

Status: **approved 2026-11-16.**

## Intent

Internal tool for testing search quality of Semantic Recipe Search (see README). Main job: type a natural-language query, see ranked recipes, and judge quickly whether ranking and dietary filters behaved correctly. Inspiration: [Refero](https://refero.design/) — search bar is the page, browsable grid underneath. Visual language from DESIGN.md (paper, serif opening, orange organic dots, ruled sections, charcoal footer).

## Goals

- Search bar as primary element; sample recipes visible before any search.
- Show how query was parsed (semantic text vs exclude/include terms) so parser mistakes are obvious.
- Per result: why it matched, flags, source link.
- Expose filtered-out candidates with the reason they were removed, to catch over-filtering (especially *unknown* ingredients).
- Spot allergen leaks at a glance without reading ingredient lists.

## Non-goals

- Public consumer product, accounts, saved favorites.
- Recipe images (dataset has none).
- Medical-grade allergen claims.

## Anti-goals

- Hiding the filter step: if a user can't tell why a recipe was removed or kept, the tool fails its purpose even if search works.
- Dashboard/metric-card look (DESIGN.md Don'ts).

## Constraints

- Search backend does not exist yet (only ingredient labeling in `ingredient_categorization/`). UI built against a JSON contract with mock data first.
- No images in RecipeNLG.
- DESIGN.md forbids reusing the Airtree name; product needs own wordmark.
- RecipeNLG `link` values often lack a scheme (`www.cookbooks.com/...`); prefix `https://` when rendering.

## Approaches (stack)

1. **Custom HTML/CSS/JS frontend + small FastAPI backend** — *chosen (Claude's call).* Full control over DESIGN.md typography, grid, SVG constellations. FastAPI wraps future `src/search.py` in Python. Static frontend, no build step.
2. **Streamlit/Gradio** (README roadmap) — fastest to wire to Python, but can't carry DESIGN.md (fonts, index nav, custom grid, hover tooltips on SVG) without heavy hacks. Rejected.
3. **React/Vite** — fine, but adds a build toolchain for a single-page tool. Rejected unless UI grows.

## Page layout

```
 [wordmark]                         ○ Search  ○ About
 ───────────────────────────────────────────────────
           Describe a dish. We'll find the recipe.
   ┌─────────────────────────────────────────────┐
   │ dim sum without peanut oil               ⏎  │
   └─────────────────────────────────────────────┘
     semantic: "dim sum"   exclude: peanut  ✕
     ⚠ Tags are heuristic, not medical-grade
 ── 24 results ─────────────────────────────────────
  [tile] [tile] [tile] [tile]      4-col grid
  title · 0.82 · flags · source ↗
 ── Filtered out (14) ▸ ────────────────────────────
 [charcoal footer + wordmark]
```

- **Opening:** sky fade + scattered orange seed dots (DESIGN.md first-screen recipe). Headline (decided): **"Describe a dish. We'll find the recipe."** in display serif.
- **Search field:** large, centered. Placeholder rotates example queries (`spicy ground beef skillet meal`, `dim sum without peanut oil`, `high-protein dinner, no dairy, no nuts`).
- **Parsed-query chips** under field: semantic text, exclude/include terms. (Claude's call.)
- **Disclaimer** next to results, not only footer.
- **Empty state:** grid of random sample recipes.
- **Results:** 4-column grid (directory grid, 9.4px gutters), fewer columns on narrow screens.
- **Filtered out:** collapsed ruled row `Filtered out (N) ▸`; expands to dimmed cards with reason, e.g. `removed: "peanut oil" → peanut`, `removed: "zaatar" → unknown`. (Decided.)

## Result card

- **Top: ingredient constellation tile** (decided). Square, 18.7px radius, paper or charcoal backing. One dot per ingredient, positions seeded by recipe id (stable).
  - Orange `#fb5e00` = ingredient carries an allergen flag (tree nut, peanut, dairy, gluten, egg, soy, fish, shellfish, sesame).
  - Charcoal = labeled, no allergen flag.
  - Hollow = unlabeled/unknown.
  - Hover dot: ingredient name + flags.
  - Exact color mapping is Claude's call.
- **Below, on paper:** title (label style), similarity score, flag chips, source link ↗ (decided).
- **Why it matched** (decided; contents Claude's call): score, query terms found in title/ingredients, filters passed. Shown on card expand or detail view.

## API contract (for mock + real backend)

`GET /api/search?q=<text>&k=100`

```json
{
  "query": {"raw": "dim sum without peanut oil", "semantic": "dim sum", "exclude": ["peanut"], "include": []},
  "results": [
    {
      "id": 123, "title": "Pork Dumplings", "score": 0.77,
      "link": "https://www.example.com/...", "source": "Gathered",
      "ingredients": [{"raw": "1 lb ground pork", "name": "ground pork", "flags": ["meat", "pork", "protein"], "known": true}],
      "flags": {"pork": 1, "soy": 1},
      "why": {"matched_terms": ["dumpling"], "passed_filters": ["peanut"]}
    }
  ],
  "filtered_out": [
    {"id": 456, "title": "...", "score": 0.80, "reason": {"ingredient": "peanut oil", "flag": "peanut"}}
  ]
}
```

`GET /api/samples?n=12` → list of result-shaped recipes for empty state.

## Left to builder

- Product name / wordmark (placeholder until decided).
- Mobile column counts and nav collapse.
- Card expand vs separate detail view for "why it matched".
- Mock data: generate from real labeled ingredients where possible.

## Deferred (Claude's calls, user approved doc with these open)

1. **Evaluation marking:** v1 is view-only. Marking results right/wrong and saving to `eval/judgments.jsonl` is a follow-up; keep card layout room for a mark control.
2. **Product name:** placeholder wordmark until named.
