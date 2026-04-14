import { describe, it, expect } from 'vitest';
import { PRNG, sha256, generateFallbackSeed } from '../../src/lib/crypto';

describe('sha256', () => {
  it('produces consistent hashes', async () => {
    const hash1 = await sha256('hello');
    const hash2 = await sha256('hello');
    expect(hash1).toBe(hash2);
    expect(hash1).toHaveLength(64);
  });

  it('produces different hashes for different inputs', async () => {
    const hash1 = await sha256('hello');
    const hash2 = await sha256('world');
    expect(hash1).not.toBe(hash2);
  });
});

describe('PRNG', () => {
  it('is deterministic given same seeds', () => {
    const rng1 = new PRNG(123n, 456n);
    const rng2 = new PRNG(123n, 456n);

    for (let i = 0; i < 100; i++) {
      expect(rng1.next()).toBe(rng2.next());
    }
  });

  it('produces different sequences for different seeds', () => {
    const rng1 = new PRNG(123n, 456n);
    const rng2 = new PRNG(789n, 101n);

    const seq1 = Array.from({ length: 10 }, () => rng1.next());
    const seq2 = Array.from({ length: 10 }, () => rng2.next());
    expect(seq1).not.toEqual(seq2);
  });

  it('nextInt returns values in range', () => {
    const rng = new PRNG(42n, 84n);
    for (let i = 0; i < 1000; i++) {
      const val = rng.nextInt(1, 100);
      expect(val).toBeGreaterThanOrEqual(1);
      expect(val).toBeLessThanOrEqual(100);
    }
  });

  it('nextFloat returns values in [0, 1)', () => {
    const rng = new PRNG(42n, 84n);
    for (let i = 0; i < 1000; i++) {
      const val = rng.nextFloat();
      expect(val).toBeGreaterThanOrEqual(0);
      expect(val).toBeLessThan(1);
    }
  });

  it('fromDerivedKey is deterministic', async () => {
    const rng1 = await PRNG.fromDerivedKey('seed123', 'example.com', 'master');
    const rng2 = await PRNG.fromDerivedKey('seed123', 'example.com', 'master');
    expect(rng1.next()).toBe(rng2.next());
  });

  it('fromDerivedKey with different domains produces different sequences', async () => {
    const rng1 = await PRNG.fromDerivedKey('seed123', 'example.com', 'master');
    const rng2 = await PRNG.fromDerivedKey('seed123', 'other.com', 'master');
    // Very unlikely to be equal
    expect(rng1.nextInt(1, 2147483647)).not.toBe(rng2.nextInt(1, 2147483647));
  });

  it('fromDerivedKey with different seeds produces different sequences', async () => {
    const rng1 = await PRNG.fromDerivedKey('seed-container-1', 'example.com', 'master');
    const rng2 = await PRNG.fromDerivedKey('seed-container-2', 'example.com', 'master');
    expect(rng1.nextInt(1, 2147483647)).not.toBe(rng2.nextInt(1, 2147483647));
  });

  it('pick selects from array', () => {
    const rng = new PRNG(42n, 84n);
    const arr = ['a', 'b', 'c', 'd', 'e'];
    for (let i = 0; i < 100; i++) {
      expect(arr).toContain(rng.pick(arr));
    }
  });

  it('shuffle preserves all elements', () => {
    const rng = new PRNG(42n, 84n);
    const arr = [1, 2, 3, 4, 5];
    const shuffled = rng.shuffle([...arr]);
    expect(shuffled.sort()).toEqual(arr.sort());
  });
});

describe('generateFallbackSeed', () => {
  it('is deterministic for same domain', async () => {
    const seed1 = await generateFallbackSeed('example.com');
    const seed2 = await generateFallbackSeed('example.com');
    expect(seed1).toBe(seed2);
  });

  it('differs for different domains', async () => {
    const seed1 = await generateFallbackSeed('example.com');
    const seed2 = await generateFallbackSeed('other.com');
    expect(seed1).not.toBe(seed2);
  });
});
