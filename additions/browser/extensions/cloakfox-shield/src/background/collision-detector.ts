/**
 * Collision Detector - Checks for fingerprint similarity between containers
 *
 * Compares assigned profiles across all containers to detect pairs that
 * share too many fingerprint signals, which could enable cross-container tracking.
 */

import type { SettingsStore } from './settings-store';
import type { ContainerManager } from './container-manager';
import type { AssignedProfileData } from '@/types';
import { ensureUniqueProfile, getAssignedProfile } from './profile-manager';

export interface CollisionResult {
  container1: { id: string; name: string };
  container2: { id: string; name: string };
  score: number; // 0-100 similarity percentage
  matches: string[]; // which signals matched
}

/** Maximum raw score from all weighted signal comparisons */
const MAX_RAW_SCORE = 90;

/** Signal weight definitions */
const SIGNAL_WEIGHTS: Record<string, number> = {
  userAgent: 25,
  platform: 10,
  screen: 15,
  language: 10,
  timezone: 10,
  hardwareConcurrency: 8,
  deviceMemory: 7,
  vendor: 5,
};

/**
 * Compare two assigned profiles and return a similarity score with matched signals.
 */
function compareProfiles(
  a: AssignedProfileData,
  b: AssignedProfileData
): { rawScore: number; matches: string[] } {
  let rawScore = 0;
  const matches: string[] = [];

  // userAgent string exact match: 25 points
  if (a.userAgent.userAgent === b.userAgent.userAgent) {
    rawScore += SIGNAL_WEIGHTS.userAgent;
    matches.push('UA');
  }

  // platform exact match: 10 points
  if (a.userAgent.platform === b.userAgent.platform) {
    rawScore += SIGNAL_WEIGHTS.platform;
    matches.push('Platform');
  }

  // screen width+height match: 15 points
  if (a.screen.width === b.screen.width && a.screen.height === b.screen.height) {
    rawScore += SIGNAL_WEIGHTS.screen;
    matches.push('Screen');
  }

  // language primary match (first 2 chars): 10 points
  const langA = (a.languages[0] || '').slice(0, 2);
  const langB = (b.languages[0] || '').slice(0, 2);
  if (langA && langA === langB) {
    rawScore += SIGNAL_WEIGHTS.language;
    matches.push('Language');
  }

  // timezone offset match: 10 points
  if (a.timezoneOffset === b.timezoneOffset) {
    rawScore += SIGNAL_WEIGHTS.timezone;
    matches.push('Timezone');
  }

  // hardwareConcurrency match: 8 points
  if (a.hardwareConcurrency === b.hardwareConcurrency) {
    rawScore += SIGNAL_WEIGHTS.hardwareConcurrency;
    matches.push('CPU');
  }

  // deviceMemory match: 7 points
  if (a.deviceMemory === b.deviceMemory) {
    rawScore += SIGNAL_WEIGHTS.deviceMemory;
    matches.push('Memory');
  }

  // vendor match: 5 points
  if (a.userAgent.vendor === b.userAgent.vendor) {
    rawScore += SIGNAL_WEIGHTS.vendor;
    matches.push('Vendor');
  }

  return { rawScore, matches };
}

export class CollisionDetector {
  private settingsStore: SettingsStore;
  private containerManager: ContainerManager;

  constructor(settingsStore: SettingsStore, containerManager: ContainerManager) {
    this.settingsStore = settingsStore;
    this.containerManager = containerManager;
  }

