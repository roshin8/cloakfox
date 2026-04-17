/**
 * Container Manager - Detects and tracks Firefox container context
 */

import browser from 'webextension-polyfill';
import type { ContainerIdentity } from '@/types';
import type { SettingsStore } from './settings-store';
import { CollisionDetector } from './collision-detector';
import { DEFAULT_COOKIE_STORE_ID, PRIVATE_COOKIE_STORE_ID } from '@/lib/constants';

export class ContainerManager {
  private settingsStore: SettingsStore;
  private containers: Map<string, ContainerIdentity> = new Map();
  private tabContainers: Map<number, string> = new Map();

  constructor(settingsStore: SettingsStore) {
    this.settingsStore = settingsStore;
  }

  /**
   * Initialize container manager
   */
  async init(): Promise<void> {
    // Load all containers
    await this.refreshContainers();

    // Listen for container changes
    this.setupContainerListeners();

    // Listen for tab changes
    this.setupTabListeners();

    console.log('[ContainerManager] Initialized with', this.containers.size, 'containers');
  }

  /**
   * Refresh the list of containers
   */
  async refreshContainers(): Promise<void> {
    try {
      const identities = await browser.contextualIdentities.query({});

      this.containers.clear();

      // Add default container
      this.containers.set(DEFAULT_COOKIE_STORE_ID, {
        cookieStoreId: DEFAULT_COOKIE_STORE_ID,
        name: 'Default',
        color: 'toolbar',
        colorCode: '#7c7c7d',
        icon: 'circle',
      });

      // Add user containers
      for (const identity of identities) {
        this.containers.set(identity.cookieStoreId, {
          cookieStoreId: identity.cookieStoreId,
          name: identity.name,
          color: identity.color,
          colorCode: identity.colorCode,
          icon: identity.icon,
        });
      }

      // Ensure settings exist for all containers
      for (const containerId of this.containers.keys()) {
        await this.settingsStore.ensureContainerSettings(containerId);
      }
    } catch (error) {
      console.error('[ContainerManager] Failed to refresh containers:', error);
    }
  }

  /**
   * Set up listeners for container lifecycle events
   */
  private setupContainerListeners(): void {
    // New container created
    browser.contextualIdentities.onCreated.addListener(async (changeInfo) => {
      const identity = changeInfo.contextualIdentity;
      this.containers.set(identity.cookieStoreId, {
        cookieStoreId: identity.cookieStoreId,
        name: identity.name,
        color: identity.color,
        colorCode: identity.colorCode,
        icon: identity.icon,
      });

      // Create settings for new container
      await this.settingsStore.ensureContainerSettings(identity.cookieStoreId);

      console.log('[ContainerManager] Container created:', identity.name);

      // Auto-protect: check similarity and rotate entropy if needed
      await this.autoProtectContainer(identity.cookieStoreId, identity.name);
    });

    // Container updated
    browser.contextualIdentities.onUpdated.addListener((changeInfo) => {
      const identity = changeInfo.contextualIdentity;
      this.containers.set(identity.cookieStoreId, {
        cookieStoreId: identity.cookieStoreId,
        name: identity.name,
        color: identity.color,
        colorCode: identity.colorCode,
        icon: identity.icon,
      });

      console.log('[ContainerManager] Container updated:', identity.name);
    });

    // Container removed
    browser.contextualIdentities.onRemoved.addListener(async (changeInfo) => {
      const identity = changeInfo.contextualIdentity;
      this.containers.delete(identity.cookieStoreId);

      // Optionally clean up settings
      // await this.settingsStore.removeContainerSettings(identity.cookieStoreId);

      console.log('[ContainerManager] Container removed:', identity.name);
    });
  }

