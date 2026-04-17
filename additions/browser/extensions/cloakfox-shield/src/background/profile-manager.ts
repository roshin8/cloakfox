/**
 * Profile Manager - Ensures unique fingerprint profiles across containers
 *
 * Prevents the same combination of identifying properties from being
 * assigned to multiple containers, which would allow cross-container tracking.
 */

import type { ContainerEntropy } from '@/types';
import { PRNG, generateSeed, base64ToUint8Array, uint8ArrayToBase64 } from '@/lib/crypto';
import {
  ALL_PROFILES,
  type UserAgentProfile,
  getRandomProfile,
} from '@/lib/profiles/user-agents';
import { generateCoherentFingerprint } from '@/lib/bayesian';
import {
  ALL_SCREENS,
  type ScreenProfile,
  getScreenForUserAgent,
  varyScreenProfile,
} from '@/lib/profiles/screen-sizes';

/**
 * Key properties that together form a fingerprintable signature
 */
export interface FingerprintSignature {
  userAgentId: string;
  screenWidth: number;
  screenHeight: number;
  devicePixelRatio: number;
  hardwareConcurrency: number;
  deviceMemory: number;
  timezoneOffset: number;
  languages: string;
}

/**
 * Assigned profile for a container
 */
export interface AssignedProfile {
  userAgent: UserAgentProfile;
  screen: ScreenProfile;
  hardwareConcurrency: number;
  deviceMemory: number;
  timezoneOffset: number;
  languages: string[];
  signature: string; // Hash of the signature for quick comparison
}

/**
 * Storage for assigned profiles
 */
interface ProfileRegistry {
  assignments: Record<string, AssignedProfile>; // keyed by cookieStoreId
  usedSignatures: Set<string>; // Set of signature hashes in use
}

// In-memory registry (loaded from storage on init)
let registry: ProfileRegistry = {
  assignments: {},
  usedSignatures: new Set(),
};

// Common timezone offsets
const TIMEZONE_OFFSETS = [
  -480, -420, -360, -300, -240, 0, 60, 120, 180, 330, 480, 540, 600,
];

// Common language combinations
const LANGUAGE_SETS = [
  ['en-US', 'en'],
  ['en-GB', 'en'],
  ['en-US'],
  ['de-DE', 'de', 'en-US', 'en'],
  ['fr-FR', 'fr', 'en-US', 'en'],
  ['es-ES', 'es', 'en-US', 'en'],
  ['pt-BR', 'pt', 'en-US', 'en'],
  ['ja-JP', 'ja', 'en-US', 'en'],
  ['zh-CN', 'zh', 'en-US', 'en'],
  ['ko-KR', 'ko', 'en-US', 'en'],
  ['ru-RU', 'ru', 'en-US', 'en'],
  ['it-IT', 'it', 'en-US', 'en'],
  ['nl-NL', 'nl', 'en-US', 'en'],
  ['pl-PL', 'pl', 'en-US', 'en'],
];

// Hardware concurrency options
const HARDWARE_CONCURRENCY = [2, 4, 6, 8, 12, 16];

// Device memory options (GB)
const DEVICE_MEMORY = [2, 4, 8, 16, 32];

/**
 * Generate a signature hash for quick comparison
 */
function generateSignatureHash(sig: FingerprintSignature): string {
  const str = `${sig.userAgentId}|${sig.screenWidth}x${sig.screenHeight}|${sig.devicePixelRatio}|${sig.hardwareConcurrency}|${sig.deviceMemory}|${sig.timezoneOffset}|${sig.languages}`;
  // Simple hash for comparison (not cryptographic)
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return hash.toString(16);
}

/**
 * Check if a signature is already in use
 */
function isSignatureInUse(sig: FingerprintSignature): boolean {
  const hash = generateSignatureHash(sig);
  return registry.usedSignatures.has(hash);
}

/**
 * Generate a unique profile for a container
 * Tries up to maxAttempts times to find a non-colliding combination
 */
