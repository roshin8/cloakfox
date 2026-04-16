/**
 * Domain Matcher
 *
 * Advanced domain matching with wildcard and pattern support
 * for domain exception rules.
 */

export interface DomainPattern {
  pattern: string;
  type: 'exact' | 'wildcard' | 'regex' | 'suffix';
  compiled?: RegExp;
}

/**
 * Parse a domain pattern string into a DomainPattern object
 */
export function parsePattern(pattern: string): DomainPattern {
  const trimmed = pattern.trim().toLowerCase();

  // Regex pattern (starts with /)
  if (trimmed.startsWith('/') && trimmed.endsWith('/')) {
    const regexStr = trimmed.slice(1, -1);
    return {
      pattern: trimmed,
      type: 'regex',
      compiled: new RegExp(regexStr, 'i'),
    };
  }

  // Wildcard pattern (contains *)
  if (trimmed.includes('*')) {
    // Convert wildcard to regex
    const escaped = trimmed
      .replace(/[.+?^${}()|[\]\\]/g, '\\$&') // Escape special regex chars except *
      .replace(/\*/g, '.*'); // Convert * to .*

    return {
      pattern: trimmed,
      type: 'wildcard',
      compiled: new RegExp(`^${escaped}$`, 'i'),
    };
  }

  // Suffix pattern (starts with .)
  if (trimmed.startsWith('.')) {
    return {
      pattern: trimmed,
      type: 'suffix',
    };
  }

  // Exact match
  return {
    pattern: trimmed,
    type: 'exact',
  };
}

/**
 * Check if a domain matches a pattern
 */
export function matchesDomain(domain: string, pattern: DomainPattern): boolean {
  const normalizedDomain = domain.toLowerCase();

  switch (pattern.type) {
    case 'exact':
      return normalizedDomain === pattern.pattern;

    case 'wildcard':
    case 'regex':
      return pattern.compiled?.test(normalizedDomain) ?? false;

    case 'suffix':
      // .example.com matches sub.example.com and example.com
      const suffix = pattern.pattern.slice(1); // Remove leading .
      return (
        normalizedDomain === suffix ||
        normalizedDomain.endsWith('.' + suffix)
      );

    default:
      return false;
  }
}

/**
 * Check if a domain matches any pattern in a list
 */
export function matchesAnyPattern(
  domain: string,
  patterns: DomainPattern[]
): boolean {
  return patterns.some((pattern) => matchesDomain(domain, pattern));
}

/**
 * Parse a list of pattern strings
 */
export function parsePatterns(patterns: string[]): DomainPattern[] {
  return patterns.map(parsePattern);
}

/**
 * Validate a pattern string
 */
