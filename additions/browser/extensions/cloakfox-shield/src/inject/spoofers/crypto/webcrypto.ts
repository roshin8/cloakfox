/**
 * WebCrypto Spoofer
 *
 * The Web Cryptography API can reveal information about
 * crypto implementation and hardware support.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize WebCrypto spoofing
 */
export function initCryptoSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  if (typeof crypto === 'undefined' || !crypto.subtle) return;

  // Spoof getRandomValues timing (can be used for entropy fingerprinting)
  const originalGetRandomValues = crypto.getRandomValues.bind(crypto);

  crypto.getRandomValues = function <T extends ArrayBufferView | null>(array: T): T {
    logAccess('crypto.getRandomValues', { spoofed: true, value: 'spoofed' });
    return originalGetRandomValues(array);
  };

  // Spoof randomUUID
  if (crypto.randomUUID) {
    const originalRandomUUID = crypto.randomUUID.bind(crypto);

    crypto.randomUUID = function (): `${string}-${string}-${string}-${string}-${string}` {
      logAccess('crypto.randomUUID', { spoofed: true, value: 'spoofed' });
      return originalRandomUUID();
    };
  }

  // Track subtle crypto operations (can reveal hardware crypto support)
  const subtleOperations = [
    'encrypt', 'decrypt', 'sign', 'verify', 'digest',
    'generateKey', 'deriveKey', 'deriveBits',
    'importKey', 'exportKey', 'wrapKey', 'unwrapKey'
  ];

  for (const op of subtleOperations) {
    const original = (crypto.subtle as any)[op];
    if (typeof original === 'function') {
      (crypto.subtle as any)[op] = function (...args: any[]) {
        logAccess(`crypto.subtle.${op}`, { spoofed: true, value: 'spoofed' });
        return original.apply(crypto.subtle, args);
      };
    }
  }

}
