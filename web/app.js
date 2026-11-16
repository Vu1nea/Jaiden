import { fetchSearch, fetchSamples, parseQuery, TAG_FLAGS } from "./mock-api.js";
import { renderCard } from "./card.js";
import { createLatest } from "./latest.js";

const latest = createLatest();

const EXAMPLES = [
  "spicy ground beef skillet meal",
  "dim sum without peanut oil",
  "high-protein dinner, no dairy, no nuts",
];

const $ = (id) => document.getElementById(id);
const form = $("search-form");
const input = $("q");
const parsed = $("parsed");
const heading = $("results-heading");
const status = $("status");
const grid = $("results");
const filtered = $("filtered");
const filteredLabel = $("filtered-label");
const filteredGrid = $("filtered-grid");

const label = (flag) => flag.replace(/_/g, " ");

function chip(text, className) {
  const li = document.createElement("li");
  li.textContent = text;
  if (className) li.className = className;
  return li;
}

// ---------- Exclude tags ----------
const selected = new Set();
const tagsEl = $("tags");
const tagButtons = new Map();
for (const flag of TAG_FLAGS) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "tag";
  b.textContent = label(flag);
  b.setAttribute("aria-pressed", "false");
  b.addEventListener("click", () => {
    if (selected.has(flag)) selected.delete(flag);
    else selected.add(flag);
    syncTags();
    submit(input.value);
  });
  tagButtons.set(flag, b);
  tagsEl.appendChild(b);
}
const clearTags = document.createElement("button");
clearTags.type = "button";
clearTags.className = "tags__clear";
clearTags.textContent = "clear";
clearTags.addEventListener("click", () => { selected.clear(); syncTags(); submit(input.value); });
tagsEl.appendChild(clearTags);

function syncTags() {
  for (const [flag, b] of tagButtons) b.setAttribute("aria-pressed", String(selected.has(flag)));
  clearTags.hidden = selected.size === 0;
}

function renderParsed(query) {
  const items = [];
  if (query.semantic) items.push(chip(`semantic: “${query.semantic}”`));
  for (const x of query.exclude) items.push(chip(`exclude: ${label(x)}`, "parsed__exclude"));
  parsed.replaceChildren(...items);
  parsed.hidden = items.length === 0;
}

function renderGrid(target, recipes, opts = () => ({})) {
  target.replaceChildren(...recipes.map((r) => renderCard(r, opts(r))));
}

async function showSamples(token) {
  parsed.hidden = true;
  heading.textContent = "Sample recipes";
  status.textContent = "";
  filtered.hidden = true;
  try {
    const samples = await fetchSamples(12);
    if (!latest.isCurrent(token)) return;
    renderGrid(grid, samples);
  } catch {
    if (!latest.isCurrent(token)) return;
    grid.replaceChildren();
    status.textContent = "Couldn't load sample recipes. Try reloading.";
  }
}

async function runQuery(q, exclude, token) {
  renderParsed(parseQuery(q));
  status.textContent = "Searching…";
  try {
    const res = await fetchSearch(q, { exclude });
    if (!latest.isCurrent(token)) return;
    const n = res.results.length;
    heading.textContent = `${n} result${n === 1 ? "" : "s"}`;
    status.textContent = n ? "" : "No recipes matched. Check the filtered-out list below.";
    renderGrid(grid, res.results);

    const m = res.filtered_out.length;
    filtered.hidden = m === 0;
    filteredLabel.textContent = `Filtered out (${m})`;
    renderGrid(filteredGrid, res.filtered_out, (r) => ({ dimmed: true, reason: r.reason }));
  } catch {
    if (!latest.isCurrent(token)) return;
    heading.textContent = "Results";
    grid.replaceChildren();
    filtered.hidden = true;
    status.textContent = "Search failed. Try again.";
  }
}

function setUrl(q, exclude) {
  const url = new URL(location.href);
  if (q) url.searchParams.set("q", q);
  else url.searchParams.delete("q");
  if (exclude.length) url.searchParams.set("x", exclude.join(","));
  else url.searchParams.delete("x");
  history.replaceState(null, "", url);
}

function submit(q) {
  const clean = q.trim();
  const exclude = [...selected];
  setUrl(clean, exclude);
  const token = latest.next();
  if (clean || exclude.length) runQuery(clean, exclude, token);
  else showSamples(token);
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  submit(input.value);
});

const examples = $("examples");
for (const q of EXAMPLES) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = q;
  b.addEventListener("click", () => { input.value = q; submit(q); });
  examples.appendChild(b);
}

if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
  let i = 0;
  setInterval(() => {
    i = (i + 1) % EXAMPLES.length;
    input.placeholder = EXAMPLES[i];
  }, 4000);
}

const params = new URL(location.href).searchParams;
const initial = params.get("q") || "";
for (const f of (params.get("x") || "").split(",")) if (TAG_FLAGS.includes(f)) selected.add(f);
syncTags();
input.value = initial;
submit(initial);
