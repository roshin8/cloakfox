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
    const settings = this.settingsStore.getContainerSettings(containerId);

    const newEnabled = !settings.enabled;
    await this.settingsStore.updateContainerSettings(containerId, { enabled: newEnabled });

    // Show notification
    await browser.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon-128.png',
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
      iconUrl: 'icons/icon-128.png',
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

    const settings = this.settingsStore.getContainerSettings(containerId);
    // A domain with `{ enabled: false }` in domainRules is treated as an
    // exception: getSettingsForDomain merges it and disables protection
    // for that domain while leaving other domains in the container spoofed.
    const domainRules = { ...(settings.domainRules || {}) };
    const isException = domainRules[domain]?.enabled === false;

    let message: string;
    if (isException) {
      delete domainRules[domain];
      await this.settingsStore.updateContainerSettings(containerId, { domainRules });
      message = `Protection enabled for ${domain}`;
    } else {
      domainRules[domain] = { ...(domainRules[domain] || {}), enabled: false };
      await this.settingsStore.updateContainerSettings(containerId, { domainRules });
      message = `Protection disabled for ${domain}`;
    }

    await browser.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon-128.png',
      title: 'Cloakfox Shield',
      message,
    });

    // Reload tab
    await browser.tabs.reload(tab.id!);
  }
}
