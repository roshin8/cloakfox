/**
 * Inject entry point — MAIN world, document_start.
 *
 * Reads __CLOAKFOX__ config injected by background, calls the Cloakfox bridge
 * to configure C++ spoofing, then cleans up.
 */

import { configureCloakfoxSpoofing } from './cloakfox-bridge';
import { initFingerprintMonitor } from './monitor/fingerprint-monitor';
import { generateFallbackSeed } from '@/lib/crypto';
import { DEFAULT_SETTINGS } from '@/constants';
import type { CloakfoxWindow, CloakfoxConfig } from '@/types';
import { DEFAULT_PROFILE } from '@/lib/profiles/default';

const win = window as unknown as CloakfoxWindow;

(async () => {
  const domain = window.location.hostname;

  // Read config injected by background (via config-injector.ts)
  const config: CloakfoxConfig | undefined = win.__CLOAKFOX__;
  delete win.__CLOAKFOX__; // Prevent page access

  if (config) {
    await configureCloakfoxSpoofing(
      config.seed,
      config.domain,
      config.profile,
      config.settings
    );
  } else {
    // Fallback: domain-only seed (no container context available)
    const fallbackSeed = await generateFallbackSeed(domain);
    await configureCloakfoxSpoofing(
      fallbackSeed,
      domain,
      DEFAULT_PROFILE,
      DEFAULT_SETTINGS
    );
  }

  // Monitor fingerprint access attempts (for popup display)
  initFingerprintMonitor();

  // Notify content script that spoofing is active
  window.postMessage({ type: 'CLOAKFOX_ACTIVE', domain }, '*');
})();