export function validatePattern(pattern: string): {
  valid: boolean;
  error?: string;
} {
  const trimmed = pattern.trim();

  if (!trimmed) {
    return { valid: false, error: 'Pattern cannot be empty' };
  }

  // Check regex validity
  if (trimmed.startsWith('/') && trimmed.endsWith('/')) {
    try {
      new RegExp(trimmed.slice(1, -1));
    } catch (e) {
      return { valid: false, error: 'Invalid regular expression' };
    }
  }

  // Check for invalid characters in non-regex patterns
  if (!trimmed.startsWith('/')) {
    const invalidChars = /[<>:"|?#\s]/;
    if (invalidChars.test(trimmed)) {
      return {
        valid: false,
        error: 'Pattern contains invalid characters',
      };
    }
  }

  return { valid: true };
}

/**
 * Get pattern type description for UI
 */
export function getPatternTypeDescription(pattern: string): string {
  const parsed = parsePattern(pattern);

  switch (parsed.type) {
    case 'exact':
      return `Matches exactly: ${pattern}`;
    case 'wildcard':
      return `Matches wildcard pattern: ${pattern}`;
    case 'regex':
      return `Matches regular expression: ${pattern}`;
    case 'suffix':
      return `Matches domain and subdomains: ${pattern}`;
    default:
      return `Unknown pattern type`;
  }
}

/**
 * Common domain patterns for presets
 */
export const PRESET_PATTERNS = {
  banking: [
    '*.bankofamerica.com',
    '*.chase.com',
    '*.wellsfargo.com',
    '*.capitalone.com',
    '*.citi.com',
    '*.usbank.com',
    '*.pnc.com',
    '*.tdbank.com',
    '*.ally.com',
    '*.paypal.com',
  ],
  streaming: [
    '*.netflix.com',
    '*.hulu.com',
    '*.disneyplus.com',
    '*.hbomax.com',
    '*.primevideo.com',
    '*.peacocktv.com',
    '*.paramountplus.com',
    '*.youtube.com',
    '*.twitch.tv',
    '*.spotify.com',
  ],
  videoConference: [
    '*.zoom.us',
    '*.teams.microsoft.com',
    'meet.google.com',
    '*.webex.com',
    '*.gotomeeting.com',
    '*.whereby.com',
    '*.discord.com',
  ],
  shopping: [
    '*.amazon.com',
    '*.ebay.com',
    '*.walmart.com',
    '*.target.com',
    '*.bestbuy.com',
    '*.etsy.com',
    '*.shopify.com',
  ],
  gaming: [
    '*.steampowered.com',
    '*.epicgames.com',
    '*.ea.com',
    '*.ubisoft.com',
    '*.xbox.com',
    '*.playstation.com',
    '*.riotgames.com',
    '*.blizzard.com',
  ],
  google: [
    '*.google.com',
    '*.gstatic.com',
    '*.googleapis.com',
    '*.googleusercontent.com',
    '*.googlevideo.com',
  ],
  microsoft: [
    '*.microsoft.com',
    '*.live.com',
    '*.office.com',
    '*.outlook.com',
    '*.azure.com',
    '*.windows.com',
  ],
  social: [
    '*.facebook.com',
    '*.twitter.com',
    '*.instagram.com',
    '*.linkedin.com',
    '*.reddit.com',
    '*.tiktok.com',
  ],
};

/**
 * Domain matcher class for efficient matching against multiple rules
 */
export class DomainMatcher {
  private patterns: DomainPattern[] = [];
  private exactMatches: Set<string> = new Set();
  private suffixMatches: string[] = [];
  private regexPatterns: DomainPattern[] = [];

  constructor(patterns: string[] = []) {
    this.setPatterns(patterns);
  }

  /**
   * Set the patterns to match against
   */
  setPatterns(patterns: string[]): void {
    this.patterns = [];
    this.exactMatches.clear();
    this.suffixMatches = [];
    this.regexPatterns = [];

    for (const p of patterns) {
      const parsed = parsePattern(p);
      this.patterns.push(parsed);

      switch (parsed.type) {
        case 'exact':
          this.exactMatches.add(parsed.pattern);
          break;
        case 'suffix':
          this.suffixMatches.push(parsed.pattern.slice(1)); // Remove leading .
          break;
        case 'wildcard':
        case 'regex':
          this.regexPatterns.push(parsed);
          break;
      }
    }
  }

  /**
   * Add a pattern
   */
  addPattern(pattern: string): void {
    const parsed = parsePattern(pattern);
    this.patterns.push(parsed);

    switch (parsed.type) {
      case 'exact':
        this.exactMatches.add(parsed.pattern);
        break;
      case 'suffix':
        this.suffixMatches.push(parsed.pattern.slice(1));
        break;
      case 'wildcard':
      case 'regex':
        this.regexPatterns.push(parsed);
        break;
    }
  }

  /**
   * Remove a pattern
   */
  removePattern(pattern: string): void {
    const patterns = this.patterns
      .filter((p) => p.pattern !== pattern.toLowerCase())
      .map((p) => p.pattern);
    this.setPatterns(patterns);
  }

  /**
   * Check if a domain matches any pattern
   */
  matches(domain: string): boolean {
    const normalized = domain.toLowerCase();

    // Fast path: exact match
    if (this.exactMatches.has(normalized)) {
      return true;
    }

    // Check suffix matches
    for (const suffix of this.suffixMatches) {
      if (normalized === suffix || normalized.endsWith('.' + suffix)) {
        return true;
      }
    }

    // Check regex/wildcard patterns
    for (const pattern of this.regexPatterns) {
      if (pattern.compiled?.test(normalized)) {
        return true;
      }
    }

    return false;
  }

  /**
   * Get all patterns
   */
  getPatterns(): string[] {
    return this.patterns.map((p) => p.pattern);
  }

  /**
   * Get pattern count
   */
  get size(): number {
    return this.patterns.length;
  }
}

export default DomainMatcher;
