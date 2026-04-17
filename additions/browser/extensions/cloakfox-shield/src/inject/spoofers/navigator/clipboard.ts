/**
 * Clipboard API Spoofer
 *
 * Spoofs navigator.clipboard to prevent fingerprinting via clipboard access patterns.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize Clipboard API spoofing
 */
export function initClipboardSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  if (!navigator.clipboard) return;

  const originalClipboard = navigator.clipboard;

  const spoofedClipboard = {
    readText: async function (): Promise<string> {
      logAccess('navigator.clipboard.readText', { spoofed: true, blocked: mode === 'block', value: 'blocked' });

      if (mode === 'block') {
        throw new DOMException('Clipboard read denied', 'NotAllowedError');
      }

      return originalClipboard.readText();
    },

    read: async function (): Promise<ClipboardItems> {
      logAccess('navigator.clipboard.read', { spoofed: true, blocked: mode === 'block', value: 'blocked' });

      if (mode === 'block') {
        throw new DOMException('Clipboard read denied', 'NotAllowedError');
      }

      return originalClipboard.read();
    },

    writeText: async function (text: string): Promise<void> {
      logAccess('navigator.clipboard.writeText', { spoofed: true, blocked: mode === 'block', value: 'blocked' });

      if (mode === 'block') {
        throw new DOMException('Clipboard write denied', 'NotAllowedError');
      }

      return originalClipboard.writeText(text);
    },

    write: async function (data: ClipboardItems): Promise<void> {
      logAccess('navigator.clipboard.write', { spoofed: true, blocked: mode === 'block', value: 'blocked' });

      if (mode === 'block') {
        throw new DOMException('Clipboard write denied', 'NotAllowedError');
      }

      return originalClipboard.write(data);
    },
  };

  // Replace navigator.clipboard
  try {
    Object.defineProperty(navigator, 'clipboard', {
      get: function () {
        logAccess('navigator.clipboard', { spoofed: true, value: 'blocked' });
        return spoofedClipboard;
      },
      configurable: true,
    });
  } catch {
    // Can't override
  }

}
