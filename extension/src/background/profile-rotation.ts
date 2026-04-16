/**
 * Profile Rotation - Automatic fingerprint rotation on schedule
 *
 * Rotates container entropy seeds on a configurable schedule to
 * prevent long-term fingerprint correlation.
 */

import browser from 'webextension-polyfill';
import type { SettingsStore } from './settings-store';
import { backgroundLogger } from '@/lib/logger';

const logger = backgroundLogger.child('ProfileRotation');

/**
 * Rotation schedule options
 */
export type RotationSchedule = 'off' | 'hourly' | 'daily' | 'weekly' | 'session';

/**
 * Rotation settings
 */
export interface RotationSettings {
  enabled: boolean;
  schedule: RotationSchedule;
  lastRotation: Record<string, number>; // containerId -> timestamp
  rotateOnStartup: boolean;
}

/**
 * Default rotation settings
 */
export const DEFAULT_ROTATION_SETTINGS: RotationSettings = {
  enabled: false,
  schedule: 'daily',
  lastRotation: {},
  rotateOnStartup: false,
};

/**
 * Schedule intervals in milliseconds
 */
const SCHEDULE_INTERVALS: Record<RotationSchedule, number> = {
  off: 0,
  hourly: 60 * 60 * 1000,
  daily: 24 * 60 * 60 * 1000,
  weekly: 7 * 24 * 60 * 60 * 1000,
  session: 0, // Special case: rotate on browser restart
};

/**
 * Profile rotation manager
 */
const ALARM_NAME = 'containershield-rotation-check';

export class ProfileRotation {
  private settingsStore: SettingsStore;
  private settings: RotationSettings = DEFAULT_ROTATION_SETTINGS;

  constructor(settingsStore: SettingsStore) {
    this.settingsStore = settingsStore;
  }

  /**
   * Initialize profile rotation
   */
  async init(): Promise<void> {
    await this.loadSettings();

    // Listen for alarm events (survives event page restarts)
    browser.alarms.onAlarm.addListener((alarm) => {
      if (alarm.name === ALARM_NAME) {
        this.checkAndRotate();
      }
    });

    if (this.settings.enabled) {
      if (this.settings.schedule === 'session' || this.settings.rotateOnStartup) {
        await this.rotateAllContainers();
      } else {
        await this.checkAndRotate();
      }

      this.startPeriodicCheck();
    }

    logger.info('Profile rotation initialized', { enabled: this.settings.enabled });
  }

  /**
   * Load rotation settings from storage
   */
  private async loadSettings(): Promise<void> {
    const result = await browser.storage.local.get('rotationSettings');
    this.settings = result.rotationSettings || DEFAULT_ROTATION_SETTINGS;
  }

  /**
   * Save rotation settings to storage
   */
  private async saveSettings(): Promise<void> {
    await browser.storage.local.set({ rotationSettings: this.settings });
  }

  /**
   * Update rotation settings
   */
  async updateSettings(updates: Partial<RotationSettings>): Promise<void> {
    this.settings = { ...this.settings, ...updates };
    await this.saveSettings();

    // Restart periodic check if enabled changed
    if ('enabled' in updates || 'schedule' in updates) {
      this.stopPeriodicCheck();
      if (this.settings.enabled && this.settings.schedule !== 'off') {
        this.startPeriodicCheck();
      }
    }

    logger.info('Rotation settings updated', updates);
  }

  /**
   * Get current rotation settings
   */
  getSettings(): RotationSettings {
    return { ...this.settings };
  }

  /**
   * Start periodic rotation check using browser.alarms (survives event page restarts)
   */
  private startPeriodicCheck(): void {
    if (this.settings.schedule === 'off' || this.settings.schedule === 'session') {
      return;
    }

    const periodMinutes = Math.min(
      SCHEDULE_INTERVALS[this.settings.schedule] / 60000,
      60 // Check at least every hour
    );

    browser.alarms.create(ALARM_NAME, { periodInMinutes: periodMinutes });
    logger.debug('Started periodic rotation alarm', { periodMinutes });
  }

  /**
   * Stop periodic rotation check
   */
  private stopPeriodicCheck(): void {
    browser.alarms.clear(ALARM_NAME);
  }

  /**
   * Check if rotation is needed and perform it
   */
  private async checkAndRotate(): Promise<void> {
    const now = Date.now();
    const interval = SCHEDULE_INTERVALS[this.settings.schedule];

    if (interval === 0) return;

    const containerIds = this.settingsStore.getAllContainerIds();

    for (const containerId of containerIds) {
      const lastRotation = this.settings.lastRotation[containerId] || 0;
      const timeSinceRotation = now - lastRotation;

      if (timeSinceRotation >= interval) {
        await this.rotateContainer(containerId);
      }
    }
  }

  /**
   * Rotate entropy for a specific container
   */
  async rotateContainer(containerId: string): Promise<void> {
    await this.settingsStore.rotateEntropy(containerId);

    this.settings.lastRotation[containerId] = Date.now();
    await this.saveSettings();

    logger.info('Rotated entropy for container', { containerId });
  }

  /**
   * Rotate entropy for all containers
   */
  async rotateAllContainers(): Promise<void> {
    const containerIds = this.settingsStore.getAllContainerIds();

    for (const containerId of containerIds) {
      await this.rotateContainer(containerId);
    }

    logger.info('Rotated entropy for all containers', { count: containerIds.length });
  }

  /**
   * Get time until next rotation for a container
   */
  getTimeUntilRotation(containerId: string): number | null {
    if (!this.settings.enabled || this.settings.schedule === 'off') {
      return null;
    }

    if (this.settings.schedule === 'session') {
      return null; // Rotates on restart only
    }

    const interval = SCHEDULE_INTERVALS[this.settings.schedule];
    const lastRotation = this.settings.lastRotation[containerId] || 0;
    const timeSinceRotation = Date.now() - lastRotation;

    return Math.max(0, interval - timeSinceRotation);
  }

  /**
   * Format time until rotation as human-readable string
   */
  formatTimeUntilRotation(containerId: string): string {
    const ms = this.getTimeUntilRotation(containerId);

    if (ms === null) {
      return this.settings.schedule === 'session' ? 'On restart' : 'Disabled';
    }

    const hours = Math.floor(ms / (60 * 60 * 1000));
    const minutes = Math.floor((ms % (60 * 60 * 1000)) / (60 * 1000));

    if (hours > 24) {
      const days = Math.floor(hours / 24);
      return `${days}d ${hours % 24}h`;
    }

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }

    return `${minutes}m`;
  }
}
