/**
 * Timezone Spoofer - Spoofs timezone and locale APIs
 * Uses assigned profile for guaranteed uniqueness across containers
 */

import type { TimezoneSpoofers, AssignedProfileData } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { farbleTimezoneOffset } from '@/lib/farbling';
import { overrideMethod, registerNative } from '@/lib/stealth';
import { TIMEZONE_IANA } from '@/lib/constants';
import { logAccess } from '../../monitor/fingerprint-monitor';

/** Exposed for Worker preamble builder — ms difference between spoofed and real timezone */
let _timezoneOffsetDiffMs = 0;
export function getTimezoneOffsetDiffMs(): number { return _timezoneOffsetDiffMs; }

// Map language codes to likely timezone offsets
const LANGUAGE_TIMEZONE: Record<string, { offset: number; tz: string }> = {
  'ja': { offset: 540, tz: 'Asia/Tokyo' },
  'ko': { offset: 540, tz: 'Asia/Seoul' },
  'zh': { offset: 480, tz: 'Asia/Shanghai' },
  'fr': { offset: 60, tz: 'Europe/Paris' },
  'de': { offset: 60, tz: 'Europe/Berlin' },
  'it': { offset: 60, tz: 'Europe/Rome' },
  'es': { offset: 60, tz: 'Europe/Madrid' },
  'pt': { offset: -180, tz: 'America/Sao_Paulo' },
  'ru': { offset: 180, tz: 'Europe/Moscow' },
  'ar': { offset: 180, tz: 'Asia/Riyadh' },
  'hi': { offset: 330, tz: 'Asia/Kolkata' },
  'th': { offset: 420, tz: 'Asia/Bangkok' },
  'vi': { offset: 420, tz: 'Asia/Ho_Chi_Minh' },
  'tr': { offset: 180, tz: 'Europe/Istanbul' },
  'pl': { offset: 60, tz: 'Europe/Warsaw' },
  'nl': { offset: 60, tz: 'Europe/Amsterdam' },
  'sv': { offset: 60, tz: 'Europe/Stockholm' },
  'da': { offset: 60, tz: 'Europe/Copenhagen' },
  'fi': { offset: 120, tz: 'Europe/Helsinki' },
  'no': { offset: 60, tz: 'Europe/Oslo' },
  'he': { offset: 120, tz: 'Asia/Jerusalem' },
  'uk': { offset: 120, tz: 'Europe/Kyiv' },
  'en': { offset: -300, tz: 'America/New_York' },
};

/**
 * Initialize timezone spoofing
 */
/**
 * Compute the current getTimezoneOffset value for a given IANA timezone.
 * This correctly handles DST transitions.
 *
 * Uses getUTC*() for the UTC side (guaranteed correct) and
 * Intl.DateTimeFormat.formatToParts with hourCycle:'h23' for target timezone
 * (avoids hour "24" midnight bug in some Firefox versions).
 */
function computeOffsetForTimezone(timezone: string): number {
  try {
    const now = new Date();

    // Get target timezone local time components via Intl
    const parts: Record<string, number> = {};
    new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      year: 'numeric', month: 'numeric', day: 'numeric',
      hour: 'numeric', minute: 'numeric', second: 'numeric',
      hourCycle: 'h23', // 0-23 range, avoids "24" bug
    }).formatToParts(now).forEach(p => {
      if (p.type !== 'literal') parts[p.type] = parseInt(p.value, 10);
    });

    // Build UTC timestamp from target timezone's local time
    const tzAsUtc = Date.UTC(
      parts.year, parts.month - 1, parts.day,
      parts.hour, parts.minute, parts.second
    );

    // Build actual UTC timestamp from Date's UTC methods (guaranteed correct)
    const utc = Date.UTC(
      now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(),
      now.getUTCHours(), now.getUTCMinutes(), now.getUTCSeconds()
    );

    return (utc - tzAsUtc) / 60000;
  } catch {
    return 0;
  }
}

