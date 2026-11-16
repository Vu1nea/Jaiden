import { renderConstellation, ALLERGEN_FLAGS } from "./constellation.js";

export function normalizeLink(link) {
  if (!link || !String(link).trim()) return null;
  const s = String(link).trim();
  return /^https?:\/\//i.test(s) ? s : `https://${s}`;
}

const label = (flag) => flag.replace(/_/g, " ");

function el(doc, tag, className, text) {
  const node = doc.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

export function renderCard(recipe, { dimmed = false, reason = null } = {}, doc = document) {
  const card = el(doc, "article", dimmed ? "card card--dimmed" : "card");

  const tile = el(doc, "div", "card__tile");
  tile.appendChild(renderConstellation(recipe, doc));
  card.appendChild(tile);

  const body = el(doc, "div", "card__body");
  body.appendChild(el(doc, "h3", "card__title", recipe.title));

  const meta = el(doc, "p", "card__meta");
  const why = recipe.why || { matched_terms: [], passed_filters: [] };
  const searched = why.matched_terms.length > 0 || why.passed_filters.length > 0;
  if (searched) meta.appendChild(el(doc, "span", "card__score", Number(recipe.score || 0).toFixed(2)));
  const href = normalizeLink(recipe.link);
  if (href) {
    const a = el(doc, "a", "card__link", `${recipe.source || "source"} ↗`);
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener";
    meta.appendChild(a);
  } else {
    meta.appendChild(el(doc, "span", "card__source", recipe.source || ""));
  }
  body.appendChild(meta);

  const flags = Object.keys(recipe.flags || {}).sort((a, b) => {
    const ia = ALLERGEN_FLAGS.includes(a) ? 0 : 1;
    const ib = ALLERGEN_FLAGS.includes(b) ? 0 : 1;
    return ia - ib || a.localeCompare(b);
  });
  if (flags.length) {
    const ul = el(doc, "ul", "card__flags");
    for (const f of flags) {
      ul.appendChild(el(doc, "li", ALLERGEN_FLAGS.includes(f) ? "chip chip--allergen" : "chip", label(f)));
    }
    body.appendChild(ul);
  }

  if (searched) {
    const parts = [];
    if (why.matched_terms.length) parts.push(`matched: ${why.matched_terms.join(", ")}`);
    if (why.passed_filters.length && !reason) parts.push(`passed: ${why.passed_filters.map(label).join(", ")}`);
    if (parts.length) body.appendChild(el(doc, "p", "card__why", parts.join(" · ")));
  }

  if (reason) {
    body.appendChild(el(doc, "p", "card__reason", `removed: "${reason.ingredient}" → ${label(reason.flag)}`));
  }

  card.appendChild(body);
  return card;
}
