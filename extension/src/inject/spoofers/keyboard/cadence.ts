/**
 * Keyboard Cadence Spoofer
 *
 * Typing rhythm/cadence is a behavioral fingerprint. This adds random
 * delays between keystrokes to normalize timing patterns.
 * Chameleon uses a minimum 30ms delay.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

export function initKeyboardCadenceSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  const minDelay = 30; // ms - Chameleon default
  const maxJitter = 15; // additional random jitter

  // Intercept keyboard events to normalize timing
  const keyEvents = new Set(['keydown', 'keyup', 'keypress']);
  let lastEventTime = 0;

  overrideMethod(EventTarget.prototype, 'addEventListener', (original, thisArg, args) => {
    const type = args[0] as string;
    let listener = args[1] as any;
    const options = args[2];

    if (keyEvents.has(type) && typeof listener === 'function') {
      logAccess('KeyboardEvent.timing', { spoofed: true, value: 'normalized' });
      const originalListener = listener;
      listener = function(this: any, event: Event) {
        const now = performance.now();
        const elapsed = now - lastEventTime;

        // If events come too fast, add the timestamp noise
        if (elapsed < minDelay && lastEventTime > 0) {
          const kbEvent = event as KeyboardEvent;
          Object.defineProperty(kbEvent, 'timeStamp', {
            value: lastEventTime + minDelay + (prng.nextFloat() * maxJitter),
            writable: false,
          });
        }

        lastEventTime = now;
        return originalListener.call(this, event);
      };
    }

    return original.call(thisArg, type, listener, options);
  });
}
