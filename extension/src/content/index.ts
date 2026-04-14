/**
 * Content script — ISOLATED world bridge.
 * Relays messages between MAIN world (inject scripts) and background.
 */

import { MSG } from '@/constants';

// Listen for messages from MAIN world (inject scripts)
window.addEventListener('message', (event) => {
  if (event.source !== window) return;

  const data = event.data;
  if (!data || typeof data.type !== 'string') return;

  switch (data.type) {
    case MSG.CLOAKFOX_ACTIVE:
      // Forward spoofing status to background
      browser.runtime.sendMessage({
        type: MSG.CLOAKFOX_ACTIVE,
        domain: data.domain,
      });
      break;

    case MSG.FINGERPRINT_ACCESS:
      // Forward fingerprint access notification to background
      browser.runtime.sendMessage({
        type: MSG.FINGERPRINT_ACCESS,
        category: data.category,
        api: data.api,
      });
      break;
  }
});

// Listen for messages from background → forward to MAIN world
browser.runtime.onMessage.addListener((message) => {
  if (message.type === MSG.STATUS) {
    window.postMessage(message, '*');
  }
});
