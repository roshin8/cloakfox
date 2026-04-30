/* Cloakfox popup — tab-aware indicator with live persona preview and
 * one-click regenerate.
 *
 * Pref reads / writes go through a chrome bridge: the popup posts
 * runtime messages, and the resource://gre/modules/CloakfoxBridge
 * JSWindowActor parent (registered in actors-registration patch)
 * runs them with chrome authority and returns results. Without that
 * bridge, the popup can only see what extension WebExtensions APIs
 * expose — which doesn't include cloakfox prefs.
 *
 * Fallback: if the bridge isn't reachable (e.g. older builds without
 * the parent actor), we still show tab/container info and the
 * "Open full settings" deep-link works on its own.
 */

(async function init() {
  const statusEl     = document.getElementById("cfx-status");
  const containerEl  = document.getElementById("cfx-container");
  const urlEl        = document.getElementById("cfx-url");
  const personaEl    = document.getElementById("cfx-persona-preview");
  const seedTagEl    = document.getElementById("cfx-seed-tag");
  const regenBtn     = document.getElementById("cfx-popup-regen");
  const settingsBtn  = document.getElementById("cfx-open-settings");
  const errBox       = document.getElementById("cfx-popup-err");

  function showError(msg) {
    if (errBox) {
      errBox.hidden = false;
      errBox.textContent = msg;
    }
  }

  // ── Tab + container resolution ────────────────────────────────
  let tab = null;
  try {
    const tabs = await browser.tabs.query({ active: true, currentWindow: true });
    tab = tabs[0];
  } catch (_e) { /* fall through */ }

  if (!tab) {
    statusEl.textContent = "—";
    containerEl.textContent = "(no active tab)";
    urlEl.textContent = "—";
    settingsBtn.disabled = true;
    if (regenBtn) regenBtn.disabled = true;
    return;
  }

  try {
    urlEl.textContent = new URL(tab.url).host || tab.url;
  } catch (_e) {
    urlEl.textContent = tab.url || "—";
  }

  let ucid = 0;
  let containerName = "Default";
  const csid = tab.cookieStoreId || "";
  const m = /^firefox-container-(\d+)$/.exec(csid);
  if (m) {
    ucid = parseInt(m[1], 10);
    try {
      const ident = await browser.contextualIdentities.get(csid);
      containerName = ident?.name || `Container ${ucid}`;
    } catch (_e) { containerName = `Container ${ucid}`; }
  }
  containerEl.textContent = containerName;

  // ── Live persona preview via chrome bridge ────────────────────
  // The bridge is implemented as a parent-process listener in
  // CloakfoxPopupBridge.sys.mjs that receives "Cloakfox:Get" /
  // "Cloakfox:Regen" messages. Browser.runtime.sendMessage sends to
  // the extension's own background, which doesn't help — we need a
  // privileged bridge. Use browser.runtime.sendNativeMessage if
  // available, else fall back to the deep-link only.
  async function callBridge(action, payload = {}) {
    // Try via runtime message to "experiments:cloakfox" — the
    // CloakfoxExperiment WebExtensions API (registered in manifest
    // experimental_apis) exposes browser.cloakfox.* methods.
    if (browser.cloakfox && typeof browser.cloakfox[action] === "function") {
      return await browser.cloakfox[action](payload);
    }
    throw new Error("Cloakfox bridge unavailable");
  }

  async function refreshPersona() {
    try {
      const data = await callBridge("getCloakCfg", { ucid });
      if (!data || !data.cfg) {
        personaEl.textContent = "(not yet generated)";
        seedTagEl.textContent = "";
        return;
      }
      const c = data.cfg;
      const platform = c["navigator.platform"] || "?";
      const w = c["screen.width"] ?? "?";
      const h = c["screen.height"] ?? "?";
      const hwc = c["navigator.hardwareConcurrency"] ?? "?";
      const renderer = (c["webGl:renderer"] || "?").slice(0, 32);
      personaEl.textContent = `${platform} · ${w}×${h} · ${hwc}c · ${renderer}`;
      seedTagEl.textContent = data.tag || "";
    } catch (e) {
      personaEl.textContent = "(bridge unavailable — open full settings)";
      seedTagEl.textContent = "";
      if (regenBtn) regenBtn.disabled = true;
    }
  }
  await refreshPersona();

  // ── Status pill ───────────────────────────────────────────────
  try {
    const data = await callBridge("getEnabled");
    const on = !!(data && data.enabled);
    statusEl.textContent = on ? "active" : "off";
    statusEl.classList.toggle("on", on);
    statusEl.classList.toggle("off", !on);
  } catch (_e) {
    // No bridge — show generic active tag (the extension is loaded so
    // Cloakfox is at least running).
    statusEl.textContent = "active";
    statusEl.classList.add("on");
  }

  // ── Regenerate button ─────────────────────────────────────────
  if (regenBtn) {
    regenBtn.addEventListener("click", async () => {
      regenBtn.disabled = true;
      regenBtn.textContent = "Rolling…";
      try {
        await callBridge("regeneratePersona", { ucid });
        await refreshPersona();
        regenBtn.textContent = "✓ Rolled";
        setTimeout(() => {
          regenBtn.textContent = "New persona";
          regenBtn.disabled = false;
        }, 1100);
      } catch (e) {
        regenBtn.textContent = "New persona";
        regenBtn.disabled = false;
        showError("Regenerate failed: " + e.message);
      }
    });
  }

  // ── Open full settings ────────────────────────────────────────
  // Tries three paths in order:
  //   1. browser.cloakfox.openSettings (chrome bridge — works once
  //      the experiment_apis registration succeeds)
  //   2. browser.tabs.create (works once the AboutRedirector C++
  //      flag fix lands via CI rebuild)
  //   3. Clipboard fallback — copy the URL so the user can paste it
  //      into the URL bar one keystroke away.
  settingsBtn.addEventListener("click", async () => {
    const url = `about:cloakfox?ucid=${ucid}`;
    try {
      await callBridge("openSettings", { ucid });
      window.close();
      return;
    } catch (_e1) { /* fall through */ }
    try {
      await browser.tabs.create({ url });
      window.close();
      return;
    } catch (_e2) { /* fall through */ }
    // Last-resort fallback — copy URL + tell the user to paste.
    try {
      await navigator.clipboard.writeText(url);
      showError(`URL copied — paste in URL bar to open settings: ${url}`);
    } catch (_e3) {
      showError(`Type ${url} in the URL bar to open settings.`);
    }
  });
})();
