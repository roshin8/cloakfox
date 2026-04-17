/**
 * Font Preferences Spoofer
 *
 * FingerprintJS measures default font sizes for serif/sans-serif/monospace/cursive/fantasy.
 * These vary by OS and reveal the platform even when UA is spoofed.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';

export function initFontPreferencesSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Standard default font sizes to report (Windows-like baseline)
  const standardSizes: Record<string, number> = {
    'serif': 16,
    'sans-serif': 16,
    'monospace': 13,
    'cursive': 16,
    'fantasy': 16,
    'system-ui': 16,
  };

  const originalGetComputedStyle = window.getComputedStyle;

  overrideMethod(window as any, 'getComputedStyle', (original, _thisArg, args) => {
    const result = original.apply(window, args);
    const element = args[0] as Element;

    // Check if this is a font-probing element (typically has only generic font family)
    if (element instanceof HTMLElement) {
      const fontFamily = element.style.fontFamily?.toLowerCase()?.replace(/['"]/g, '');
      if (fontFamily && fontFamily in standardSizes) {
        // Return a proxy that spoofs fontSize
        return new Proxy(result, {
          get(target, prop) {
            if (prop === 'fontSize') {
              const noise = mode === 'noise' ? prng.nextNoise(0.5) : 0;
              return (standardSizes[fontFamily] + noise).toFixed(4) + 'px';
            }
            const val = (target as any)[prop];
            return typeof val === 'function' ? val.bind(target) : val;
          },
        });
      }
    }

    return result;
  });
}
