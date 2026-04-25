/* Cloakfox popup — tab-aware indicator. Vanilla MV3, no React, no
 * bundler. Only job: show what container the user's current tab is
 * in and deep-link into about:cloakfox?ucid=<N> for that container.
 *
 * Cannot read chrome prefs (cloakfox.enabled, cloakfox.s.cloak_cfg_N
 * etc.) directly — extensions don't have that privilege. The status
 * field stays generic ("Cloakfox active") rather than reflecting per-
 * container seed state. The full settings page is one click away
 * if the user wants details.
 */

(async function init() {
  const statusEl     = document.getElementById("cfx-status");
  const containerEl  = document.getElementById("cfx-container");
  const urlEl        = document.getElementById("cfx-url");
  const settingsBtn  = document.getElementById("cfx-open-settings");

  // Get the active tab in the current window. Both Manifest V3 and
  // Firefox WebExtensions support this without host permissions.
  let tab = null;
  try {
    const tabs = await browser.tabs.query({ active: true, currentWindow: true });
    tab = tabs[0];
  } catch (_e) { /* fall through to "—" */ }

  if (!tab) {
    statusEl.textContent = "—";
    containerEl.textContent = "(no active tab)";
    urlEl.textContent = "—";
    settingsBtn.disabled = true;
    return;
  }

  // Display the URL (host only — full URL would overflow).
  try {
    const u = new URL(tab.url);
    urlEl.textContent = u.host || u.protocol;
  } catch (_e) {
    urlEl.textContent = tab.url || "—";
  }

  // Resolve the container. Firefox's cookieStoreId is "firefox-default"
  // for the default container or "firefox-container-N" for a named
  // container, where N is the userContextId.
  let ucid = 0;
  let containerName = "Default (no container)";
  const csid = tab.cookieStoreId || "";
  const m = /^firefox-container-(\d+)$/.exec(csid);
  if (m) {
    ucid = parseInt(m[1], 10);
    try {
      const ident = await browser.contextualIdentities.get(csid);
      containerName = ident?.name || `Container ${ucid}`;
    } catch (_e) {
      containerName = `Container ${ucid}`;
    }
  }
  containerEl.textContent = containerName;

  // Status — best-effort. We don't have access to chrome prefs from
  // the extension, so we display a generic "active" tag rather than
  // reading cloakfox.enabled. If a future Experiment API is added,
  // this can read the real state.
  statusEl.textContent = "active";
  statusEl.classList.add("on");

  // Hook the settings button to deep-link with ?ucid=<N>.
  settingsBtn.addEventListener("click", async () => {
    await browser.tabs.create({ url: `about:cloakfox?ucid=${ucid}` });
    window.close();
  });
})();
