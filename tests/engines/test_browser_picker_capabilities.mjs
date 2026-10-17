import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const settings = readFileSync(new URL("../../additions/browser/components/cloakfox/content/settings.js", import.meta.url), "utf8");

test("identity version catalog is independent from the engine switch", () => {
  const block = settings.match(/const browserCapabilities = \(\) => Object\.freeze\(\{[\s\S]*?\n\}\);/)?.[0] || "";
  assert.match(block, /gecko: Object\.freeze\(\{ available: true/);
  assert.match(block, /chromium: Object\.freeze\(\{ available: true/);
  assert.match(block, /webkit: Object\.freeze\(\{ available: true/);
  assert.doesNotMatch(block, /Services\.prefs/);
});

test("identity apply validates the catalog without changing the engine", () => {
  assert.match(settings, /normalizeBrowserSelection\(\{ browser, version \}, browserCapabilities\(\)\)/);
  assert.doesNotMatch(settings, /engine_host\.test\.enabled/);
});
