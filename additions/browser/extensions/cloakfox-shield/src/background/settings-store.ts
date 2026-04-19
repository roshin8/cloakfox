/**
 * Settings Store - Per-container settings and entropy management
 */

import browser from 'webextension-polyfill';
import type {
  ContainerSettings,
  ContainerEntropy,
  GlobalStorage,
  IPDatabase,
} from '@/types';
import { createDefaultSettings, createDefaultIPSettings } from '@/types/settings';
import { generateSeed, uint8ArrayToBase64 } from '@/lib/crypto';
import { STORAGE_KEYS, EXTENSION_VERSION } from '@/lib/constants';

export class SettingsStore {
  private storage: GlobalStorage | null = null;

  /**
   * Initialize the settings store
   */
  async init(): Promise<void> {
    await this.load();

    // Migrate if needed
    await this.migrate();

  }

  /**
   * Load settings from storage
   */
  private async load(): Promise<void> {
    const result = await browser.storage.local.get([
      STORAGE_KEYS.CONTAINER_SETTINGS,
      STORAGE_KEYS.ENTROPY,
      STORAGE_KEYS.IP_DATABASE,
      STORAGE_KEYS.VERSION,
    ]);

    this.storage = {
      containers: (result[STORAGE_KEYS.CONTAINER_SETTINGS] as Record<string, ContainerSettings>) || {},
      entropy: (result[STORAGE_KEYS.ENTROPY] as Record<string, ContainerEntropy>) || {},
      defaults: createDefaultSettings(),
      ipDatabase: (result[STORAGE_KEYS.IP_DATABASE] as IPDatabase) || this.createDefaultIPDatabase(),
      version: (result[STORAGE_KEYS.VERSION] as string) || '0.0.0',
    };
  }

  /**
   * Create default IP database
   */
  private createDefaultIPDatabase(): IPDatabase {
    return {
      ipRecords: {},
      settings: createDefaultIPSettings(),
      exceptions: [],
      trackedDomains: [],
    };
  }

  /**
   * Save settings to storage
   */
  private async save(): Promise<void> {
    if (!this.storage) return;

    await browser.storage.local.set({
      [STORAGE_KEYS.CONTAINER_SETTINGS]: this.storage.containers,
      [STORAGE_KEYS.ENTROPY]: this.storage.entropy,
      [STORAGE_KEYS.IP_DATABASE]: this.storage.ipDatabase,
      [STORAGE_KEYS.VERSION]: EXTENSION_VERSION,
    });
  }

  /**
   * Migrate settings if needed
   */
  private async migrate(): Promise<void> {
    if (!this.storage) return;

    if (this.storage.version !== EXTENSION_VERSION) {
      // Merge new default fields into existing container settings
      // This ensures new spoofer categories/fields get added
      // and old 'block' defaults get updated to 'noise' for balanced mode
      const defaults = createDefaultSettings();

      for (const [, settings] of Object.entries(this.storage.containers)) {
        // Deep merge spoofers - add missing categories and fields from defaults
        if (settings.spoofers && defaults.spoofers) {
          for (const [cat, defaultVals] of Object.entries(defaults.spoofers)) {
            if (!(cat in settings.spoofers)) {
              // New category - add entire default
              (settings.spoofers as any)[cat] = defaultVals;
            } else {
              // Existing category - add missing fields only
              for (const [key, defaultVal] of Object.entries(defaultVals as Record<string, string>)) {
                if (!((settings.spoofers as any)[cat] as Record<string, string>)[key]) {
                  (settings.spoofers as any)[cat][key] = defaultVal;
                }
              }
            }
          }
        }

        // If balanced mode (level 2), ensure no signals are blocked
        // (old defaults had some signals as 'block' which is now only for strict mode)
        if (settings.protectionLevel === 2 && settings.spoofers) {
          for (const [cat, vals] of Object.entries(settings.spoofers)) {
            for (const [key, val] of Object.entries(vals as Record<string, string>)) {
              if (val === 'block') {
                (settings.spoofers as any)[cat][key] = 'noise';
              }
            }
          }
        }

        // Merge new header fields
        if (defaults.headers) {
          for (const [key, val] of Object.entries(defaults.headers)) {
            if (!(key in (settings.headers || {}))) {
              (settings as any).headers = { ...(settings.headers || {}), [key]: val };
            }
          }
        }
      }

      this.storage.version = EXTENSION_VERSION;
      await this.save();
    }
  }

  /**
   * Ensure settings exist for a container
   */
  async ensureContainerSettings(containerId: string): Promise<void> {
    if (!this.storage) {
      await this.load();
    }
    if (!this.storage) {
      return;
    }

    // Create settings if not exist
    if (!this.storage.containers[containerId]) {
      this.storage.containers[containerId] = createDefaultSettings();
    }

    // Create entropy if not exist
    if (!this.storage.entropy[containerId]) {
      const seed = await generateSeed();
      this.storage.entropy[containerId] = {
        cookieStoreId: containerId,
        seed: uint8ArrayToBase64(seed),
        createdAt: Date.now(),
      };
    }

    await this.save();
  }

  /**
   * Get settings for a container
   */
  getContainerSettings(containerId: string): ContainerSettings {
    if (!this.storage) {
      return createDefaultSettings();
    }

    return this.storage.containers[containerId] || createDefaultSettings();
  }

