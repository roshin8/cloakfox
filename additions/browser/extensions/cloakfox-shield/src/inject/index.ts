/**
 * Inject Script — runs in the page MAIN world at document_start.
 *
 * In the stealth architecture (see content/index.ts for the other half):
 * the ISOLATED-world content script calls all Cloakfox WebIDL setters
 * (which are Func-gated to the cloakfox-shield extension principal and
 * invisible from MAIN) and writes a bridge attribute onto
 * document.documentElement containing the deterministic config plus the
 * set of signals C++ already handled. This script reads that attribute
 * and REMOVES it synchronously — by the time any page <script> tag runs
 * the attribute is gone. No sessionStorage, no window globals, no
 * postMessage, no CustomEvent. Nothing page-observable persists.
 *
 * We still run JS-level fallback spoofers here (prototype overrides on
 * navigator.*, screen.*, WebGLRenderingContext.prototype.*, etc.) for
 * any signals C++ didn't handle. The handled set from the bridge gates
 * them so C++ values are never overridden.
 *
 * Fallback path: if the bridge attribute is missing (e.g. the content
 * script didn't run for some reason — different run_at, extension
 * disabled, etc.) we regenerate the config locally and run spoofers
 * without the pre-handled set. Today that means JS does everything
 * visible to the page, which is worse than the cross-world split but
 * better than doing nothing.
 */

import { initStealth } from '@/lib/stealth';
import { initializeSpoofers } from './spoofers';
import { initFingerprintMonitor } from './monitor/fingerprint-monitor';
import { buildWorkerPreamble } from './spoofers/workers/worker-fingerprint';
import { generateConfig } from '@/lib/boot-config';
import type { InjectConfig, SpooferSettings } from '@/types';

// Patch Function.prototype.toString FIRST — before any spoofers
initStealth();

const BRIDGE_ATTR = 'data-cfx-boot';

function allSpoofersDisabled(settings: SpooferSettings): boolean {
  for (const category of Object.values(settings)) {
    for (const value of Object.values(category)) {
      if (value !== 'off') return false;
    }
  }
  return true;
}

// Try to read the bridge. ISOLATED content script populated it earlier
// on this same navigation (manifest orders content/ before inject/).
let config: InjectConfig;
let preCoreHandled: Set<string> | undefined;

const bridgeRaw = document.documentElement.getAttribute(BRIDGE_ATTR);
if (bridgeRaw) {
  // Synchronous read + remove — attribute is gone before page scripts run.
  document.documentElement.removeAttribute(BRIDGE_ATTR);
  try {
    const parsed = JSON.parse(bridgeRaw) as { config: InjectConfig; handled: string[] };
    config = parsed.config;
    preCoreHandled = new Set(parsed.handled);
  } catch {
    // Malformed bridge payload — fall through to local config.
    config = generateConfig(window.location.hostname || 'unknown', navigator.platform || '');
  }
} else {
  // No bridge; content script didn't run. Regenerate locally so JS
  // spoofers still fire (no C++ skip gating — JS will do everything).
  config = generateConfig(window.location.hostname || 'unknown', navigator.platform || '');
}

if (allSpoofersDisabled(config.settings)) {
  initFingerprintMonitor();
} else {
  initializeSpoofers(config, preCoreHandled);
}

// Post the generated profile to the content script (ISOLATED world)
// so the popup can display the actual spoofed values.
try {
  const workerPreamble = buildWorkerPreamble(config.assignedProfile);
  window.postMessage({
    type: 'CONTAINER_SHIELD_ACTIVE_PROFILE',
    profile: config.assignedProfile,
    domain: config.domain,
    workerPreamble,
  }, '*');
} catch {}
