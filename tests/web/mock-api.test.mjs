import { test } from "node:test";
import assert from "node:assert/strict";
import { parseQuery, runSearch, fetchSearch } from "../../web/mock-api.js";

const ing = (name, flags = [], known = true) => ({ raw: name, name, flags, known });
const recipe = (id, title, ingredients) => ({ id, title, link: "", source: "test", ingredients, flags: {} });

test("parseQuery: without peanut oil", () => {
  assert.deepEqual(parseQuery("dim sum without peanut oil"),
    { raw: "dim sum without peanut oil", semantic: "dim sum", exclude: ["peanut"], include: [] });
});

test("parseQuery: multiple no clauses", () => {
  const q = parseQuery("high-protein dinner, no dairy, no nuts");
  assert.equal(q.semantic, "high-protein dinner");
  assert.deepEqual(q.exclude, ["dairy", "tree_nut", "peanut"]);
});

test("parseQuery: free of and -free", () => {
  assert.deepEqual(parseQuery("cookies free of egg").exclude, ["egg"]);
  assert.deepEqual(parseQuery("gluten-free bread").exclude, ["gluten"]);
  assert.equal(parseQuery("gluten-free bread").semantic, "bread");
});

test("parseQuery: plain query untouched", () => {
  assert.deepEqual(parseQuery("spicy ground beef skillet meal"),
    { raw: "spicy ground beef skillet meal", semantic: "spicy ground beef skillet meal", exclude: [], include: [] });
});

const DUMPLINGS = [
  recipe(1, "Pork Dumplings", [ing("ground pork", ["meat", "pork"]), ing("ginger")]),
  recipe(2, "Peanut Dumplings", [ing("ground pork", ["meat", "pork"]), ing("peanut oil", ["peanut"])]),
];

test("runSearch: peanut recipe filtered with reason", () => {
  const r = runSearch("dumplings without peanut oil", DUMPLINGS);
  assert.deepEqual(r.results.map((x) => x.id), [1]);
  assert.equal(r.filtered_out.length, 1);
  assert.deepEqual(r.filtered_out[0].reason, { ingredient: "peanut oil", flag: "peanut" });
  assert.deepEqual(r.results[0].why, { matched_terms: ["dumplings"], passed_filters: ["peanut"] });
  assert.equal(r.results[0].score, 1);
});

const FLAT = [recipe(3, "Zaatar Flatbread", [ing("pita", ["gluten"]), ing("zaatar", [], false)])];

test("runSearch: unknown ingredient only filtered when excluding", () => {
  assert.deepEqual(runSearch("flatbread", FLAT).results.map((x) => x.id), [3]);
  const r = runSearch("flatbread no dairy", FLAT);
  assert.equal(r.results.length, 0);
  assert.deepEqual(r.filtered_out[0].reason, { ingredient: "zaatar", flag: "unknown" });
});

test("runSearch: exclusion-only query returns all passing sorted by title", () => {
  const recipes = [
    recipe(5, "Zucchini Bake", [ing("zucchini")]),
    recipe(6, "Cheese Toast", [ing("cheddar cheese", ["dairy"])]),
    recipe(7, "Apple Crisp", [ing("apples")]),
  ];
  const r = runSearch("no dairy", recipes);
  assert.deepEqual(r.results.map((x) => x.title), ["Apple Crisp", "Zucchini Bake"]);
  assert.ok(r.results.every((x) => x.score === 0));
});

test("runSearch: unmapped exclusion filters by ingredient name", () => {
  const recipes = [recipe(8, "Tomato Salsa", [ing("tomatoes"), ing("fresh cilantro")])];
  const r = runSearch("salsa without cilantro", recipes);
  assert.deepEqual(r.filtered_out[0].reason, { ingredient: "fresh cilantro", flag: "ingredient" });
});

test("runSearch: results sorted by score and k limits", () => {
  const recipes = [
    recipe(9, "Beef Stew", [ing("beef")]),
    recipe(10, "Spicy Beef Skillet", [ing("beef")]),
    recipe(11, "Tea", [ing("tea")]),
  ];
  const r = runSearch("spicy beef skillet", recipes);
  assert.deepEqual(r.results.map((x) => x.id), [10, 9]);
  assert.equal(runSearch("spicy beef skillet", recipes, 1).results.length, 1);
});

test("fetchSearch: blank query rejects", async () => {
  await assert.rejects(fetchSearch("   "), /empty query/);
});

// --- final-review fixes ---
import { readFileSync } from "node:fs";
const MOCK = JSON.parse(readFileSync(new URL("../../web/mock/recipes.json", import.meta.url), "utf8"));

test("parseQuery: trailing punctuation and brackets keep exclusion", () => {
  assert.deepEqual(parseQuery("pasta without dairy.").exclude, ["dairy"]);
  assert.equal(parseQuery("pasta without dairy.").semantic, "pasta");
  assert.deepEqual(parseQuery("pasta, no dairy!").exclude, ["dairy"]);
  assert.deepEqual(parseQuery("pasta (no dairy)").exclude, ["dairy"]);
  assert.equal(parseQuery("pasta (no dairy)").semantic, "pasta");
});

test("parseQuery: w/o", () => {
  const q = parseQuery("pasta w/o cheese");
  assert.equal(q.semantic, "pasta");
  assert.deepEqual(q.exclude, ["dairy"]);
});

test("parseQuery: and/or conjunctions", () => {
  assert.deepEqual(parseQuery("no nuts and no dairy"), { raw: "no nuts and no dairy", semantic: "", exclude: ["tree_nut", "peanut", "dairy"], include: [] });
  assert.deepEqual(parseQuery("without eggs or milk").exclude, ["egg", "dairy"]);
  assert.deepEqual(parseQuery("no dairy and nuts").exclude, ["dairy", "tree_nut", "peanut"]);
  assert.deepEqual(parseQuery("pasta without peanuts or tree nuts").exclude, ["peanut", "tree_nut"]);
});

test("runSearch: stopwords are not search tokens", () => {
  const recipes = [recipe(20, "Pork and Ginger Dumplings", [ing("ginger")]), recipe(21, "Apple Crisp", [ing("apples")])];
  assert.deepEqual(runSearch("no nuts and no dairy", recipes).results.map((x) => x.id).sort(), [20, 21]);
});

test("every built-in example query returns at least one result", () => {
  for (const q of ["spicy ground beef skillet meal", "dim sum without peanut oil", "high-protein dinner, no dairy, no nuts"]) {
    assert.ok(runSearch(q, MOCK).results.length > 0, q);
  }
});

test("mock data: oats carry gluten (union of case-variant labels)", () => {
  const oats = MOCK.flatMap((r) => r.ingredients).find((i) => i.name === "oats");
  assert.ok(oats.flags.includes("gluten"));
  assert.equal(runSearch("gluten-free breakfast bars", MOCK).results.some((r) => r.title.includes("Oat")), false);
});
