// Client-side stand-in for the search API. Returns the same JSON shape as the
// planned GET /api/search and /api/samples so it can be swapped for fetch() later.

const TERM_FLAGS = {
  nut: ["tree_nut", "peanut"], nuts: ["tree_nut", "peanut"],
  peanut: ["peanut"], peanuts: ["peanut"], "peanut oil": ["peanut"],
  "tree nut": ["tree_nut"], "tree nuts": ["tree_nut"],
  dairy: ["dairy"], milk: ["dairy"], cheese: ["dairy"],
  gluten: ["gluten"], wheat: ["gluten"],
  egg: ["egg"], eggs: ["egg"],
  soy: ["soy"], fish: ["fish"],
  shellfish: ["shellfish"], shrimp: ["shellfish"],
  sesame: ["sesame"], meat: ["meat"], pork: ["pork"], beef: ["beef"],
};
const FLAG_NAMES = new Set(Object.values(TERM_FLAGS).flat());

const TRIGGER = "(?:without|no|free of)";
// A clause runs until punctuation (already turned into commas), end of query,
// or " and/or <another trigger>". Its term may itself list items with and/or.
const CLAUSE = new RegExp(`\\b${TRIGGER}\\s+([a-z' ]+?)(?=\\s*,|\\s+(?:and|or)\\s+${TRIGGER}\\b|\\s*$)`, "g");
const SUFFIX = /\b([a-z]+)-free\b/g;
const STOPWORDS = new Set(["and", "or", "with", "the", "for", "without"]);

export function parseQuery(raw) {
  const text = raw.toLowerCase().replace(/\bw\/o\b/g, "without").replace(/[.!?;()[\]]/g, ",");
  const terms = [];
  let rest = text.replace(CLAUSE, (_, t) => { terms.push(...t.trim().split(/\s+(?:and|or)\s+/)); return ","; });
  rest = rest.replace(SUFFIX, (_, t) => { terms.push(t); return ","; });
  const semantic = rest.split(",")
    .map((s) => s.trim().replace(/\s+/g, " "))
    .filter((s) => s && !/^(?:and|or)$/.test(s))
    .join(", ");

  const exclude = [];
  for (const t of terms) {
    for (const f of TERM_FLAGS[t] || [t]) if (!exclude.includes(f)) exclude.push(f);
  }
  return { raw, semantic, exclude, include: [] };
}

function tokens(text) {
  return [...new Set((text.toLowerCase().match(/[a-z]+/g) || []).filter((w) => w.length >= 3 && !STOPWORDS.has(w)))];
}

function filterReason(recipe, exclude) {
  for (const f of exclude.filter((x) => FLAG_NAMES.has(x))) {
    const hit = recipe.ingredients.find((i) => i.flags.includes(f));
    if (hit) return { ingredient: hit.name, flag: f };
  }
  for (const term of exclude.filter((x) => !FLAG_NAMES.has(x))) {
    const hit = recipe.ingredients.find((i) => i.name.toLowerCase().includes(term));
    if (hit) return { ingredient: hit.name, flag: "ingredient" };
  }
  if (exclude.length) {
    const hit = recipe.ingredients.find((i) => !i.known);
    if (hit) return { ingredient: hit.name, flag: "unknown" };
  }
  return null;
}

export const TAG_FLAGS = ["tree_nut", "peanut", "dairy", "gluten", "egg", "soy", "fish", "shellfish", "sesame", "meat", "pork", "beef"];

// extraExclude: flags picked from the tag selector, merged with exclusions parsed from the text.
export function runSearch(raw, recipes, k = 100, extraExclude = []) {
  const query = parseQuery(raw);
  for (const f of extraExclude) if (!query.exclude.includes(f)) query.exclude.push(f);
  const qTokens = tokens(query.semantic);
  const results = [];
  const filtered_out = [];

  for (const recipe of recipes) {
    const haystack = new Set(tokens([recipe.title, ...recipe.ingredients.map((i) => i.name)].join(" ")));
    const matched = qTokens.filter((t) => haystack.has(t));
    if (qTokens.length && !matched.length) continue;
    const score = qTokens.length ? Math.round((matched.length / qTokens.length) * 100) / 100 : 0;
    const item = { ...recipe, score, why: { matched_terms: matched, passed_filters: query.exclude } };
    const reason = filterReason(recipe, query.exclude);
    if (reason) filtered_out.push({ ...item, reason });
    else results.push(item);
  }

  const order = qTokens.length
    ? (a, b) => b.score - a.score || a.title.localeCompare(b.title)
    : (a, b) => a.title.localeCompare(b.title);
  results.sort(order);
  filtered_out.sort(order);
  return { query, results: results.slice(0, k), filtered_out };
}

let cache = null;
function loadRecipes() {
  if (!cache) {
    cache = fetch(new URL("./mock/recipes.json", import.meta.url))
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .catch((e) => { cache = null; throw e; });
  }
  return cache;
}

export async function fetchSearch(q, { exclude = [], k = 100 } = {}) {
  const text = (q || "").trim();
  if (!text && !exclude.length) throw new Error("empty query");
  return runSearch(text, await loadRecipes(), k, exclude);
}

export async function fetchSamples(n = 12) {
  const recipes = await loadRecipes();
  return recipes.slice(0, n).map((r) => ({ ...r, score: 0, why: { matched_terms: [], passed_filters: [] } }));
}