  /**
   * Set up listeners for tab events
   */
  private setupTabListeners(): void {
    // Track tab creation
    browser.tabs.onCreated.addListener((tab) => {
      if (tab.id && tab.cookieStoreId) {
        this.tabContainers.set(tab.id, tab.cookieStoreId);
      }
    });

    // Track tab updates
    browser.tabs.onUpdated.addListener((tabId, _changeInfo, tab) => {
      if (tab.cookieStoreId) {
        this.tabContainers.set(tabId, tab.cookieStoreId);
      }
    });

    // Clean up on tab close
    browser.tabs.onRemoved.addListener((tabId) => {
      this.tabContainers.delete(tabId);
    });
  }

  /**
   * Auto-protect a newly created container by checking fingerprint similarity
   * against existing containers and rotating entropy if too similar.
   */
  private async autoProtectContainer(containerId: string, containerName: string): Promise<void> {
    try {
      const ipDatabase = this.settingsStore.getIPDatabase();
      const ipSettings = ipDatabase.settings;

      if (!ipSettings.autoProtectNewContainers) {
        return;
      }

      const threshold = ipSettings.similarityThreshold;
      const detector = new CollisionDetector(this.settingsStore, this);
      const maxAttempts = 5;

      for (let attempt = 0; attempt < maxAttempts; attempt++) {
        const results = await detector.checkSingleContainer(containerId);
        const highSimilarity = results.find((r) => r.score > threshold);

        if (!highSimilarity) {
          // No collisions above threshold - success
          try {
            await browser.notifications.create(`auto-protect-${containerId}`, {
              type: 'basic',
              title: 'Cloakfox Shield',
              message: attempt === 0
                ? `Container "${containerName}" has a unique fingerprint.`
                : `Container "${containerName}" fingerprint rotated ${attempt} time(s) to ensure uniqueness.`,
            });
          } catch {}
          return;
        }

        // Similarity too high - rotate entropy
        console.log(
          `[ContainerManager] Auto-protect: "${containerName}" similarity ${highSimilarity.score}% with "${highSimilarity.container2.name}" (attempt ${attempt + 1}/${maxAttempts})`
        );
        await this.settingsStore.rotateEntropy(containerId);
      }

      // Exhausted attempts - warn the user
      try {
        await browser.notifications.create(`auto-protect-${containerId}`, {
          type: 'basic',
          title: 'Cloakfox Shield - Warning',
          message: `Container "${containerName}" may still share fingerprint signals with another container after ${maxAttempts} rotation attempts.`,
        });
      } catch {}
    } catch (error) {
      console.error('[ContainerManager] Auto-protect failed:', error);
    }
  }

  /**
   * Get container ID for a tab
   */
  async getContainerForTab(tabId: number): Promise<string> {
    // Check cache first
    const cached = this.tabContainers.get(tabId);
    if (cached) {
      return cached;
    }

    // Fetch from API
    try {
      const tab = await browser.tabs.get(tabId);
      const containerId = tab.cookieStoreId || DEFAULT_COOKIE_STORE_ID;
      this.tabContainers.set(tabId, containerId);
      return containerId;
    } catch {
      return DEFAULT_COOKIE_STORE_ID;
    }
  }

  /**
   * Get all containers
   */
  getAllContainers(): ContainerIdentity[] {
    return Array.from(this.containers.values());
  }

  /**
   * Get a specific container by ID
   */
  getContainer(cookieStoreId: string): ContainerIdentity | undefined {
    return this.containers.get(cookieStoreId);
  }

  /**
   * Check if a cookie store ID is a private browsing container
   */
  isPrivateContainer(cookieStoreId: string): boolean {
    return cookieStoreId === PRIVATE_COOKIE_STORE_ID;
  }

  /**
   * Check if a cookie store ID is the default container
   */
  isDefaultContainer(cookieStoreId: string): boolean {
    return cookieStoreId === DEFAULT_COOKIE_STORE_ID;
  }

  /**
   * Get container name by ID
   */
  getContainerName(cookieStoreId: string): string {
    const container = this.containers.get(cookieStoreId);
    if (container) {
      return container.name;
    }

    if (cookieStoreId === PRIVATE_COOKIE_STORE_ID) {
      return 'Private Browsing';
    }

    return 'Unknown';
  }
}
