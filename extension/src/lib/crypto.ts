/**
 * Cryptographic utilities for Cloakfox Shield
 * Uses Web Crypto API and xorshift128+ PRNG
 */

/**
 * Generate a cryptographically secure random seed (32 bytes)
 */
export async function generateSeed(): Promise<Uint8Array> {
  return crypto.getRandomValues(new Uint8Array(32));
}

/**
 * Convert Uint8Array to base64 string
 */
export function uint8ArrayToBase64(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Convert base64 string to Uint8Array
 */
export function base64ToUint8Array(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/**
 * Hash a string using SHA-256
 */
export async function sha256(input: string): Promise<Uint8Array> {
  const encoder = new TextEncoder();
  const data = encoder.encode(input);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  return new Uint8Array(hashBuffer);
}

/**
 * Hash a string to a hex string
 */
export async function sha256Hex(input: string): Promise<string> {
  const hash = await sha256(input);
  return Array.from(hash)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Derive a deterministic key from seed + domain + api name
 * Used to generate consistent fingerprints per container + domain
 */
export async function deriveKey(
  seed: Uint8Array | string,
  domain: string,
  apiName: string
): Promise<Uint8Array> {
  const seedStr = typeof seed === 'string' ? seed : uint8ArrayToBase64(seed);
  const input = `${seedStr}:${domain}:${apiName}`;
  return sha256(input);
}

/**
 * xorshift128+ PRNG - fast, deterministic, good distribution
 * State initialized from a 32-byte seed
 */
export class PRNG {
  private static readonly MASK64 = (1n << 64n) - 1n;
  private state0: bigint;
  private state1: bigint;

  constructor(seed: Uint8Array) {
    // Initialize state from first 16 bytes
    const view = new DataView(seed.buffer, seed.byteOffset, seed.byteLength);
    this.state0 = view.getBigUint64(0, true);
    this.state1 = view.getBigUint64(8, true);

    // Ensure non-zero state
    if (this.state0 === 0n && this.state1 === 0n) {
      this.state0 = 1n;
    }
  }

  /**
   * Create PRNG from base64 seed string
   */
  static fromBase64(seedBase64: string): PRNG {
    return new PRNG(base64ToUint8Array(seedBase64));
  }

  /**
   * Create PRNG from derived key
   */
  static async fromDerivedKey(
    seed: Uint8Array | string,
    domain: string,
    apiName: string
  ): Promise<PRNG> {
    const key = await deriveKey(seed, domain, apiName);
    return new PRNG(key);
  }

  /**
   * Generate next random 64-bit unsigned integer
   */
  nextBigInt(): bigint {
    const M = PRNG.MASK64;
    let s1 = this.state0;
    const s0 = this.state1;

    this.state0 = s0;
    // Mask after left shift to prevent BigInt from growing unbounded
    // (JavaScript BigInt doesn't wrap at 64 bits like C's uint64_t)
    s1 ^= (s1 << 23n) & M;
    s1 ^= s1 >> 17n;
    s1 ^= s0;
    s1 ^= s0 >> 26n;
    this.state1 = s1 & M;

    return (this.state0 + this.state1) & M;
  }

  /**
   * Generate random number in [0, 1)
   */
  nextFloat(): number {
    const bigInt = this.nextBigInt();
    // Use upper 53 bits for full precision
    const mantissa = Number(bigInt >> 11n);
    // Note: Can't use (1 << 53) because JS bit shifts are 32-bit
    return mantissa / 9007199254740992; // 2^53
  }

  /**
   * Generate random number in [min, max)
   */
  nextFloatRange(min: number, max: number): number {
    return min + this.nextFloat() * (max - min);
  }

  /**
   * Generate random integer in [min, max]
   */
  nextInt(min: number, max: number): number {
    return Math.floor(this.nextFloatRange(min, max + 1));
  }

  /**
   * Generate small noise value for farbling
   * Returns value in [-amount, +amount]
   */
  nextNoise(amount: number): number {
    return (this.nextFloat() - 0.5) * 2 * amount;
  }

  /**
   * Pick random element from array
   */
  pick<T>(array: T[]): T {
    return array[this.nextInt(0, array.length - 1)];
  }

  /**
   * Shuffle array in place (Fisher-Yates)
   */
  shuffle<T>(array: T[]): T[] {
    for (let i = array.length - 1; i > 0; i--) {
      const j = this.nextInt(0, i);
      [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
  }
}

/**
 * Generate a fingerprint hash for a specific API
 * Deterministic: same container + domain + api = same hash
 */
export async function generateFingerprintHash(
  containerSeed: string,
  domain: string,
  apiName: string
): Promise<string> {
  const input = `${containerSeed}:${domain}:${apiName}`;
  return sha256Hex(input);
}
