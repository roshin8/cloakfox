/**
 * Intl APIs Spoofer
 *
 * Various Intl APIs reveal locale and formatting preferences
 * that can be used for fingerprinting.
 */

import type { ProtectionMode, AssignedProfileData } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize Intl APIs spoofing
 */
export function initIntlSpoofer(mode: ProtectionMode, prng: PRNG, assignedProfile?: AssignedProfileData): void {
  if (mode === 'off') return;

  // Use profile language, not hardcoded en-US
  const spoofedLocale = assignedProfile?.languages?.[0] || 'en-US';

  // Spoof Intl.ListFormat
  if (typeof Intl.ListFormat !== 'undefined') {
    const OriginalListFormat = Intl.ListFormat;

    // @ts-ignore
    Intl.ListFormat = function (
      locales?: string | string[],
      options?: Intl.ListFormatOptions
    ): Intl.ListFormat {
      logAccess('Intl.ListFormat', { spoofed: true, value: 'spoofed' });

      if (mode === 'block') {
        locales = spoofedLocale;
      }

      return new OriginalListFormat(locales, options);
    };

    (Intl.ListFormat as any).supportedLocalesOf = OriginalListFormat.supportedLocalesOf;
  }

  // Spoof Intl.RelativeTimeFormat
  if (typeof Intl.RelativeTimeFormat !== 'undefined') {
    const OriginalRelativeTimeFormat = Intl.RelativeTimeFormat;

    // @ts-ignore
    Intl.RelativeTimeFormat = function (
      locales?: string | string[],
      options?: Intl.RelativeTimeFormatOptions
    ): Intl.RelativeTimeFormat {
      logAccess('Intl.RelativeTimeFormat', { spoofed: true, value: 'spoofed' });

      if (mode === 'block') {
        locales = spoofedLocale;
      }

      return new OriginalRelativeTimeFormat(locales, options);
    };

    (Intl.RelativeTimeFormat as any).supportedLocalesOf = OriginalRelativeTimeFormat.supportedLocalesOf;
  }

  // Spoof Intl.PluralRules
  if (typeof Intl.PluralRules !== 'undefined') {
    const OriginalPluralRules = Intl.PluralRules;

    // @ts-ignore
    Intl.PluralRules = function (
      locales?: string | string[],
      options?: Intl.PluralRulesOptions
    ): Intl.PluralRules {
      logAccess('Intl.PluralRules', { spoofed: true, value: 'spoofed' });

      if (mode === 'block') {
        locales = spoofedLocale;
      }

      return new OriginalPluralRules(locales, options);
    };

    (Intl.PluralRules as any).supportedLocalesOf = OriginalPluralRules.supportedLocalesOf;
  }

  // Spoof Intl.NumberFormat
  if (typeof Intl.NumberFormat !== 'undefined') {
    const OriginalNumberFormat = Intl.NumberFormat;

    // @ts-ignore
    Intl.NumberFormat = function (
      locales?: string | string[],
      options?: Intl.NumberFormatOptions
    ): Intl.NumberFormat {
      logAccess('Intl.NumberFormat', { spoofed: true, value: 'spoofed' });

      if (mode === 'block') {
        locales = spoofedLocale;
      }

      return new OriginalNumberFormat(locales, options);
    };

    (Intl.NumberFormat as any).supportedLocalesOf = OriginalNumberFormat.supportedLocalesOf;
  }

  // Spoof Intl.Collator
  if (typeof Intl.Collator !== 'undefined') {
    const OriginalCollator = Intl.Collator;

    // @ts-ignore
    Intl.Collator = function (
      locales?: string | string[],
      options?: Intl.CollatorOptions
    ): Intl.Collator {
      logAccess('Intl.Collator', { spoofed: true, value: 'spoofed' });

      if (mode === 'block') {
        locales = spoofedLocale;
      }

      return new OriginalCollator(locales, options);
    };

    (Intl.Collator as any).supportedLocalesOf = OriginalCollator.supportedLocalesOf;
  }

  // Spoof Intl.Segmenter (if available)
  if (typeof (Intl as any).Segmenter !== 'undefined') {
    const OriginalSegmenter = (Intl as any).Segmenter;

    (Intl as any).Segmenter = function (
      locales?: string | string[],
      options?: any
    ): any {
      logAccess('Intl.Segmenter', { spoofed: true, value: 'spoofed' });

      if (mode === 'block') {
        locales = spoofedLocale;
      }

      return new OriginalSegmenter(locales, options);
    };

    (Intl as any).Segmenter.supportedLocalesOf = OriginalSegmenter.supportedLocalesOf;
  }

  // Spoof Intl.DisplayNames
  if (typeof (Intl as any).DisplayNames !== 'undefined') {
    const OriginalDisplayNames = (Intl as any).DisplayNames;

    (Intl as any).DisplayNames = function (
      locales?: string | string[],
      options?: any
    ): any {
      logAccess('Intl.DisplayNames', { spoofed: true, value: 'spoofed' });

      if (mode === 'block') {
        locales = spoofedLocale;
      }

      return new OriginalDisplayNames(locales, options);
    };

    (Intl as any).DisplayNames.supportedLocalesOf = OriginalDisplayNames.supportedLocalesOf;
  }

}
