/**
 * Font Enumeration Spoofer - Prevents font fingerprinting
 *
 * Font fingerprinting works by:
 * 1. Measuring text rendered with specific fonts
 * 2. Checking which system fonts are available
 * 3. Using the unique combination of available fonts as an identifier
 */

import type { ProtectionMode, AssignedProfileData } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

// Cross-platform common fonts
const COMMON_FONTS = [
  'Arial', 'Arial Black', 'Comic Sans MS', 'Courier New', 'Georgia',
  'Impact', 'Times New Roman', 'Trebuchet MS', 'Verdana', 'Helvetica', 'Tahoma',
];

// Windows-specific fonts
const WINDOWS_FONTS = [
  'Calibri', 'Cambria', 'Cambria Math', 'Candara', 'Consolas', 'Constantia', 'Corbel',
  'Segoe UI', 'Segoe UI Symbol', 'Segoe Print', 'Segoe Script',
  'Microsoft Sans Serif', 'Microsoft YaHei', 'Microsoft JhengHei',
  'Malgun Gothic', 'Yu Gothic', 'MS Gothic', 'MS PGothic', 'MS Mincho', 'MS PMincho',
  'SimSun', 'SimHei', 'NSimSun', 'PMingLiU', 'MingLiU',
  'Palatino Linotype', 'Book Antiqua', 'Franklin Gothic Medium',
  'Lucida Console', 'Lucida Sans Unicode',
  'Gadugi', 'Ebrima', 'Leelawadee UI', 'Nirmala UI', 'Javanese Text',
  'Sylfaen', 'Marlett', 'Webdings', 'Wingdings', 'Wingdings 2', 'Wingdings 3',
  'Century Gothic', 'Bookman Old Style', 'Garamond',
  'Agency FB', 'Berlin Sans FB', 'Bodoni MT', 'Britannic Bold',
  'Brush Script MT', 'Castellar', 'Colonna MT', 'Cooper Black',
  'Copperplate Gothic Bold', 'Copperplate Gothic Light',
  'Haettenschweiler', 'Harlow Solid Italic', 'Imprint MT Shadow',
  'Informal Roman', 'Lucida Calligraphy', 'Lucida Handwriting',
  'Mistral', 'Modern No. 20', 'Niagara Engraved', 'Old English Text MT',
  'Onyx', 'Parchment', 'Playbill', 'Rockwell', 'Rockwell Condensed',
  'Script MT Bold', 'Showcard Gothic', 'Snap ITC', 'Stencil',
  'Wide Latin',
];

// macOS-specific fonts
const MACOS_FONTS = [
  'Helvetica Neue', 'San Francisco', 'SF Pro', 'SF Mono', 'SF Compact',
  'Menlo', 'Monaco', 'Avenir', 'Avenir Next', 'Avenir Next Condensed',
  'Baskerville', 'Big Caslon', 'Bodoni 72', 'Bodoni 72 Oldstyle', 'Bodoni 72 Smallcaps',
  'Bradley Hand', 'Brush Script MT', 'Chalkboard', 'Chalkboard SE', 'Chalkduster',
  'Charter', 'Cochin', 'Copperplate', 'Didot', 'Futura',
  'Geneva', 'Gill Sans', 'Herculanum', 'Hoefler Text',
  'Lucida Grande', 'Luminari', 'Marker Felt', 'Noteworthy', 'Optima',
  'Palatino', 'Papyrus', 'Phosphate', 'Rockwell', 'Savoye LET',
  'SignPainter', 'Skia', 'Snell Roundhand', 'Trattatello', 'Zapfino',
  'American Typewriter', 'Andale Mono', 'Apple Chancery', 'Apple Color Emoji',
  'Apple SD Gothic Neo', 'Apple Symbols',
  'Hiragino Sans', 'Hiragino Kaku Gothic ProN', 'Hiragino Mincho ProN',
  'PingFang SC', 'PingFang TC', 'PingFang HK',
  'STHeiti', 'STSong', 'STFangsong', 'STKaiti',
];

// Linux-specific fonts
const LINUX_FONTS = [
  'DejaVu Sans', 'DejaVu Sans Mono', 'DejaVu Serif',
  'Liberation Sans', 'Liberation Serif', 'Liberation Mono',
  'Noto Sans', 'Noto Serif', 'Noto Mono', 'Noto Color Emoji',
  'Ubuntu', 'Ubuntu Mono', 'Ubuntu Condensed',
  'Cantarell', 'Droid Sans', 'Droid Serif', 'Droid Sans Mono',
  'FreeSans', 'FreeSerif', 'FreeMono',
  'Nimbus Sans L', 'Nimbus Roman No9 L', 'Nimbus Mono L',
  'URW Gothic L', 'URW Bookman L', 'URW Chancery L',
  'Bitstream Vera Sans', 'Bitstream Vera Serif', 'Bitstream Vera Sans Mono',
  'Lato', 'Open Sans', 'Roboto', 'Source Code Pro', 'Source Sans Pro',
  'Fira Sans', 'Fira Mono', 'Inconsolata',
];

function getPlatformFonts(platformName?: string): string[] {
  switch (platformName) {
    case 'Windows': return WINDOWS_FONTS;
    case 'macOS': return MACOS_FONTS;
    case 'Linux': return LINUX_FONTS;
    default: return WINDOWS_FONTS; // Default to Windows (most common)
  }
}

/**
 * Initialize font enumeration spoofing
 */
