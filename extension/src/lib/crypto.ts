/**
 * Cryptographic primitives for Cloakfox Shield.
 *
 * xorshift128+ PRNG seeded via SHA-256 derivation.
 * All fingerprint randomization MUST use this — never Math.random().
 */

/** xorshift128+ PRNG — fast, deterministic, good distribution */
export class PRNG {
  private state0: bigint;
  private state1: bigint;

  constructor(seed0: bigint, seed1: bigint) {
    // Ensure non-zero state
    this.state0 = seed0 || 1n;
    this.state1 = seed1 || 2n;
  }

  /** Create a PRNG from a derived key: SHA-256(seed + separator + context) */
  static async fromDerivedKey(
    seed: string,
    context: string,
    purpose: string
  ): Promise<PRNG> {
    const key = `${seed}|${context}|${purpose}`;
    const hash = await sha256(key);
    const seed0 = BigInt('0x' + hash.slice(0, 16));
    const seed1 = BigInt('0x' + hash.slice(16, 32));
    return new PRNG(seed0, seed1);
  }

  /** Next 64-bit unsigned integer */
  next(): bigint {
    let s1 = this.state0;
    const s0 = this.state1;
    const result = (s0 + s1) & 0xFFFFFFFFFFFFFFFFn;
    this.state0 = s0;
    s1 ^= s1 << 23n;
    s1 ^= s1 >> 17n;
    s1 ^= s0;
    s1 ^= s0 >> 26n;
    this.state1 = s1;
    return result;
  }

  /** Random integer in [min, max] inclusive */
  nextInt(min: number, max: number): number {
    const range = BigInt(max - min + 1);
    return min + Number(this.next() % range);
  }

  /** Random float in [0, 1) */
  nextFloat(): number {
    return Number(this.next() & 0x1FFFFFFFFFFFFFn) / 2 ** 53;
  }

  /** Select a random element from an array */
  pick<T>(arr: readonly T[]): T {
    return arr[this.nextInt(0, arr.length - 1)]!;
  }

  /** Shuffle array in place (Fisher-Yates) */
  shuffle<T>(arr: T[]): T[] {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = this.nextInt(0, i);
      [arr[i], arr[j]] = [arr[j]!, arr[i]!];
    }
    return arr;
  }
}

/** SHA-256 hash, returns hex string */
export async function sha256(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const buffer = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/** Generate a random entropy seed (for new containers) */
export function generateEntropySeed(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/** Generate a fallback seed from domain only (no container context) */
export async function generateFallbackSeed(domain: string): Promise<string> {
  return sha256(`cloakfox-fallback|${domain}`);
}
