/* Browser choices shown by about:cloakfox. This module is deliberately pure so
 * the catalog can be tested without a running Gecko process. */

const DEFINITIONS = Object.freeze([
  { id: "firefox", label: "Firefox", engine: "gecko" },
  { id: "chrome", label: "Chrome", engine: "chromium" },
  { id: "edge", label: "Edge", engine: "chromium" },
  { id: "chromium", label: "Chromium", engine: "chromium" },
  { id: "safari", label: "Safari", engine: "webkit" },
  { id: "custom", label: "Custom", engine: null },
]);

function major(value) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

export function listBrowserFamilies(capabilities = {}) {
  return DEFINITIONS.map(definition => {
    const capability = definition.engine ? capabilities[definition.engine] : null;
    const available = definition.id !== "custom";
    let unavailableReason = "";
    if (!available && definition.id === "custom") unavailableReason = "Use Advanced field overrides for a custom User-Agent.";
    return Object.freeze({ ...definition, available, unavailableReason });
  });
}

export function listBrowserVersions(family, capabilities = {}) {
  const definition = DEFINITIONS.find(item => item.id === family);
  if (!definition?.engine) return [];
  const current = major(capabilities[family]?.version || capabilities[definition.engine]?.version);
  if (!current) return [];
  // Firefox and Chromium-family majors ship frequently, so nine adjacent
  // releases stays useful without presenting very stale identities. Safari
  // majors span much longer periods and therefore use a smaller window.
  const releaseCount = definition.engine === "webkit" ? 3 : 9;
  return Object.freeze([
    ...Array.from({ length: releaseCount }, (_, offset) => Object.freeze({
      value: String(current - offset),
      label: offset === 0 ? `${current} (current)`
        : offset >= 4 ? `${current - offset} (older)` : String(current - offset),
      confidence: offset <= 2 ? "high" : "lower",
    })),
    Object.freeze({ value: "random-recent", label: "Random recent", confidence: "high" }),
  ]);
}

export function normalizeBrowserSelection(value, capabilities = {}) {
  const family = listBrowserFamilies(capabilities).find(item => item.id === value?.browser);
  if (!family?.available || !family.engine) return null;
  const version = listBrowserVersions(family.id, capabilities).find(item => item.value === String(value?.version));
  return version ? Object.freeze({ browser: family.id, version: version.value, engine: family.engine }) : null;
}

export const BROWSER_FAMILIES = DEFINITIONS;
