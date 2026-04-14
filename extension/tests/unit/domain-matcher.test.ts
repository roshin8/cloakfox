import { describe, it, expect } from 'vitest';
import { matchesDomain, findMatchingRule, getBaseDomain } from '../../src/lib/domain-matcher';
import type { DomainRule } from '../../src/lib/domain-matcher';

describe('matchesDomain', () => {
  it('matches exact domains', () => {
    expect(matchesDomain('example.com', 'example.com')).toBe(true);
    expect(matchesDomain('example.com', 'other.com')).toBe(false);
  });

  it('matches wildcard patterns', () => {
    expect(matchesDomain('sub.example.com', '*.example.com')).toBe(true);
    expect(matchesDomain('example.com', '*.example.com')).toBe(true);
    expect(matchesDomain('deep.sub.example.com', '*.example.com')).toBe(true);
    expect(matchesDomain('notexample.com', '*.example.com')).toBe(false);
  });

  it('matches suffix patterns', () => {
    expect(matchesDomain('sub.example.com', '.example.com')).toBe(true);
    expect(matchesDomain('example.com', '.example.com')).toBe(true);
    expect(matchesDomain('other.com', '.example.com')).toBe(false);
  });

  it('matches regex patterns', () => {
    expect(matchesDomain('example.com', '/^example\\.com$/')).toBe(true);
    expect(matchesDomain('sub.example.com', '/example\\.com/')).toBe(true);
    expect(matchesDomain('other.com', '/^example\\.com$/')).toBe(false);
  });

  it('matches case-insensitive regex', () => {
    expect(matchesDomain('Example.com', '/example\\.com/i')).toBe(true);
  });
});

describe('findMatchingRule', () => {
  const rules: DomainRule[] = [
    { pattern: 'exact.com', action: 'whitelist' },
    { pattern: '*.google.com', action: 'custom', settings: { strict: true } },
    { pattern: '.example.com', action: 'blacklist' },
  ];

  it('finds exact match', () => {
    expect(findMatchingRule('exact.com', rules)?.action).toBe('whitelist');
  });

  it('finds wildcard match', () => {
    expect(findMatchingRule('maps.google.com', rules)?.action).toBe('custom');
  });

  it('finds suffix match', () => {
    expect(findMatchingRule('sub.example.com', rules)?.action).toBe('blacklist');
  });

  it('returns undefined for no match', () => {
    expect(findMatchingRule('unknown.org', rules)).toBeUndefined();
  });

  it('returns first match (priority by order)', () => {
    const overlapping: DomainRule[] = [
      { pattern: '*.example.com', action: 'whitelist' },
      { pattern: '.example.com', action: 'blacklist' },
    ];
    expect(findMatchingRule('sub.example.com', overlapping)?.action).toBe('whitelist');
  });
});

describe('getBaseDomain', () => {
  it('returns domain as-is for two parts', () => {
    expect(getBaseDomain('example.com')).toBe('example.com');
  });

  it('strips subdomains', () => {
    expect(getBaseDomain('sub.example.com')).toBe('example.com');
    expect(getBaseDomain('deep.sub.example.com')).toBe('example.com');
  });

  it('handles single-part domains', () => {
    expect(getBaseDomain('localhost')).toBe('localhost');
  });
});
