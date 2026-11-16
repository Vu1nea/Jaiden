import { test } from "node:test";
import assert from "node:assert/strict";
import { createLatest } from "../../web/latest.js";

test("only the newest token is current", () => {
  const latest = createLatest();
  const a = latest.next();
  const b = latest.next();
  assert.equal(latest.isCurrent(a), false);
  assert.equal(latest.isCurrent(b), true);
});
