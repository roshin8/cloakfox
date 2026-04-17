/**
 * MIDI API Spoofer
 *
 * MIDI device enumeration can be used for fingerprinting.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize MIDI API spoofing
 */
export function initMIDISpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Spoof navigator.requestMIDIAccess
  if ('requestMIDIAccess' in navigator) {
    const originalRequestMIDIAccess = (navigator as any).requestMIDIAccess.bind(navigator);

    (navigator as any).requestMIDIAccess = async function (
      options?: MIDIOptions
    ): Promise<MIDIAccess> {
      logAccess('navigator.requestMIDIAccess', { spoofed: mode !== 'block' });

      if (mode === 'block') {
        // Reject with a permission denied error
        throw new DOMException('Permission denied', 'NotAllowedError');
      }

      const access = await originalRequestMIDIAccess(options);

      // Return access but log any device enumeration
      return new Proxy(access, {
        get(target, prop) {
          if (prop === 'inputs' || prop === 'outputs') {
            logAccess(`MIDIAccess.${String(prop)}`, { spoofed: true });
          }
          const value = (target as any)[prop];
          if (typeof value === 'function') {
            return value.bind(target);
          }
          return value;
        },
      });
    };
  }

}
