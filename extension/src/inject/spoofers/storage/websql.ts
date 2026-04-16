/**
 * WebSQL (openDatabase) Spoofer
 *
 * WebSQL is deprecated but still used for fingerprinting.
 * Its availability varies across browsers.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize WebSQL spoofing
 */
export function initWebSQLSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Check if openDatabase exists
  if ('openDatabase' in window) {
    const originalOpenDatabase = (window as any).openDatabase;

    if (mode === 'block') {
      // Remove openDatabase to normalize fingerprint
      try {
        delete (window as any).openDatabase;
      } catch {
        try {
          (window as any).openDatabase = undefined;
        } catch {
          // Can't remove
        }
      }
    } else {
      // Wrap openDatabase to log access
      try {
        (window as any).openDatabase = function (
          name: string,
          version: string,
          displayName: string,
          estimatedSize: number,
          creationCallback?: (db: any) => void
        ): any {
          logAccess('openDatabase', { spoofed: true, value: 'blocked' });
          return originalOpenDatabase.call(
            window,
            name,
            version,
            displayName,
            estimatedSize,
            creationCallback
          );
        };
      } catch {
        // Can't override
      }
    }

  } else {
    // openDatabase doesn't exist - no action needed for blocking
    // For noise mode, we could add a fake one, but it's deprecated so probably not worth it
  }
}
