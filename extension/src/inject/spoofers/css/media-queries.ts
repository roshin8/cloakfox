/**
 * CSS Media Queries Spoofer
 *
 * Media queries reveal screen characteristics, color preferences,
 * motion preferences, and system info. FingerprintJS/fingerprint.com
 * check all of these.
 */

import type { ProtectionMode, AssignedProfileData } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

interface MediaQueryOverrides {
  'prefers-color-scheme': 'light' | 'dark';
  'prefers-reduced-motion': 'no-preference' | 'reduce';
  'prefers-contrast': 'no-preference' | 'more' | 'less';
  'prefers-reduced-transparency': 'no-preference' | 'reduce';
  'forced-colors': 'none' | 'active';
  'inverted-colors': 'none' | 'inverted';
  'color-gamut': 'srgb' | 'p3' | 'rec2020';
  'dynamic-range': 'standard' | 'high';
  'pointer': 'none' | 'coarse' | 'fine';
  'hover': 'none' | 'hover';
  'any-pointer': 'none' | 'coarse' | 'fine';
  'any-hover': 'none' | 'hover';
}

export function initCSSSpoofer(mode: ProtectionMode, prng: PRNG, assignedProfile?: AssignedProfileData): void {
  if (mode === 'off') return;

  const originalMatchMedia = window.matchMedia;

  // Get spoofed screen dimensions to match CSS queries
  const spoofedWidth = assignedProfile?.screen?.width;
  const spoofedHeight = assignedProfile?.screen?.height;
  const spoofedDPR = assignedProfile?.screen?.devicePixelRatio;

  const overrides: MediaQueryOverrides = {
    'prefers-color-scheme': prng.pick(['light', 'dark']),
    'prefers-reduced-motion': prng.pick(['no-preference', 'no-preference', 'no-preference', 'reduce']),
    'prefers-contrast': 'no-preference',
    'prefers-reduced-transparency': 'no-preference',
    'forced-colors': 'none',
    'inverted-colors': 'none',
    'color-gamut': prng.pick(['srgb', 'p3']),
    'dynamic-range': prng.pick(['standard', 'high']),
    'pointer': 'fine',
    'hover': 'hover',
    'any-pointer': 'fine',
    'any-hover': 'hover',
  };

  // monochrome: always report 0 (non-monochrome)
  // This is a numeric query so handled separately

  overrideMethod(window as any, 'matchMedia', (original, thisArg, args) => {
    logAccess('matchMedia', { spoofed: true });
    const query = args[0] as string;

    // Handle monochrome query
    if (/\(\s*monochrome\s*\)/.test(query)) {
      return createFakeMediaQueryList(query, false);
    }
    if (/\(\s*monochrome\s*:\s*0\s*\)/.test(query)) {
      return createFakeMediaQueryList(query, true);
    }

    // Handle screen dimension queries (width, height, device-width, device-height)
    if (spoofedWidth && spoofedHeight) {
      // Match queries like (width: 1680px), (max-width: 1680px), (min-width: 1024px)
      const dimQueries: Array<{ pattern: RegExp; evaluate: (val: number) => boolean }> = [
        { pattern: /\(\s*(?:device-)?width\s*:\s*(\d+)(?:px)?\s*\)/i, evaluate: (v) => v === spoofedWidth },
        { pattern: /\(\s*max-(?:device-)?width\s*:\s*(\d+)(?:px)?\s*\)/i, evaluate: (v) => spoofedWidth <= v },
        { pattern: /\(\s*min-(?:device-)?width\s*:\s*(\d+)(?:px)?\s*\)/i, evaluate: (v) => spoofedWidth >= v },
        { pattern: /\(\s*(?:device-)?height\s*:\s*(\d+)(?:px)?\s*\)/i, evaluate: (v) => v === spoofedHeight },
        { pattern: /\(\s*max-(?:device-)?height\s*:\s*(\d+)(?:px)?\s*\)/i, evaluate: (v) => spoofedHeight <= v },
        { pattern: /\(\s*min-(?:device-)?height\s*:\s*(\d+)(?:px)?\s*\)/i, evaluate: (v) => spoofedHeight >= v },
      ];

      if (spoofedDPR) {
        dimQueries.push(
          { pattern: /\(\s*(?:-webkit-)?device-pixel-ratio\s*:\s*([\d.]+)\s*\)/i, evaluate: (v) => v === spoofedDPR },
          { pattern: /\(\s*(?:-webkit-)?min-device-pixel-ratio\s*:\s*([\d.]+)\s*\)/i, evaluate: (v) => spoofedDPR >= v },
          { pattern: /\(\s*(?:-webkit-)?max-device-pixel-ratio\s*:\s*([\d.]+)\s*\)/i, evaluate: (v) => spoofedDPR <= v },
          { pattern: /\(\s*resolution\s*:\s*([\d.]+)dppx\s*\)/i, evaluate: (v) => v === spoofedDPR },
        );
      }

      for (const { pattern, evaluate } of dimQueries) {
        const dimMatch = query.match(pattern);
        if (dimMatch) {
          return createFakeMediaQueryList(query, evaluate(parseFloat(dimMatch[1])));
        }
      }
    }

    // Handle feature queries we override
    for (const [feature, value] of Object.entries(overrides)) {
      const regex = new RegExp(`\\(\\s*${feature}\\s*:\\s*([^)]+)\\s*\\)`);
      const match = query.match(regex);
      if (match) {
        return createFakeMediaQueryList(query, match[1].trim() === value);
      }
    }

    return original.apply(thisArg, args);
  });

  // Intercept getPropertyValue for CSS custom properties set by @media rules.
  // CreepJS creates: @media(device-width:1680px){body{--device-width:1680;}}
  // Then reads: getComputedStyle(body).getPropertyValue('--device-width')
  if (spoofedWidth && spoofedHeight) {
    const origGetPropValue = CSSStyleDeclaration.prototype.getPropertyValue;
    CSSStyleDeclaration.prototype.getPropertyValue = function(prop: string): string {
      const val = origGetPropValue.call(this, prop);

      // Rewrite --device-width/height/screen/aspect-ratio
      if (prop === '--device-width' && val.trim()) return String(spoofedWidth);
      if (prop === '--device-height' && val.trim()) return String(spoofedHeight);
      if (prop === '--device-screen' && val.trim()) return `${spoofedWidth} x ${spoofedHeight}`;
      if (prop === '--device-aspect-ratio' && val.trim()) {
        const gcd = (a: number, b: number): number => b === 0 ? a : gcd(b, a % b);
        const d = gcd(spoofedWidth, spoofedHeight);
        return `${spoofedWidth / d}/${spoofedHeight / d}`;
      }

      return val;
    };
  }
}

function createFakeMediaQueryList(query: string, matches: boolean): MediaQueryList {
  const listeners: Array<(event: MediaQueryListEvent) => void> = [];

  return {
    matches,
    media: query,
    onchange: null,
    addListener: (cb: any) => { if (cb) listeners.push(cb); },
    removeListener: (cb: any) => {
      const idx = listeners.indexOf(cb);
      if (idx > -1) listeners.splice(idx, 1);
    },
    addEventListener: (_type: string, cb: any) => { if (cb) listeners.push(cb); },
    removeEventListener: (_type: string, cb: any) => {
      const idx = listeners.indexOf(cb);
      if (idx > -1) listeners.splice(idx, 1);
    },
    dispatchEvent: () => true,
  } as MediaQueryList;
}
