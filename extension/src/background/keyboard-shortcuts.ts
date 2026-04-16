/**
 * Keyboard Shortcuts Handler
 *
 * Handles keyboard shortcut commands for Cloakfox Shield
 */

import browser from 'webextension-polyfill';
import { SettingsStore } from './settings-store';

export class KeyboardShortcuts {
  private settingsStore: SettingsStore;

  constructor(settingsStore: SettingsStore) {
    this.settingsStore = settingsStore;
  }

  /**
   * Initialize keyboard shortcuts
   */
  init(): void {
    browser.commands.onCommand.addListener((command) => {
      this.handleCommand(command);
    });

    console.log('[CloakfoxShield] Keyboard shortcuts initialized');
  }

  /**
   * Handle keyboard command
   */
  private async handleCommand(command: string): Promise<void> {
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });

    if (!tab?.id || !tab.cookieStoreId) return;

    switch (command) {
      case 'toggle-protection':
        await this.toggleProtection(tab);
        break;
      case 'rotate-fingerprint':
        await this.rotateFingerprint(tab);
        break;
      case 'toggle-site-exception':
        await this.toggleSiteException(tab);
        break;
      case 'open-popup':
        await browser.action.openPopup();
        break;
      default:
        console.log('[CloakfoxShield] Unknown command:', command);
    }
  }

  /**
   * Toggle protection on/off for current container
   */
  private async toggleProtection(tab: browser.Tabs.Tab): Promise<void> {
    const containerId = tab.cookieStoreId!;
    const settings = await this.settingsStore.getSettings(containerId);

    const newEnabled = !settings.enabled;
    await this.settingsStore.updateSettings(containerId, { enabled: newEnabled });

    // Show notification
    await browser.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon-96.svg',
      title: 'Cloakfox Shield',
      message: newEnabled ? 'Protection enabled' : 'Protection disabled',
    });

    // Reload tab
    await browser.tabs.reload(tab.id!);
  }

  /**
   * Rotate fingerprint for current container
   */
  private async rotateFingerprint(tab: browser.Tabs.Tab): Promise<void> {
    const containerId = tab.cookieStoreId!;

    // Regenerate seed
    await browser.runtime.sendMessage({
      type: 'ROTATE_FINGERPRINT',
      containerId,
    });

    await browser.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon-96.svg',
      title: 'Cloakfox Shield',
      message: 'Fingerprint rotated for this container',
    });

    // Reload tab
    await browser.tabs.reload(tab.id!);
  }

  /**
   * Toggle exception for current site
   */
  private async toggleSiteException(tab: browser.Tabs.Tab): Promise<void> {
    if (!tab.url) return;

    const containerId = tab.cookieStoreId!;
    const url = new URL(tab.url);
    const domain = url.hostname;

    const settings = await this.settingsStore.getSettings(containerId);
    const exceptions = settings.domainExceptions || [];

    let message: string;
    if (exceptions.includes(domain)) {
      // Remove exception
      const newExceptions = exceptions.filter((d: string) => d !== domain);
      await this.settingsStore.updateSettings(containerId, {
        domainExceptions: newExceptions,
      });
      message = `Protection enabled for ${domain}`;
    } else {
      // Add exception
      await this.settingsStore.updateSettings(containerId, {
        domainExceptions: [...exceptions, domain],
      });
      message = `Protection disabled for ${domain}`;
    }

    await browser.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon-96.svg',
      title: 'Cloakfox Shield',
      message,
    });

    // Reload tab
    await browser.tabs.reload(tab.id!);
  }
}