export function initTimezoneSpoofer(
  settings: TimezoneSpoofers,
  prng: PRNG,
  assignedProfile?: AssignedProfileData
): void {
  // Determine timezone IANA name - prefer assigned profile, then infer from language
  let targetTimezone: string;

  if (assignedProfile?.timezoneOffset !== undefined) {
    targetTimezone = TIMEZONE_IANA[assignedProfile.timezoneOffset] || 'UTC';

    // If timezone name doesn't match, try to get a better one from language
    if (targetTimezone === 'UTC' && assignedProfile?.languages?.length) {
      const lang = assignedProfile.languages[0].split('-')[0];
      const langTZ = LANGUAGE_TIMEZONE[lang];
      if (langTZ) {
        targetTimezone = langTZ.tz;
      }
    }
  } else if (assignedProfile?.languages?.length) {
    const lang = assignedProfile.languages[0].split('-')[0];
    const langTZ = LANGUAGE_TIMEZONE[lang];
    if (langTZ) {
      targetTimezone = langTZ.tz;
    } else {
      const offset = farbleTimezoneOffset(prng);
      targetTimezone = TIMEZONE_IANA[offset] || 'UTC';
    }
  } else {
    const offset = farbleTimezoneOffset(prng);
    targetTimezone = TIMEZONE_IANA[offset] || 'UTC';
  }

  // Compute actual offset dynamically (handles DST correctly)
  const currentOffset = computeOffsetForTimezone(targetTimezone);

  // Spoof Date.prototype.getTimezoneOffset
  // Use DIRECT defineProperty (not overrideMethod/Proxy) because
  // Firefox Proxy-wrapped getTimezoneOffset may not intercept all call paths
  if (settings.date !== 'off') {
    // Save REAL getTimezoneOffset BEFORE overriding (needed for Date constructor offset computation)
    const _realGetTZO = Date.prototype.getTimezoneOffset;
    const realOffset = _realGetTZO.call(new Date());

    let tzLogged = false;
    const spoofedGetTZO = function getTimezoneOffset(this: Date): number {
      if (!tzLogged) {
        logAccess('Date.getTimezoneOffset', { spoofed: true, value: targetTimezone });
        tzLogged = true;
      }
      if (settings.date === 'block') return 0;
      return currentOffset;
    };
    registerNative(spoofedGetTZO, 'getTimezoneOffset');
    // Try multiple override strategies — Firefox 149 may not honor defineProperty
    // on certain builtin prototypes in the page context
    try {
      Object.defineProperty(Date.prototype, 'getTimezoneOffset', {
        value: spoofedGetTZO, writable: true, configurable: true,
      });
    } catch {}
    // Direct assignment as fallback
    Date.prototype.getTimezoneOffset = spoofedGetTZO;

    // Override Date constructor to spoof timezone for string-based offset computation.
    // CreepJS computes timezone via:
    //   utc = Date.parse(new Date("4/06/2026"))  ← local-parsed
    //   now = +new Date("2026-04-06")             ← UTC-parsed (ISO date-only)
    //   offset = (utc - now) / 60000
    //
    // We shift LOCAL-parsed dates but NOT UTC-parsed (ISO date-only) dates.
    const OrigDate = Date;
    // realOffset was saved before the override above
    const offsetDiffMs = (currentOffset - realOffset) * 60000;
    _timezoneOffsetDiffMs = offsetDiffMs; // Expose for Worker preamble

    // ISO date-only format (YYYY-MM-DD) is parsed as UTC per spec — don't shift
    const isISODateOnly = (s: string): boolean => /^\d{4}-\d{2}-\d{2}$/.test(s.trim());

    const SpoofedDate = function(this: any, ...args: any[]) {
      if (new.target) {
        if (args.length === 0) {
          return new OrigDate();
        }
        if (args.length === 1 && typeof args[0] === 'string') {
          const s = args[0];
          if (isISODateOnly(s)) {
            return new OrigDate(s); // UTC — no shift
          }
          // Local-parsed — shift to spoofed timezone
          return new OrigDate(OrigDate.parse(s) + offsetDiffMs);
        }
        return new (OrigDate as any)(...args);
      }
      return new OrigDate().toString();
    } as any;

    SpoofedDate.prototype = OrigDate.prototype;
    Object.setPrototypeOf(SpoofedDate, OrigDate);
    SpoofedDate.now = OrigDate.now;
    SpoofedDate.UTC = OrigDate.UTC;
    SpoofedDate.parse = function(s: string): number {
      if (isISODateOnly(s)) return OrigDate.parse(s); // UTC — no shift
      return OrigDate.parse(s) + offsetDiffMs;
    };
    registerNative(SpoofedDate, 'Date');
    registerNative(SpoofedDate.parse, 'parse');

    try { (window as any).Date = SpoofedDate; } catch {}


    // Also spoof toLocaleString methods to be consistent
    overrideMethod(Date.prototype, 'toLocaleString', (original, thisArg, args) => {
      const locales = args[0] as string | string[] | undefined;
      const options = args[1] as Intl.DateTimeFormatOptions | undefined;
      return original.call(thisArg, locales, {
        ...options,
        timeZone: options?.timeZone || targetTimezone,
      });
    });

    overrideMethod(Date.prototype, 'toLocaleDateString', (original, thisArg, args) => {
      const locales = args[0] as string | string[] | undefined;
      const options = args[1] as Intl.DateTimeFormatOptions | undefined;
      return original.call(thisArg, locales, {
        ...options,
        timeZone: options?.timeZone || targetTimezone,
      });
    });

    overrideMethod(Date.prototype, 'toLocaleTimeString', (original, thisArg, args) => {
      const locales = args[0] as string | string[] | undefined;
      const options = args[1] as Intl.DateTimeFormatOptions | undefined;
      return original.call(thisArg, locales, {
        ...options,
        timeZone: options?.timeZone || targetTimezone,
      });
    });

    // Override toString/toTimeString to show spoofed timezone name
    // These embed the OS timezone name (e.g., "Central Daylight Time") which leaks real location
    const offsetSign = currentOffset <= 0 ? '+' : '-';
    const absOffset = Math.abs(currentOffset);
    const offsetHours = String(Math.floor(absOffset / 60)).padStart(2, '0');
    const offsetMins = String(absOffset % 60).padStart(2, '0');
    const gmtString = `GMT${offsetSign}${offsetHours}${offsetMins}`;

    // Get the timezone abbreviation from Intl
    let tzAbbr = targetTimezone;
    try {
      const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: targetTimezone, timeZoneName: 'long',
      }).formatToParts(new Date());
      const tzPart = parts.find(p => p.type === 'timeZoneName');
      if (tzPart) tzAbbr = tzPart.value;
    } catch {}

    overrideMethod(Date.prototype, 'toString', (original, thisArg, _args) => {
      const date = thisArg as Date;
      // Rebuild the string with spoofed timezone
      try {
        const dateStr = new Intl.DateTimeFormat('en-US', {
          timeZone: targetTimezone,
          weekday: 'short', year: 'numeric', month: 'short', day: '2-digit',
          hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
        }).format(date);
        return `${dateStr} ${gmtString} (${tzAbbr})`;
      } catch {
        return original.call(thisArg);
      }
    });

    overrideMethod(Date.prototype, 'toTimeString', (original, thisArg, _args) => {
      const date = thisArg as Date;
      try {
        const timeStr = new Intl.DateTimeFormat('en-US', {
          timeZone: targetTimezone,
          hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
        }).format(date);
        return `${timeStr} ${gmtString} (${tzAbbr})`;
      } catch {
        return original.call(thisArg);
      }
    });

    overrideMethod(Date.prototype, 'toDateString', (original, thisArg, _args) => {
      const date = thisArg as Date;
      try {
        return new Intl.DateTimeFormat('en-US', {
          timeZone: targetTimezone,
          weekday: 'short', year: 'numeric', month: 'short', day: '2-digit',
        }).format(date);
      } catch {
        return original.call(thisArg);
      }
    });
  }

  // Spoof Intl.DateTimeFormat
  if (settings.intl !== 'off') {
    const OriginalDateTimeFormat = Intl.DateTimeFormat;

    let intlLogged = false;
    // @ts-ignore - We're replacing the constructor
    Intl.DateTimeFormat = function (
      locales?: string | string[],
      options?: Intl.DateTimeFormatOptions
    ): Intl.DateTimeFormat {
      if (!intlLogged) {
        logAccess('Intl.DateTimeFormat', { spoofed: true, value: targetTimezone });
        intlLogged = true;
      }
      return new OriginalDateTimeFormat(locales, {
        ...options,
        timeZone: options?.timeZone || targetTimezone,
      });
    };

    // Copy static methods
    Intl.DateTimeFormat.supportedLocalesOf = OriginalDateTimeFormat.supportedLocalesOf;

    // Override resolvedOptions to return our timezone
    overrideMethod(OriginalDateTimeFormat.prototype, 'resolvedOptions', (original, thisArg, _args) => {
      const options = original.call(thisArg) as Intl.ResolvedDateTimeFormatOptions;
      return {
        ...options,
        timeZone: targetTimezone,
      };
    });
  }

}
