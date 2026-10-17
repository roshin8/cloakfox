import test from "node:test";
import assert from "node:assert/strict";

import {
  listBrowserFamilies,
  listBrowserVersions,
  normalizeBrowserSelection,
} from "../../additions/browser/components/cloakfox/CloakfoxBrowserProfiles.sys.mjs";

const capabilities = Object.freeze({
  gecko: { available: true, version: "158.0" },
  chromium: { available: false, version: "154.0" },
  webkit: { available: false, version: "26.0" },
});

test("identity families stay selectable independently from the active engine", () => {
  const families = listBrowserFamilies(capabilities);
  assert.deepEqual(families.map(item => item.id), ["firefox", "chrome", "edge", "chromium", "safari", "custom"]);
  assert.equal(families.find(item => item.id === "firefox").available, true);
  for (const id of ["firefox", "chrome", "edge", "chromium", "safari"])
    assert.equal(families.find(item => item.id === id).available, true);
  assert.equal(families.find(item => item.id === "custom").available, false);
});

test("Firefox versions include current through minus three and random recent", () => {
  const versions = listBrowserVersions("firefox", capabilities);
  assert.deepEqual(versions.map(item => item.value), ["158", "157", "156", "155", "random-recent"]);
  assert.deepEqual(versions.slice(0, 3).map(item => item.confidence), ["high", "high", "high"]);
  assert.equal(versions[3].confidence, "lower");
});

test("normalization rejects stale or unsupported selections without guessing", () => {
  assert.deepEqual(normalizeBrowserSelection({ browser: "firefox", version: "157" }, capabilities),
    { browser: "firefox", version: "157", engine: "gecko" });
  assert.deepEqual(normalizeBrowserSelection({ browser: "chrome", version: "154" }, capabilities),
    { browser: "chrome", version: "154", engine: "chromium" });
  assert.equal(normalizeBrowserSelection({ browser: "firefox", version: "98" }, capabilities), null);
});
