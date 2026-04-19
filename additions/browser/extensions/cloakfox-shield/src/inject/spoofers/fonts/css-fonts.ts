/**
 * CSS Font Detection Spoofer
 *
 * Fonts can be detected using CSS by measuring rendered text dimensions.
 * This is harder to spoof than JS font enumeration.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize CSS font detection spoofing
 */
export function initCSSFontSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Spoof document.fonts (FontFaceSet)
  if ('fonts' in document) {
    const originalFonts = document.fonts;

    // Spoof check() method
    const originalCheck = originalFonts.check.bind(originalFonts);

    originalFonts.check = function (font: string, text?: string): boolean {
      logAccess('document.fonts.check', { spoofed: true });

      if (mode === 'block') {
        // Only report system fonts as available
        const systemFonts = ['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy'];
        const fontFamily = font.split(' ').pop()?.toLowerCase() || '';
        return systemFonts.some(sf => fontFamily.includes(sf));
      }

      return originalCheck(font, text);
    };

    // Spoof load() method
    const originalLoad = originalFonts.load.bind(originalFonts);

    originalFonts.load = async function (font: string, text?: string): Promise<FontFace[]> {
      logAccess('document.fonts.load', { spoofed: true });

      if (mode === 'block') {
        return [];
      }

      return originalLoad(font, text);
    };

    // Spoof ready promise
    Object.defineProperty(originalFonts, 'ready', {
      get: function () {
        logAccess('document.fonts.ready', { spoofed: true });
        return Promise.resolve(originalFonts);
      },
    });

    // Spoof status
    Object.defineProperty(originalFonts, 'status', {
      get: function () {
        return 'loaded';
      },
    });
  }

  // Spoof FontFace constructor
  if (typeof FontFace !== 'undefined') {
    const OriginalFontFace = FontFace;

    // @ts-ignore
    window.FontFace = function (
      family: string,
      source: string | ArrayBuffer | ArrayBufferView,
      descriptors?: FontFaceDescriptors
    ): FontFace {
      logAccess('FontFace.constructor', { spoofed: true });

      if (mode === 'block') {
        // Return a font face that never loads
        const fakeFontFace = new OriginalFontFace(family, source as BufferSource, descriptors);
        Object.defineProperty(fakeFontFace, 'status', { value: 'error' });
        return fakeFontFace;
      }

      return new OriginalFontFace(family, source as BufferSource, descriptors);
    };

    (window.FontFace as any).prototype = OriginalFontFace.prototype;
  }

}