export function initFontSpoofer(mode: ProtectionMode, prng: PRNG, assignedProfile?: AssignedProfileData): void {
  if (mode === 'off') return;

  // Select fonts matching the SPOOFED platform, not the real one
  const platformName = assignedProfile?.userAgent?.platformName;
  const platformFonts = getPlatformFonts(platformName);

  let availableFonts: Set<string>;

  if (mode === 'block') {
    // Only common fonts
    availableFonts = new Set(COMMON_FONTS);
  } else {
    // Common fonts + random subset of platform-appropriate fonts
    const shuffled = prng.shuffle([...platformFonts]);
    const numExtra = prng.nextInt(15, Math.min(40, shuffled.length));
    availableFonts = new Set([
      ...COMMON_FONTS,
      ...shuffled.slice(0, numExtra),
    ]);
  }

  // System font keywords that reveal the real OS
  const MAC_SYSTEM_FONTS = new Set(['-apple-system', 'BlinkMacSystemFont', '.AppleSystemUIFont', 'Apple Color Emoji']);
  const WIN_SYSTEM_FONTS = new Set(['Segoe UI', 'Segoe UI Emoji', 'Segoe UI Symbol']);
  const LINUX_SYSTEM_FONTS = new Set(['Cantarell', 'Ubuntu', 'Noto Sans']);

  // Block system fonts from wrong platform
  const blockedSystemFonts = new Set<string>();
  if (platformName !== 'macOS') MAC_SYSTEM_FONTS.forEach(f => blockedSystemFonts.add(f));
  if (platformName !== 'Windows') WIN_SYSTEM_FONTS.forEach(f => blockedSystemFonts.add(f));
  if (platformName !== 'Linux') LINUX_SYSTEM_FONTS.forEach(f => blockedSystemFonts.add(f));

  // Override document.fonts if available
  if ('fonts' in document && document.fonts) {
    const originalCheck = document.fonts.check.bind(document.fonts);

    document.fonts.check = function (font: string, text?: string): boolean {
      logAccess('document.fonts.check', { spoofed: true, value: `${availableFonts.size} fonts` });
      const fontFamily = extractFontFamily(font);

      // Block fonts not in our platform set or wrong-platform system fonts
      if (fontFamily && (blockedSystemFonts.has(fontFamily) || !availableFonts.has(fontFamily))) {
        return false;
      }

      return originalCheck(font, text);
    };

    // Override FontFaceSet.prototype.check
    overrideMethod(FontFaceSet.prototype, 'check', (original, thisArg, args) => {
      logAccess('FontFaceSet.check', { spoofed: true, value: `${availableFonts.size} fonts` });
      const font = args[0] as string;
      const text = args[1] as string | undefined;
      const fontFamily = extractFontFamily(font);

      if (fontFamily && !availableFonts.has(fontFamily)) {
        return false;
      }

      return original.call(thisArg, font, text);
    });
  }

  // Override FontFace constructor + load() to block non-platform fonts.
  // CreepJS uses: new FontFace(font, 'local("font")').load() and checks if it resolves.
  if (typeof FontFace !== 'undefined') {
    const OrigFontFace = FontFace;
    (window as any).FontFace = function(family: string, source: string, descriptors?: FontFaceDescriptors) {
      const ff = new OrigFontFace(family, source, descriptors);
      const origLoad = ff.load.bind(ff);

      // If font not in our platform list, make load() reject
      if (family && !availableFonts.has(family) && blockedSystemFonts.has(family) || (family && !availableFonts.has(family) && !family.startsWith('-'))) {
        ff.load = () => Promise.reject(new DOMException('A network error occurred.', 'NetworkError'));
      }

      return ff;
    };
    (window as any).FontFace.prototype = OrigFontFace.prototype;
  }

  const GENERIC_FONTS = new Set(['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui', 'ui-sans-serif', 'ui-serif', 'ui-monospace']);

  // Override CSS font-family resolution via computed styles
  overrideMethod(window as any, 'getComputedStyle', (original, _thisArg, args) => {
    logAccess('getComputedStyle(fontFamily)', { spoofed: true, value: `${availableFonts.size} fonts` });
    const styles = original.apply(window, args);

    return new Proxy(styles, {
      get(target, prop) {
        const value = (target as any)[prop];

        if (prop === 'fontFamily' && typeof value === 'string') {
          const families = value.split(',').map((f: string) => f.trim().replace(/["']/g, ''));
          const filtered = families.filter(
            (f: string) => !blockedSystemFonts.has(f) && (availableFonts.has(f) || GENERIC_FONTS.has(f))
          );
          return filtered.join(', ') || 'sans-serif';
        }

        if (typeof value === 'function') {
          return value.bind(target);
        }

        return value;
      },
    });
  });
}

/**
 * Extract font family name from CSS font shorthand string.
 * Handles: "12px Arial", "bold 14px 'Times New Roman'", "12px \"American Typewriter\""
 */
function extractFontFamily(font: string): string | null {
  // Try quoted font name first: "..." or '...'
  const quotedMatch = font.match(/["']([^"']+)["']/);
  if (quotedMatch) return quotedMatch[1];

  // Unquoted: everything after the size value (e.g., "12px Arial Black")
  const sizeMatch = font.match(/\d+(?:px|pt|em|rem|%|ex|ch|vw|vh)\s*\/?\s*[\d.]*\s*(.*)/i);
  if (sizeMatch && sizeMatch[1]) {
    return sizeMatch[1].trim().replace(/,.*$/, '').trim();
  }

  // Fallback: return the whole string trimmed
  return font.trim() || null;
}
