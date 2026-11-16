import { test } from "node:test";
import assert from "node:assert/strict";
import { renderCard } from "../../web/card.js";

// Minimal DOM stub: enough for renderCard/renderConstellation.
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this._text = ""; this.className = ""; }
  appendChild(c) { this.children.push(c); return c; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); }
  set innerHTML(_) { throw new Error("innerHTML must not be used"); }
  all() { return [this, ...this.children.flatMap((c) => c.all())]; }
  find(cls) { return this.all().find((n) => (n.className || n.attrs.class || "").split(" ").includes(cls)); }
}
const doc = { createElement: (t) => new Node(t), createElementNS: (_, t) => new Node(t) };
const ing = (name, flags = [], known = true) => ({ raw: name, name, flags, known });
const base = {
  id: 1, title: "Pork Dumplings", link: "www.x.com/a", source: "Gathered",
  ingredients: [ing("ground pork", ["meat", "pork"]), ing("peanut oil", ["peanut"])],
  flags: { pork: 1, peanut: 1, meat: 1 }, score: 0.5,
  why: { matched_terms: ["dumplings"], passed_filters: ["dairy"] },
};

test("title is text, not markup", () => {
  const card = renderCard({ ...base, title: "<img src=x onerror=alert(1)>" }, {}, doc);
  assert.equal(card.find("card__title").textContent, "<img src=x onerror=alert(1)>");
});

test("why line and score", () => {
  const card = renderCard(base, {}, doc);
  assert.equal(card.find("card__score").textContent, "0.50");
  assert.equal(card.find("card__why").textContent, "matched: dumplings · passed: dairy");
});

test("allergen chips first", () => {
  const chips = renderCard(base, {}, doc).find("card__flags").children.map((c) => c.textContent);
  assert.deepEqual(chips, ["peanut", "meat", "pork"]);
});

test("filtered card shows reason and is dimmed", () => {
  const card = renderCard(base, { dimmed: true, reason: { ingredient: "peanut oil", flag: "peanut" } }, doc);
  assert.ok(card.className.includes("card--dimmed"));
  assert.equal(card.find("card__reason").textContent, 'removed: "peanut oil" → peanut');
});

test("link attributes", () => {
  const a = renderCard(base, {}, doc).find("card__link");
  assert.equal(a.href, "https://www.x.com/a");
  assert.equal(a.rel, "noopener");
  assert.equal(a.target, "_blank");
});

test("sample card hides score and why", () => {
  const card = renderCard({ ...base, why: { matched_terms: [], passed_filters: [] } }, {}, doc);
  assert.equal(card.find("card__score"), undefined);
  assert.equal(card.find("card__why"), undefined);
});
