/**
 * Context Menu Integration
 *
 * Adds right-click menu options for Cloakfox Shield
 */

import browser from 'webextension-polyfill';
import { SettingsStore } from './settings-store';
import { ContainerManager } from './container-manager';

export class ContextMenuManager {
  private settingsStore: SettingsStore;
  private containerManager: ContainerManager;

  constructor(settingsStore: SettingsStore, containerManager: ContainerManager) {
    this.settingsStore = settingsStore;
    this.containerManager = containerManager;
  }

  /**
   * Initialize context menus
   */
  async init(): Promise<void> {
    // Remove existing menus first
    await browser.contextMenus.removeAll();

    // Create parent menu
    browser.contextMenus.create({
      id: 'cloakfox-parent',
      title: 'Cloakfox Shield',
      contexts: ['page', 'link'],
    });

    // Toggle protection for current site
    browser.contextMenus.create({
      id: 'toggle-site-protection',
      parentId: 'cloakfox-parent',
      title: 'Disable protection for this site',
      contexts: ['page'],
    });

    // Separator
    browser.contextMenus.create({
      id: 'separator-1',
      parentId: 'cloakfox-parent',
      type: 'separator',
      contexts: ['page', 'link'],
    });

    // Open link in container submenu
    browser.contextMenus.create({
      id: 'open-in-container',
      parentId: 'cloakfox-parent',
      title: 'Open link in container...',
      contexts: ['link'],
    });

    // Get containers and add submenu items
    await this.updateContainerMenus();

    // Separator
    browser.contextMenus.create({
      id: 'separator-2',
      parentId: 'cloakfox-parent',
      type: 'separator',
      contexts: ['page'],
    });

    // Rotate fingerprint
    browser.contextMenus.create({
      id: 'rotate-fingerprint',
      parentId: 'cloakfox-parent',
      title: 'Rotate fingerprint for this container',
      contexts: ['page'],
    });

    // View fingerprint monitor
    browser.contextMenus.create({
      id: 'view-monitor',
      parentId: 'cloakfox-parent',
      title: 'View fingerprint accesses',
      contexts: ['page'],
    });

    // Listen for menu clicks
    browser.contextMenus.onClicked.addListener((info, tab) => {
      this.handleMenuClick(info, tab);
    });

    console.log('[CloakfoxShield] Context menus initialized');
  }

  /**
   * Update container submenus
   */
  async updateContainerMenus(): Promise<void> {
    try {
      const containers = await browser.contextualIdentities.query({});

      for (const container of containers) {
        browser.contextMenus.create({
          id: `open-in-${container.cookieStoreId}`,
          parentId: 'open-in-container',
          title: `${container.name}`,
          contexts: ['link'],
          icons: {
            '16': `icons/container-${container.color}.svg`,
          },
        });
      }

      // Add "No Container" option
      browser.contextMenus.create({
        id: 'open-in-default',
        parentId: 'open-in-container',
        title: 'No Container (default)',
        contexts: ['link'],
      });
    } catch (error) {
      console.error('[CloakfoxShield] Failed to update container menus:', error);
    }
  }

  /**
   * Handle menu item clicks
   */
  private async handleMenuClick(
    info: browser.Menus.OnClickData,
    tab?: browser.Tabs.Tab
  ): Promise<void> {
    const menuId = info.menuItemId as string;

    if (menuId === 'toggle-site-protection' && tab?.url) {
      await this.toggleSiteProtection(tab);
    } else if (menuId === 'rotate-fingerprint' && tab) {
      await this.rotateFingerprint(tab);
    } else if (menuId === 'view-monitor') {
      await this.openMonitor();
    } else if (menuId.startsWith('open-in-')) {
      const containerId = menuId.replace('open-in-', '');
      await this.openLinkInContainer(info.linkUrl!, containerId);
    }
  }

  /**
   * Toggle protection for current site
   */
  private async toggleSiteProtection(tab: browser.Tabs.Tab): Promise<void> {
    if (!tab.url || !tab.cookieStoreId) return;

    try {
      const url = new URL(tab.url);
      const domain = url.hostname;

      const settings = this.settingsStore.getContainerSettings(tab.cookieStoreId);
      const domainRules = { ...(settings.domainRules || {}) };
      const isExcepted = domainRules[domain]?.enabled === false;

      if (isExcepted) {
        delete domainRules[domain];
        await this.settingsStore.updateContainerSettings(tab.cookieStoreId, { domainRules });
        browser.contextMenus.update('toggle-site-protection', {
          title: 'Disable protection for this site',
        });
      } else {
        domainRules[domain] = { ...(domainRules[domain] || {}), enabled: false };
        await this.settingsStore.updateContainerSettings(tab.cookieStoreId, { domainRules });
        browser.contextMenus.update('toggle-site-protection', {
          title: 'Enable protection for this site',
        });
      }

      // Reload tab to apply changes
      await browser.tabs.reload(tab.id!);
    } catch (error) {
      console.error('[CloakfoxShield] Failed to toggle site protection:', error);
    }
  }

  /**
   * Rotate fingerprint for current container
   */
  private async rotateFingerprint(tab: browser.Tabs.Tab): Promise<void> {
    if (!tab.cookieStoreId) return;

    try {
      // Send message to rotate fingerprint
      await browser.runtime.sendMessage({
        type: 'ROTATE_FINGERPRINT',
        containerId: tab.cookieStoreId,
      });

      // Show notification
      await browser.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon-128.png',
        title: 'Cloakfox Shield',
        message: 'Fingerprint rotated. Reload pages to apply.',
      });
    } catch (error) {
      console.error('[CloakfoxShield] Failed to rotate fingerprint:', error);
    }
  }

  /**
   * Open fingerprint monitor popup
   */
  private async openMonitor(): Promise<void> {
    await browser.action.openPopup();
  }

  /**
   * Open link in specified container
   */
  private async openLinkInContainer(url: string, containerId: string): Promise<void> {
    try {
      const options: browser.Tabs.CreateCreatePropertiesType = { url };

      if (containerId !== 'default') {
        options.cookieStoreId = containerId;
      }

      await browser.tabs.create(options);
    } catch (error) {
      console.error('[CloakfoxShield] Failed to open link in container:', error);
    }
  }
}
