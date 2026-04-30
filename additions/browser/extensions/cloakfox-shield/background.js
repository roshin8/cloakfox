/* Cloakfox-shield background script.
 *
 * Minimal — its only job is to ensure the cloakfox experiment API
 * gets registered at startup. Built-in addons in Firefox load their
 * experiment_apis lazily; without a persistent background page that
 * touches browser.cloakfox, the popup can't see it on first open.
 *
 * Touching browser.cloakfox here forces Firefox to instantiate the
 * API (parent script + schema) so the popup can use it immediately.
 */

(function init() {
  // Touch the experiment API so it gets registered + the parent
  // script loads. The actual return value doesn't matter.
  if (browser.cloakfox && typeof browser.cloakfox.getEnabled === "function") {
    browser.cloakfox.getEnabled().catch(() => {});
  }
})();
