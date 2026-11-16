import { test } from "node:test";
import assert from "node:assert/strict";
import { layoutDots, ALLERGEN_FLAGS } from "../../web/constellation.js";
import { normalizeLink } from "../../web/card.js";

const ing = (name, flags = [], known = true) => ({ raw: name, name, flags, known });

test("allergen flag list", () => {
  assert.deepEqual(ALLERGEN_FLAGS,
    ["tree_nut", "peanut", "dairy", "gluten", "egg", "soy", "fish", "shellfish", "sesame"]);
});

test("layout is stable per recipe id and differs between ids", () => {
  const ings = [ing("milk", ["dairy"]), ing("salt"), ing("onion")];
  assert.deepEqual(layoutDots({ id: 7, ingredients: ings }), layoutDots({ id: 7, ingredients: ings }));
  assert.notDeepEqual(layoutDots({ id: 7, ingredients: ings }), layoutDots({ id: 8, ingredients: ings }));
});

test("dot kinds: allergen, clean, unknown", () => {
  const d = layoutDots({ id: 1, ingredients: [ing("milk", ["dairy"]), ing("beef", ["meat", "beef"]), ing("zaatar", [], false)] });
  assert.deepEqual(d.map((x) => x.kind), ["allergen", "clean", "unknown"]);
  assert.equal(d[0].name, "milk");
});

test("0 and 60 ingredients stay in bounds", () => {
  assert.equal(layoutDots({ id: 2, ingredients: [] }).length, 0);
  const d = layoutDots({ id: 3, ingredients: Array.from({ length: 60 }, (_, i) => ing("x" + i)) });
  assert.equal(d.length, 60);
  for (const p of d) {
    assert.ok(p.r >= 2.5 && p.r <= 5);
    assert.ok(p.x >= p.r && p.x <= 100 - p.r && p.y >= p.r && p.y <= 100 - p.r);
  }
});

test("normalizeLink", () => {
  assert.equal(normalizeLink("www.cookbooks.com/a"), "https://www.cookbooks.com/a");
  assert.equal(normalizeLink("http://x.com"), "http://x.com");
  assert.equal(normalizeLink(""), null);
  assert.equal(normalizeLink(undefined), null);
});
