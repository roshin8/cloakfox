/**
 * SettingsStore — manages global and per-domain spoofing settings.
 *
 * Global settings apply to all domains by default.
 * Per-domain rules can override specific settings.
 */

import { STORAGE_KEYS, DEFAULT_SETTINGS } from '@/constants';
import type { SpooferSettings } from '@/types';

export interface DomainRule {
  pattern: string; // e.g. "example.com", "*.google.com", "*"
  settings: Partial<SpooferSettings>;
}

/** In-memory cache of settings */
let globalSettings: SpooferSettings = { ...DEFAULT_SETTINGS };
let domainRules: DomainRule[] = [];
let initialized = false;

/** Load settings from storage */
async function ensureLoaded(): Promise<void> {
  if (initialized) return;

  const stored = await browser.storage.local.get([
    STORAGE_KEYS.GLOBAL_SETTINGS,
    STORAGE_KEYS.DOMAIN_RULES,
  ]);

  if (stored[STORAGE_KEYS.GLOBAL_SETTINGS]) {
    globalSettings = stored[STORAGE_KEYS.GLOBAL_SETTINGS] as SpooferSettings;
  }
  if (stored[STORAGE_KEYS.DOMAIN_RULES]) {
    domainRules = stored[STORAGE_KEYS.DOMAIN_RULES] as DomainRule[];
  }

  initialized = true;
}

/** Get merged settings for a specific domain */
export async function getSettingsForDomain(
  _cookieStoreId: string,
  domain: string
): Promise<SpooferSettings> {
  await ensureLoaded();

  // Start with global defaults
  const merged = deepClone(globalSettings);

  // Apply matching domain rules (most specific last)
  for (const rule of domainRules) {
    if (matchesDomain(rule.pattern, domain)) {
      deepMerge(merged, rule.settings);
    }
  }

  return merged;
}

/** Update global settings */
export async function updateGlobalSettings(
  settings: Partial<SpooferSettings>
): Promise<void> {
  await ensureLoaded();
  deepMerge(globalSettings, settings);
  await browser.storage.local.set({
    [STORAGE_KEYS.GLOBAL_SETTINGS]: globalSettings,
  });
}

/** Add or update a domain rule */
export async function setDomainRule(rule: DomainRule): Promise<void> {
  await ensureLoaded();
  const idx = domainRules.findIndex((r) => r.pattern === rule.pattern);
  if (idx >= 0) {
    domainRules[idx] = rule;
  } else {
    domainRules.push(rule);
  }
  await browser.storage.local.set({
    [STORAGE_KEYS.DOMAIN_RULES]: domainRules,
  });
}

/** Remove a domain rule */
export async function removeDomainRule(pattern: string): Promise<void> {
  await ensureLoaded();
  domainRules = domainRules.filter((r) => r.pattern !== pattern);
  await browser.storage.local.set({
    [STORAGE_KEYS.DOMAIN_RULES]: domainRules,
  });
}

/** Check if a pattern matches a domain */
function matchesDomain(pattern: string, domain: string): boolean {
  if (pattern === '*') return true;
  if (pattern === domain) return true;

  // Wildcard subdomain: *.example.com matches sub.example.com and example.com
  if (pattern.startsWith('*.')) {
    const base = pattern.slice(2);
    return domain === base || domain.endsWith('.' + base);
  }

  return false;
}

function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

function deepMerge(target: Record<string, unknown>, source: Record<string, unknown>): void {
  for (const key of Object.keys(source)) {
    const sv = source[key];
    const tv = target[key];
    if (sv && typeof sv === 'object' && !Array.isArray(sv) && tv && typeof tv === 'object') {
      deepMerge(tv as Record<string, unknown>, sv as Record<string, unknown>);
    } else {
      target[key] = sv;
    }
  }
}
