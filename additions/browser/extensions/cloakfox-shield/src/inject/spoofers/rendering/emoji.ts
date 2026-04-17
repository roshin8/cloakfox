/**
 * Emoji Rendering Spoofer
 *
 * Emoji rendering differs across OS/browser combinations,
 * creating a fingerprint when drawn to canvas.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';
import { farbleImageData } from '@/lib/farbling';

// Emoji characters commonly used for fingerprinting
const FINGERPRINT_EMOJIS = [
  '\u{1F600}', '\u{1F3A8}', '\u{1F512}', '\u{1F308}', '\u{1F3AD}', '\u{1F3AA}', '\u{1F3F3}\u{FE0F}\u{200D}\u{1F308}', '\u{1F468}\u{200D}\u{1F469}\u{200D}\u{1F467}\u{200D}\u{1F466}',
  '\u{1F9D1}\u{200D}\u{1F91D}\u{200D}\u{1F9D1}', '\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}', '\u{1F441}\u{FE0F}\u{200D}\u{1F5E8}\u{FE0F}', '\u{26A1}', '\u{2764}\u{FE0F}', '\u{1F525}'
];

/**
 * Initialize emoji rendering spoofing
 */
export function initEmojiSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // The main vector is canvas text rendering of emojis
  // We already spoof canvas, but we can add emoji-specific protection

  // Detect if text contains emoji
  const containsEmoji = (text: string): boolean => {
    const emojiRegex = /[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]|[\u{FE00}-\u{FE0F}]|[\u{1F000}-\u{1F02F}]/u;
    return emojiRegex.test(text);
  };

  // Spoof measureText for emoji
  overrideMethod(CanvasRenderingContext2D.prototype, 'measureText', (original, thisArg, args) => {
    const text = args[0] as string;
    const result = original.call(thisArg, text) as TextMetrics;

    if (containsEmoji(text)) {
      logAccess('CanvasRenderingContext2D.measureText(emoji)', { spoofed: true, value: 'noised' });

      if (mode === 'block') {
        return {
          width: 0,
          actualBoundingBoxLeft: 0,
          actualBoundingBoxRight: 0,
          actualBoundingBoxAscent: 0,
          actualBoundingBoxDescent: 0,
          fontBoundingBoxAscent: 0,
          fontBoundingBoxDescent: 0,
          emHeightAscent: 0,
          emHeightDescent: 0,
          alphabeticBaseline: 0,
          hangingBaseline: 0,
          ideographicBaseline: 0,
        } as TextMetrics;
      }

      // Add noise to metrics
      const noise = () => prng.nextNoise(0.5);
      return new Proxy(result, {
        get(target, prop) {
          const value = (target as any)[prop];
          if (typeof value === 'number') {
            return value + noise();
          }
          return value;
        },
      });
    }

    return result;
  });

}
