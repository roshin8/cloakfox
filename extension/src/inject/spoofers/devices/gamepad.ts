/**
 * Gamepad API Spoofer
 *
 * Connected gamepads can be enumerated and used for fingerprinting.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize Gamepad API spoofing
 */
export function initGamepadSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Spoof navigator.getGamepads()
  if ('getGamepads' in navigator) {
    const originalGetGamepads = navigator.getGamepads.bind(navigator);

    navigator.getGamepads = function (): (Gamepad | null)[] {
      logAccess('navigator.getGamepads', { spoofed: mode !== 'block' });

      if (mode === 'block') {
        return [null, null, null, null]; // Standard 4-slot array with no gamepads
      }

      return originalGetGamepads();
    };
  }

  // Block gamepadconnected events
  if (mode === 'block') {
    const originalAddEventListener = window.addEventListener;

    window.addEventListener = function (
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | AddEventListenerOptions
    ) {
      if (type === 'gamepadconnected' || type === 'gamepaddisconnected') {
        logAccess(`window.addEventListener(${type})`, { blocked: true });
        return; // Don't register the listener
      }

      return originalAddEventListener.call(window, type, listener, options);
    };
  }

}
