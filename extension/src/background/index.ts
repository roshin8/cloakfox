/**
 * Background entry point — initializes all background services.
 */

import { ConfigInjector } from './config-injector';
import { getProfileForContainer } from './profile-manager';
import { getSettingsForDomain } from './settings-store';
import { generateEntropySeed } from '@/lib/crypto';
import { STORAGE_KEYS } from '@/constants';

/** In-memory entropy cache (persisted to storage) */
const entropyCache = new Map<string, string>();

/** Initialize entropy for a container, generating if needed */
async function ensureEntropy(cookieStoreId: string): Promise<string> {
  const cached = entropyCache.get(cookieStoreId);
  if (cached) return cached;

  // Check storage
  const stored = await browser.storage.local.get(STORAGE_KEYS.CONTAINER_ENTROPY);
  const allEntropy = (stored[STORAGE_KEYS.CONTAINER_ENTROPY] ?? {}) as Record<
    string,
    string
  >;

  if (allEntropy[cookieStoreId]) {
    entropyCache.set(cookieStoreId, allEntropy[cookieStoreId]);
    return allEntropy[cookieStoreId];
  }

  // Generate new entropy
  const seed = generateEntropySeed();
  allEntropy[cookieStoreId] = seed;
  await browser.storage.local.set({ [STORAGE_KEYS.CONTAINER_ENTROPY]: allEntropy });
  entropyCache.set(cookieStoreId, seed);
  return seed;
}

/** Get the container (cookie store) for a tab */
async function getContainerForTab(tabId: number): Promise<string> {
  const tab = await browser.tabs.get(tabId);
  return tab.cookieStoreId ?? 'firefox-default';
}

// Initialize config injector with real implementations
const _injector = new ConfigInjector({
  getContainerForTab,
  getEntropySeed: ensureEntropy,
  getAssignedProfile: async (cookieStoreId) => {
    const entropy = await ensureEntropy(cookieStoreId);
    return getProfileForContainer(cookieStoreId, entropy);
  },
  getSettingsForDomain: async (cookieStoreId, domain) => {
    return getSettingsForDomain(cookieStoreId, domain);
  },
});

// Log startup
console.log('[Cloakfox Shield] Background initialized');
