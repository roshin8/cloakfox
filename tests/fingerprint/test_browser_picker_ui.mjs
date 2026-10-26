import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const root = new URL("../../additions/browser/components/cloakfox/content/", import.meta.url);
const html = readFileSync(new URL("settings.html", root), "utf8");
const css = readFileSync(new URL("settings.css", root), "utf8");
const js = readFileSync(new URL("settings.js", root), "utf8");

test("identity composer exposes accessible browser, version, OS and hardware controls", () => {
  for (const id of ["cfx-browser-families", "cfx-persona-version", "cfx-persona-filter", "cfx-persona-hardware", "cfx-profile-preview"])
    assert.match(html, new RegExp(`id=["']${id}["']`));
  assert.match(html, /Browser family/);
  assert.match(html, /Generate and apply/);
  assert.match(html, /Raw User-Agent remains available under Advanced field overrides/);
});

test("browser choices are catalog-driven and separate from engine selection", () => {
  assert.match(js, /listBrowserFamilies/);
  assert.match(js, /listBrowserVersions/);
  assert.match(js, /normalizeBrowserSelection/);
  assert.match(js, /unavailableReason/);
  assert.match(js, /persona_browser/);
  assert.match(js, /persona_version/);
});

test("picker has responsive, focus, selected, disabled, confidence and preview styling", () => {
  for (const token of ["browser-family-grid", "browser-family-tile", ":focus-visible", ".is-selected", ":disabled", "profile-confidence", "profile-preview"])
    assert.ok(css.includes(token), token);
  assert.match(css, /@media[^\{]*\(max-width:/);
});

test("hybrid layout keeps the focused editor and restores an all-controls view", () => {
  assert.match(js, /\[\["console", "Focused categories"\], \["grouped", "All controls"\]\]/);
  assert.match(js, /layout\.value === "grouped" \|\| category\.id === active/);
  assert.match(js, /label:"Persona & identity"[^\n]+"sec-screen-management"/);
  assert.doesNotMatch(js, /sec-screen-management"\)\.hidden = !chromium/);
});

test("identity utilities and experimental engine choice have clear structure", () => {
  for (const token of ["profile-tools", "cfx-profile-tools-title", "profile-disclosure-body", "profile-engine", "cfx-engine-title", "profile-engine-badge"])
    assert.ok(html.includes(token), token);
  assert.match(html, /Chromium switching is not available in this build/);
  assert.match(css, /\.profile-engine-control\s*\{[^}]*grid-template-columns/s);
  assert.match(css, /@media\(max-width:760px\)[\s\S]*\.profile-engine-control\{grid-template-columns:1fr/);
});

test("focused identity mode keeps the full browser field editor reachable", () => {
  assert.match(js, /id === "cfx-persona-panel" \? "Identity generator"/);
  assert.match(js, /id === "sec-identity" \? "Browser fields"/);
  assert.doesNotMatch(css, /body\[data-category="identity"\] \.settings-tabs\s*\{\s*display:none/);
  assert.match(js, /advanced\.open = wasOpen \?\? !Services\.prefs\.getBoolPref\("cloakfox\.ui\.collapse_advanced", false\)/);
  assert.match(js, /panels:\["cfx-persona-panel","sec-identity","cfx-font-settings","cfx-persona-similarity","sec-appearance","sec-screen-management","cfx-engine-settings","cfx-identity-maintenance","cfx-identity-help"\]/);
  assert.match(js, /id === "cfx-engine-settings" \? "Engine"/);
  assert.match(js, /id === "cfx-identity-help" \? "Help"/);
  assert.match(js, /id === "cfx-identity-maintenance" \? "Reset & data"/);
});

test("browser-specific settings follow the selected identity family", () => {
  assert.match(js, /cloakfox-browser-family-change/);
  assert.match(js, /id === "sec-appearance"\) return family === "firefox"/);
  assert.match(js, /id === "cfx-engine-settings" \|\| id === "sec-screen-management"/);
  assert.match(js, /\["chrome", "edge", "chromium"\]/);
});

test("desktop branding keeps its switch, status and actions in one control", () => {
  assert.match(html, /class="branding-control"[\s\S]*class="appearance-choice"[\s\S]*class="hero-actions"/);
  assert.doesNotMatch(html, /Choose the name and icon macOS shows for this browser/);
  assert.match(css, /#sec-appearance \.branding-control\s*\{[^}]*grid-template-columns:auto minmax\(260px,1fr\) auto auto[^}]*background:var\(--bg-elev-2\)/s);
  assert.match(css, /#sec-appearance \.appearance-switch\s*\{[^}]*grid-column:1/s);
});

test("focused mode uses evident tabs and keeps the active persona visible", () => {
  assert.match(js, /contextHeader\.append\(identitySummary, tabs\)/);
  assert.doesNotMatch(css, /data-category="identity"\]\s+\.current-persona-strip\s*\{\s*display:none/);
  assert.match(css, /focused-context-header > \.settings-tabs\s*\{[^}]*border-bottom:1px solid var\(--border\)/s);
  assert.match(css, /focused-context-header > \.settings-tabs button\s*\{[^}]*margin:0 -1px -1px 0[^}]*background:var\(--bg-elev-2\)/s);
  assert.match(css, /settings-tabs button\[aria-selected="true"\][^{]*\{[^}]*border-bottom-color:var\(--bg-elev\)[^}]*background:var\(--bg-elev\)[^}]*box-shadow:none/s);
  assert.match(css, /focused-context-header ~ \.settings-group:not\(\[hidden\]\)\s*\{[^}]*border-top:0[^}]*background:var\(--bg-elev\)/s);
  assert.match(css, /data-category="identity"\] #cfx-persona-panel\s*\{[^}]*background:var\(--bg-elev\)/s);
  assert.match(js, /browserLabel.*platform.*w.*h.*dpr.*hwc.*renderer/s);
});