  /**
   * Check a single container against all others for fingerprint collisions.
   * Returns results sorted by similarity score descending.
   */
  async checkSingleContainer(containerId: string): Promise<CollisionResult[]> {
    const containers = this.containerManager.getAllContainers();
    if (containers.length < 2) return [];

    // Resolve the target container's profile
    const targetEntropy = this.settingsStore.getEntropy(containerId);
    if (!targetEntropy) return [];

    let targetAssigned = getAssignedProfile(containerId);
    if (!targetAssigned) {
      targetAssigned = await ensureUniqueProfile(targetEntropy);
    }

    const targetProfile: AssignedProfileData = {
      userAgent: {
        id: targetAssigned.userAgent.id,
        name: targetAssigned.userAgent.name,
        userAgent: targetAssigned.userAgent.userAgent,
        platform: targetAssigned.userAgent.platform,
        vendor: targetAssigned.userAgent.vendor,
        appVersion: targetAssigned.userAgent.appVersion,
        oscpu: targetAssigned.userAgent.oscpu,
        mobile: targetAssigned.userAgent.mobile,
        platformName: targetAssigned.userAgent.platformName,
        platformVersion: targetAssigned.userAgent.platformVersion,
        brands: targetAssigned.userAgent.brands,
      },
      screen: {
        width: targetAssigned.screen.width,
        height: targetAssigned.screen.height,
        availWidth: targetAssigned.screen.availWidth,
        availHeight: targetAssigned.screen.availHeight,
        colorDepth: targetAssigned.screen.colorDepth,
        pixelDepth: targetAssigned.screen.pixelDepth,
        devicePixelRatio: targetAssigned.screen.devicePixelRatio,
      },
      hardwareConcurrency: targetAssigned.hardwareConcurrency,
      deviceMemory: targetAssigned.deviceMemory,
      timezoneOffset: targetAssigned.timezoneOffset,
      languages: targetAssigned.languages,
    };

    const targetContainer = containers.find((c) => c.cookieStoreId === containerId);
    const results: CollisionResult[] = [];

    // Compare target against every other container
    for (const other of containers) {
      if (other.cookieStoreId === containerId) continue;

      let otherAssigned = getAssignedProfile(other.cookieStoreId);
      if (!otherAssigned) {
        const otherEntropy = this.settingsStore.getEntropy(other.cookieStoreId);
        if (!otherEntropy) continue;
        otherAssigned = await ensureUniqueProfile(otherEntropy);
      }

      const otherProfile: AssignedProfileData = {
        userAgent: {
          id: otherAssigned.userAgent.id,
          name: otherAssigned.userAgent.name,
          userAgent: otherAssigned.userAgent.userAgent,
          platform: otherAssigned.userAgent.platform,
          vendor: otherAssigned.userAgent.vendor,
          appVersion: otherAssigned.userAgent.appVersion,
          oscpu: otherAssigned.userAgent.oscpu,
          mobile: otherAssigned.userAgent.mobile,
          platformName: otherAssigned.userAgent.platformName,
          platformVersion: otherAssigned.userAgent.platformVersion,
          brands: otherAssigned.userAgent.brands,
        },
        screen: {
          width: otherAssigned.screen.width,
          height: otherAssigned.screen.height,
          availWidth: otherAssigned.screen.availWidth,
          availHeight: otherAssigned.screen.availHeight,
          colorDepth: otherAssigned.screen.colorDepth,
          pixelDepth: otherAssigned.screen.pixelDepth,
          devicePixelRatio: otherAssigned.screen.devicePixelRatio,
        },
        hardwareConcurrency: otherAssigned.hardwareConcurrency,
        deviceMemory: otherAssigned.deviceMemory,
        timezoneOffset: otherAssigned.timezoneOffset,
        languages: otherAssigned.languages,
      };

      const { rawScore, matches } = compareProfiles(targetProfile, otherProfile);
      const score = Math.round((rawScore / MAX_RAW_SCORE) * 100);

      results.push({
        container1: { id: containerId, name: targetContainer?.name || 'Unknown' },
        container2: { id: other.cookieStoreId, name: other.name },
        score,
        matches,
      });
    }

    results.sort((a, b) => b.score - a.score);
    return results;
  }

  /**
   * Check all container pairs for fingerprint collisions.
   * Returns results sorted by similarity score descending.
   */
  async checkAllContainers(): Promise<CollisionResult[]> {
    const containers = this.containerManager.getAllContainers();
    if (containers.length < 2) return [];

    // Resolve assigned profiles for every container
    const profiles = new Map<string, AssignedProfileData>();

    for (const container of containers) {
      const id = container.cookieStoreId;

      // Try cached profile first
      let assigned = getAssignedProfile(id);
      if (!assigned) {
        const entropy = this.settingsStore.getEntropy(id);
        if (!entropy) continue;
        assigned = await ensureUniqueProfile(entropy);
      }

      // Convert AssignedProfile -> AssignedProfileData (same shape used by UI)
      profiles.set(id, {
        userAgent: {
          id: assigned.userAgent.id,
          name: assigned.userAgent.name,
          userAgent: assigned.userAgent.userAgent,
          platform: assigned.userAgent.platform,
          vendor: assigned.userAgent.vendor,
          appVersion: assigned.userAgent.appVersion,
          oscpu: assigned.userAgent.oscpu,
          mobile: assigned.userAgent.mobile,
          platformName: assigned.userAgent.platformName,
          platformVersion: assigned.userAgent.platformVersion,
          brands: assigned.userAgent.brands,
        },
        screen: {
          width: assigned.screen.width,
          height: assigned.screen.height,
          availWidth: assigned.screen.availWidth,
          availHeight: assigned.screen.availHeight,
          colorDepth: assigned.screen.colorDepth,
          pixelDepth: assigned.screen.pixelDepth,
          devicePixelRatio: assigned.screen.devicePixelRatio,
        },
        hardwareConcurrency: assigned.hardwareConcurrency,
        deviceMemory: assigned.deviceMemory,
        timezoneOffset: assigned.timezoneOffset,
        languages: assigned.languages,
      });
    }

    const ids = Array.from(profiles.keys());
    const results: CollisionResult[] = [];

    // Compare every unique pair
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const idA = ids[i];
        const idB = ids[j];
        const profileA = profiles.get(idA)!;
        const profileB = profiles.get(idB)!;

        const { rawScore, matches } = compareProfiles(profileA, profileB);
        const score = Math.round((rawScore / MAX_RAW_SCORE) * 100);

        const containerA = containers.find((c) => c.cookieStoreId === idA);
        const containerB = containers.find((c) => c.cookieStoreId === idB);

        results.push({
          container1: { id: idA, name: containerA?.name || 'Unknown' },
          container2: { id: idB, name: containerB?.name || 'Unknown' },
          score,
          matches,
        });
      }
    }

    // Sort by score descending
    results.sort((a, b) => b.score - a.score);

    return results;
  }
}
