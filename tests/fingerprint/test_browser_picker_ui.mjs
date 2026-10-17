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
  assert.match(js, /label:"Display & graphics"[^\n]+"sec-screen-management"/);
  assert.doesNotMatch(js, /sec-screen-management"\)\.hidden = !chromium/);
});

test("identity utilities and experimental engine choice have clear structure", () => {
  for (const token of ["profile-tools", "cfx-profile-tools-title", "profile-disclosure-body", "profile-engine", "cfx-engine-title", "profile-engine-badge"])
    assert.ok(html.includes(token), token);
  assert.match(html, /Chromium switching is not available in this build/);
  assert.match(css, /\.profile-engine-control\s*\{[^}]*grid-template-columns/s);
  assert.match(css, /@media\(max-width:760px\)[\s\S]*\.profile-engine-control\{grid-template-columns:1fr/);
});
