import { fetchSearch, fetchSamples, parseQuery } from "./mock-api.js";
import { renderCard } from "./card.js";

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

async function showSamples() {
  parsed.hidden = true;
  heading.textContent = "Sample recipes";
  status.textContent = "";
  filtered.hidden = true;
  try {
    renderGrid(grid, await fetchSamples(12));
  } catch {
    grid.replaceChildren();
    status.textContent = "Couldn't load sample recipes. Try reloading.";
  }
}

async function runQuery(q) {
  renderParsed(parseQuery(q));
  status.textContent = "Searching…";
  try {
    const res = await fetchSearch(q);
    renderParsed(res.query);
    const n = res.results.length;
    heading.textContent = `${n} result${n === 1 ? "" : "s"}`;
    status.textContent = n ? "" : "No recipes matched. Check the filtered-out list below.";
    renderGrid(grid, res.results);

    const m = res.filtered_out.length;
    filtered.hidden = m === 0;
    filteredLabel.textContent = `Filtered out (${m})`;
    renderGrid(filteredGrid, res.filtered_out, (r) => ({ dimmed: true, reason: r.reason }));
  } catch {
    heading.textContent = "Results";
    grid.replaceChildren();
    filtered.hidden = true;
    status.textContent = "Search failed. Try again.";
  }
}

function setUrl(q) {
  const url = new URL(location.href);
  if (q) url.searchParams.set("q", q);
  else url.searchParams.delete("q");
  history.replaceState(null, "", url);
}

function submit(q) {
  const clean = q.trim();
  setUrl(clean);
  if (clean) runQuery(clean);
  else showSamples();
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

const initial = new URL(location.href).searchParams.get("q") || "";
input.value = initial;
submit(initial);