export function generateUniqueProfile(
  entropy: ContainerEntropy,
  maxAttempts: number = 100
): AssignedProfile {
  const seedBytes = base64ToUint8Array(entropy.seed);

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    // Create a modified seed for each attempt
    const attemptSeed = new Uint8Array(seedBytes.length);
    attemptSeed.set(seedBytes);
    // Mix in the attempt number
    attemptSeed[0] ^= attempt;
    attemptSeed[1] ^= attempt >> 8;

    const prng = new PRNG(attemptSeed);

    // Select profile components
    const userAgent = getRandomProfile(prng, { desktopOnly: true });
    const baseScreen = getScreenForUserAgent(prng, userAgent.mobile, userAgent.platformName);
    const screen = varyScreenProfile(baseScreen, prng);
    const hardwareConcurrency = prng.pick(HARDWARE_CONCURRENCY);
    const deviceMemory = prng.pick(DEVICE_MEMORY);
    const timezoneOffset = prng.pick(TIMEZONE_OFFSETS);
    const languages = prng.pick(LANGUAGE_SETS);

    // Build signature
    const signature: FingerprintSignature = {
      userAgentId: userAgent.id,
      screenWidth: screen.width,
      screenHeight: screen.height,
      devicePixelRatio: screen.devicePixelRatio,
      hardwareConcurrency,
      deviceMemory,
      timezoneOffset,
      languages: languages.join(','),
    };

    // Check for collision
    if (!isSignatureInUse(signature)) {
      const signatureHash = generateSignatureHash(signature);

      const profile: AssignedProfile = {
        userAgent,
        screen,
        hardwareConcurrency,
        deviceMemory,
        timezoneOffset,
        languages,
        signature: signatureHash,
      };

      return profile;
    }

    console.log(
      `[ProfileManager] Collision detected on attempt ${attempt + 1}, retrying...`
    );
  }

  // If we exhaust attempts, force a unique profile by adding random suffix
  console.warn(
    '[ProfileManager] Could not find unique profile after max attempts, forcing uniqueness'
  );

  const prng = new PRNG(seedBytes);
  const userAgent = getRandomProfile(prng, { desktopOnly: true });
  const baseScreen = getScreenForUserAgent(prng, userAgent.mobile, userAgent.platformName);

  // Add random variation to force uniqueness
  const forcedScreen: ScreenProfile = {
    ...baseScreen,
    availHeight: baseScreen.availHeight - Math.floor(Math.random() * 50),
    devicePixelRatio:
      baseScreen.devicePixelRatio + (Math.random() - 0.5) * 0.01,
  };

  const profile: AssignedProfile = {
    userAgent,
    screen: forcedScreen,
    hardwareConcurrency: prng.pick(HARDWARE_CONCURRENCY),
    deviceMemory: prng.pick(DEVICE_MEMORY),
    timezoneOffset: prng.pick(TIMEZONE_OFFSETS),
    languages: prng.pick(LANGUAGE_SETS),
    signature: `forced-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  };

  return profile;
}

/**
 * Generate a profile using the Bayesian network for statistical coherence.
 * Falls back to the PRNG approach if the network fails to load.
 */
export async function generateProfileWithBayesian(
  entropy: ContainerEntropy
): Promise<AssignedProfile> {
  try {
    const fp = await generateCoherentFingerprint(entropy.seed);

    // Map Bayesian output to our AssignedProfile format
    // Find matching UA profile from our profiles list, or create one from the Bayesian output
    const prng = new PRNG(base64ToUint8Array(entropy.seed));
    const matchingUA = ALL_PROFILES.find(p => p.userAgent === fp.userAgent);
    const userAgent: UserAgentProfile = matchingUA || {
      id: `bayesian-${prng.nextInt(0, 99999)}`,
      name: fp.userAgent.split('/').pop() || 'Unknown',
      userAgent: fp.userAgent,
      platform: fp.platform,
      vendor: '',
      appVersion: fp.appVersion,
      oscpu: fp.oscpu,
      mobile: false,
      platformName: fp.platform.includes('Win') ? 'Windows' : fp.platform.includes('Mac') ? 'macOS' : 'Linux',
      platformVersion: '',
    };

    const screen: ScreenProfile = {
      width: fp.screen.width,
      height: fp.screen.height,
      availWidth: fp.screen.availWidth,
      availHeight: fp.screen.availHeight,
      colorDepth: fp.screen.colorDepth,
      pixelDepth: fp.screen.pixelDepth,
      devicePixelRatio: fp.screen.devicePixelRatio,
    };

    const signature = `bayesian-${fp.userAgent.slice(-20)}-${fp.screen.width}x${fp.screen.height}`;

    return {
      userAgent,
      screen,
      hardwareConcurrency: fp.hardwareConcurrency,
      deviceMemory: fp.deviceMemory || prng.pick(DEVICE_MEMORY),
      timezoneOffset: prng.pick(TIMEZONE_OFFSETS),
      languages: prng.pick(LANGUAGE_SETS),
      signature,
    };
  } catch (e) {
    console.warn('[ProfileManager] Bayesian network failed, falling back to PRNG:', e);
    return generateUniqueProfile(entropy);
  }
}

/**
 * Register a profile assignment for a container
 */
export function registerProfile(
  cookieStoreId: string,
  profile: AssignedProfile
): void {
  // Remove old assignment if exists
  const oldProfile = registry.assignments[cookieStoreId];
  if (oldProfile) {
    registry.usedSignatures.delete(oldProfile.signature);
  }

  // Register new assignment
  registry.assignments[cookieStoreId] = profile;
  registry.usedSignatures.add(profile.signature);

  // Persist to storage
  saveRegistry();

  console.log(
    `[ProfileManager] Registered profile for container ${cookieStoreId}:`,
    profile.userAgent.name,
    `${profile.screen.width}x${profile.screen.height}`
  );
}

/**
 * Get assigned profile for a container
 */
export function getAssignedProfile(
  cookieStoreId: string
): AssignedProfile | undefined {
  return registry.assignments[cookieStoreId];
}

/**
 * Remove profile assignment when container is deleted
 */
export function unregisterProfile(cookieStoreId: string): void {
  const profile = registry.assignments[cookieStoreId];
  if (profile) {
    registry.usedSignatures.delete(profile.signature);
    delete registry.assignments[cookieStoreId];
    saveRegistry();
    console.log(`[ProfileManager] Unregistered profile for container ${cookieStoreId}`);
  }
}

/**
 * Get all assigned profiles (for UI display)
 */
export function getAllAssignedProfiles(): Record<string, AssignedProfile> {
  return { ...registry.assignments };
}

/**
 * Check how many unique profiles are still available
 */
export function getAvailableProfileCount(): number {
  const totalCombinations =
    ALL_PROFILES.length *
    ALL_SCREENS.length *
    HARDWARE_CONCURRENCY.length *
    DEVICE_MEMORY.length *
    TIMEZONE_OFFSETS.length *
    LANGUAGE_SETS.length;

  return totalCombinations - registry.usedSignatures.size;
}

/**
 * Save registry to browser storage
 */
async function saveRegistry(): Promise<void> {
  try {
    const data = {
      assignments: registry.assignments,
      usedSignatures: Array.from(registry.usedSignatures),
    };
    await browser.storage.local.set({ profileRegistry: data });
  } catch (error) {
    console.error('[ProfileManager] Failed to save registry:', error);
  }
}

/**
 * Load registry from browser storage
 */
export async function loadRegistry(): Promise<void> {
  try {
    const result = await browser.storage.local.get('profileRegistry');
    if (result.profileRegistry) {
      registry = {
        assignments: result.profileRegistry.assignments || {},
        usedSignatures: new Set(result.profileRegistry.usedSignatures || []),
      };
      console.log(
        `[ProfileManager] Loaded ${Object.keys(registry.assignments).length} profile assignments`
      );
    }
  } catch (error) {
    console.error('[ProfileManager] Failed to load registry:', error);
  }
}

/**
 * Initialize profile manager
 */
export async function initProfileManager(): Promise<void> {
  await loadRegistry();

  // Clean up orphaned assignments (containers that no longer exist)
  try {
    const containers = await browser.contextualIdentities.query({});
    const validIds = new Set(containers.map((c) => c.cookieStoreId));
    validIds.add('firefox-default'); // Default container

    let cleaned = 0;
    for (const cookieStoreId of Object.keys(registry.assignments)) {
      if (!validIds.has(cookieStoreId)) {
        unregisterProfile(cookieStoreId);
        cleaned++;
      }
    }

    if (cleaned > 0) {
      console.log(`[ProfileManager] Cleaned up ${cleaned} orphaned profile assignments`);
    }
  } catch (error) {
    console.error('[ProfileManager] Failed to clean up orphaned assignments:', error);
  }
}

/**
 * Get or create profile for a container
 * This is the main entry point - ensures a unique profile exists
 */
export async function ensureUniqueProfile(
  entropy: ContainerEntropy
): Promise<AssignedProfile> {
  const existing = getAssignedProfile(entropy.cookieStoreId);
  if (existing) {
    return existing;
  }

  // Generate new unique profile — try Bayesian network first for coherent fingerprints
  const profile = await generateProfileWithBayesian(entropy);
  registerProfile(entropy.cookieStoreId, profile);

  return profile;
}
