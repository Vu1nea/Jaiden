// Ingredient constellation: one dot per ingredient, placed deterministically
// from the recipe id. Orange = allergen, ink = clean, hollow = unlabeled.

export const ALLERGEN_FLAGS = ["tree_nut", "peanut", "dairy", "gluten", "egg", "soy", "fish", "shellfish", "sesame"];
const SVG_NS = "http://www.w3.org/2000/svg";
const PAD = 6;

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function dotKind(ingredient) {
  if (!ingredient.known) return "unknown";
  return ingredient.flags.some((f) => ALLERGEN_FLAGS.includes(f)) ? "allergen" : "clean";
}

// Jittered grid: shuffle cells, place each dot inside its own cell, so dots
// spread across the tile without piling up.
export function layoutDots(recipe) {
  const ings = recipe.ingredients || [];
  const n = ings.length;
  if (!n) return [];
  const rand = mulberry32((Number(recipe.id) || 0) * 2654435761 + 1);
  const cols = Math.ceil(Math.sqrt(n * 1.6));
  const rows = Math.ceil((n * 1.6) / cols);
  const cells = Array.from({ length: cols * rows }, (_, i) => i);
  for (let i = cells.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [cells[i], cells[j]] = [cells[j], cells[i]];
  }
  const cw = (100 - 2 * PAD) / cols;
  const ch = (100 - 2 * PAD) / rows;
  const maxR = Math.max(2.5, Math.min(5, Math.min(cw, ch) / 2.4));

  return ings.map((ing, i) => {
    const r = 2.5 + rand() * (maxR - 2.5);
    const col = cells[i] % cols;
    const row = Math.floor(cells[i] / cols);
    const clamp = (v) => Math.min(100 - r, Math.max(r, v));
    const x = clamp(PAD + col * cw + r + rand() * Math.max(0, cw - 2 * r));
    const y = clamp(PAD + row * ch + r + rand() * Math.max(0, ch - 2 * r));
    return { x, y, r, kind: dotKind(ing), name: ing.name, flags: ing.flags };
  });
}

export function renderConstellation(recipe, doc = document) {
  const svg = doc.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 100 100");
  svg.setAttribute("class", "constellation");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${(recipe.ingredients || []).length} ingredients`);
  for (const d of layoutDots(recipe)) {
    const c = doc.createElementNS(SVG_NS, "circle");
    c.setAttribute("cx", d.x.toFixed(2));
    c.setAttribute("cy", d.y.toFixed(2));
    c.setAttribute("r", d.r.toFixed(2));
    c.setAttribute("class", `dot dot--${d.kind}`);
    const title = doc.createElementNS(SVG_NS, "title");
    const label = d.kind === "unknown" ? "unknown" : d.flags.length ? d.flags.join(", ").replace(/_/g, " ") : "no flags";
    title.textContent = `${d.name} — ${label}`;
    c.appendChild(title);
    svg.appendChild(c);
  }
  return svg;
}
