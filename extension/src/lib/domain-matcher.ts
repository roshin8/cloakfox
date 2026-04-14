/**
 * Domain matching for per-domain rules and whitelists.
 * Supports exact, wildcard, suffix, and regex patterns.
 */

export type DomainPattern = string;

export interface DomainRule {
  pattern: DomainPattern;
  action: 'whitelist' | 'blacklist' | 'custom';
  settings?: Record<string, unknown>;
}

/** Check if a domain matches a pattern */
export function matchesDomain(domain: string, pattern: DomainPattern): boolean {
  // Exact match
  if (domain === pattern) return true;

  // Wildcard: *.example.com matches sub.example.com
  if (pattern.startsWith('*.')) {
    const suffix = pattern.slice(2);
    return domain === suffix || domain.endsWith('.' + suffix);
  }

  // Suffix match: .example.com matches anything ending with it
  if (pattern.startsWith('.')) {
    return domain.endsWith(pattern) || domain === pattern.slice(1);
  }

  // Regex: /pattern/flags
  const regexMatch = pattern.match(/^\/(.+)\/([gimsuy]*)$/);
  if (regexMatch) {
    const regex = new RegExp(regexMatch[1]!, regexMatch[2]);
    return regex.test(domain);
  }

  return false;
}

/** Find the first matching rule for a domain */
export function findMatchingRule(
  domain: string,
  rules: DomainRule[]
): DomainRule | undefined {
  return rules.find((rule) => matchesDomain(domain, rule.pattern));
}

/** Extract the effective top-level domain + 1 (eTLD+1) */
export function getBaseDomain(hostname: string): string {
  const parts = hostname.split('.');
  if (parts.length <= 2) return hostname;
  // Simple heuristic — a proper implementation would use the public suffix list
  return parts.slice(-2).join('.');
}