  /**
   * Get settings for a container with domain overrides applied
   */
  getSettingsForDomain(containerId: string, domain: string): ContainerSettings {
    const baseSettings = this.getContainerSettings(containerId);

    // Check for domain-specific overrides
    const domainRule = baseSettings.domainRules[domain];
    if (domainRule) {
      return this.mergeSettings(baseSettings, domainRule);
    }

    // Check for wildcard domain matches
    const parts = domain.split('.');
    for (let i = 1; i < parts.length; i++) {
      const wildcardDomain = '*.' + parts.slice(i).join('.');
      const wildcardRule = baseSettings.domainRules[wildcardDomain];
      if (wildcardRule) {
        return this.mergeSettings(baseSettings, wildcardRule);
      }
    }

    return baseSettings;
  }

  /**
   * Merge base settings with partial overrides
   */
  private mergeSettings(
    base: ContainerSettings,
    overrides: Partial<ContainerSettings>
  ): ContainerSettings {
    return {
      ...base,
      ...overrides,
      profile: { ...base.profile, ...overrides.profile },
      headers: { ...base.headers, ...overrides.headers },
      spoofers: {
        graphics: { ...base.spoofers.graphics, ...overrides.spoofers?.graphics },
        audio: { ...base.spoofers.audio, ...overrides.spoofers?.audio },
        hardware: { ...base.spoofers.hardware, ...overrides.spoofers?.hardware },
        navigator: { ...base.spoofers.navigator, ...overrides.spoofers?.navigator },
        timezone: { ...base.spoofers.timezone, ...overrides.spoofers?.timezone },
        fonts: { ...base.spoofers.fonts, ...overrides.spoofers?.fonts },
        network: { ...base.spoofers.network, ...overrides.spoofers?.network },
        timing: { ...base.spoofers.timing, ...overrides.spoofers?.timing },
        css: { ...base.spoofers.css, ...overrides.spoofers?.css },
        speech: { ...base.spoofers.speech, ...overrides.spoofers?.speech },
        permissions: { ...base.spoofers.permissions, ...overrides.spoofers?.permissions },
        storage: { ...base.spoofers.storage, ...overrides.spoofers?.storage },
        math: { ...base.spoofers.math, ...overrides.spoofers?.math },
        keyboard: { ...base.spoofers.keyboard, ...overrides.spoofers?.keyboard },
        workers: { ...base.spoofers.workers, ...overrides.spoofers?.workers },
        errors: { ...base.spoofers.errors, ...overrides.spoofers?.errors },
        rendering: { ...base.spoofers.rendering, ...overrides.spoofers?.rendering },
        intl: { ...base.spoofers.intl, ...overrides.spoofers?.intl },
        crypto: { ...base.spoofers.crypto, ...overrides.spoofers?.crypto },
        devices: { ...base.spoofers.devices, ...overrides.spoofers?.devices },
        features: { ...base.spoofers.features, ...overrides.spoofers?.features },
        payment: { ...base.spoofers.payment, ...overrides.spoofers?.payment },
      },
    };
  }

  /**
   * Update settings for a container
   */
  async updateContainerSettings(
    containerId: string,
    updates: Partial<ContainerSettings>
  ): Promise<void> {
    if (!this.storage) return;

    const current = this.getContainerSettings(containerId);
    this.storage.containers[containerId] = this.mergeSettings(current, updates);
    await this.save();
  }

  /**
   * Get entropy for a container
   */
  getEntropy(containerId: string): ContainerEntropy | undefined {
    return this.storage?.entropy[containerId];
  }

  /**
   * Rotate entropy for a container (regenerate seed)
   */
  async rotateEntropy(containerId: string): Promise<void> {
    if (!this.storage) return;

    const seed = await generateSeed();
    this.storage.entropy[containerId] = {
      cookieStoreId: containerId,
      seed: uint8ArrayToBase64(seed),
      createdAt: this.storage.entropy[containerId]?.createdAt || Date.now(),
      rotatedAt: Date.now(),
    };

    await this.save();
  }

  /**
   * Get IP database
   */
  getIPDatabase(): IPDatabase {
    return this.storage?.ipDatabase || this.createDefaultIPDatabase();
  }

  /**
   * Update IP database
   */
  async updateIPDatabase(updates: Partial<IPDatabase>): Promise<void> {
    if (!this.storage) return;

    this.storage.ipDatabase = {
      ...this.storage.ipDatabase,
      ...updates,
    };

    await this.save();
  }

  /**
   * Get all container IDs with settings
   */
  getAllContainerIds(): string[] {
    return Object.keys(this.storage?.containers || {});
  }

  /**
   * Export all settings (for backup)
   */
  exportSettings(): GlobalStorage | null {
    return this.storage;
  }

  /**
   * Import settings (from backup)
   */
  async importSettings(settings: GlobalStorage): Promise<void> {
    this.storage = settings;
    await this.save();
  }

  /**
   * Reset settings to defaults
   */
  async resetToDefaults(containerId?: string): Promise<void> {
    if (!this.storage) return;

    if (containerId) {
      this.storage.containers[containerId] = createDefaultSettings();
    } else {
      this.storage.containers = {};
      this.storage.defaults = createDefaultSettings();
    }

    await this.save();
  }
}
