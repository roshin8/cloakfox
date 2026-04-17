/**
 * FingerprintGenerator — generates coherent browser fingerprints
 * using the Bayesian network from BrowserForge/Apify fingerprint-suite.
 *
 * Ensures all fingerprint properties are statistically realistic:
 * Windows UA → Windows GPU → Windows fonts → Windows screen, etc.
 */

import { BayesianNetwork, type NetworkDefinition, type RandomFn } from './bayesian-network';
import { PRNG, base64ToUint8Array } from '@/lib/crypto';

const STRINGIFIED_PREFIX = 'STRINGIFIED:';
const MISSING_VALUE_TOKEN = 'MISSING_VALUE';

let network: BayesianNetwork | null = null;
let networkPromise: Promise<BayesianNetwork> | null = null;

/** Load the network data (lazy, cached) */
async function getNetwork(): Promise<BayesianNetwork> {
  if (network) return network;
  if (networkPromise) return networkPromise;

  networkPromise = (async () => {
    // Dynamic import for the large JSON file
    const data = await import('@/data/fingerprint-network.json');
    network = new BayesianNetwork(data as unknown as NetworkDefinition);
    return network;
  })();

  return networkPromise;
}

/** Adapt our PRNG to the RandomFn interface */
function prngToRandom(prng: PRNG): RandomFn {
  return {
    next: () => {
      // PRNG.nextInt gives integers, we need [0,1)
      return prng.nextInt(0, 2147483646) / 2147483647;
    },
  };
}

export interface GeneratedFingerprint {
  userAgent: string;
  appVersion: string;
  platform: string;
  oscpu: string;
  deviceMemory: number | null;
  hardwareConcurrency: number;
  maxTouchPoints: number;
  screen: {
    width: number;
    height: number;
    availWidth: number;
    availHeight: number;
    colorDepth: number;
    pixelDepth: number;
    devicePixelRatio: number;
    innerWidth: number;
    innerHeight: number;
    outerWidth: number;
    outerHeight: number;
  };
  videoCard: {
    vendor: string;
    renderer: string;
  };
  fonts: string[];
  audioCodecs: Record<string, string>;
  videoCodecs: Record<string, string>;
  battery: Record<string, string> | null;
  multimediaDevices: string[];
}

/**
 * Generate a coherent fingerprint from a seed.
 * Same seed always produces the same fingerprint (deterministic via seeded PRNG).
 */
export async function generateCoherentFingerprint(
  seed: string
): Promise<GeneratedFingerprint> {
  const net = await getNetwork();
  const seedBytes = base64ToUint8Array(seed);
  const prng = new PRNG(seedBytes);
  const rng = prngToRandom(prng);

  // Sample from the Bayesian network
  const raw = net.generateSample(rng);

  // Unpack stringified values
  const sample: Record<string, any> = {};
  for (const [key, value] of Object.entries(raw)) {
    if (value === MISSING_VALUE_TOKEN) {
      sample[key] = null;
    } else if (typeof value === 'string' && value.startsWith(STRINGIFIED_PREFIX)) {
      try {
        sample[key] = JSON.parse(value.slice(STRINGIFIED_PREFIX.length));
      } catch {
        sample[key] = value;
      }
    } else {
      sample[key] = value;
    }
  }

  // Parse numeric values
  const parsedMemory = parseInt(sample.deviceMemory, 10);
  const parsedTouch = parseInt(sample.maxTouchPoints, 10);
  const parsedCores = parseInt(sample.hardwareConcurrency, 10);

  return {
    userAgent: sample.userAgent || '',
    appVersion: sample.appVersion || '',
    platform: sample.platform || '',
    oscpu: sample.oscpu || '',
    deviceMemory: Number.isNaN(parsedMemory) ? null : parsedMemory,
    hardwareConcurrency: Number.isNaN(parsedCores) ? 8 : parsedCores,
    maxTouchPoints: Number.isNaN(parsedTouch) ? 0 : parsedTouch,
    screen: sample.screen || {
      width: 1920, height: 1080, availWidth: 1920, availHeight: 1040,
      colorDepth: 24, pixelDepth: 24, devicePixelRatio: 1,
      innerWidth: 1920, innerHeight: 969, outerWidth: 1920, outerHeight: 1040,
    },
    videoCard: sample.videoCard || { vendor: '', renderer: '' },
    fonts: Array.isArray(sample.fonts) ? sample.fonts : [],
    audioCodecs: sample.audioCodecs || {},
    videoCodecs: sample.videoCodecs || {},
    battery: sample.battery || null,
    multimediaDevices: Array.isArray(sample.multimediaDevices) ? sample.multimediaDevices : [],
  };
}
