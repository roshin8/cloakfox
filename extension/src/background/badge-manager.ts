/**
 * Badge Manager - Updates toolbar icon badge with protection stats
 */

import browser from 'webextension-polyfill';

interface TabStats {
  blocked: number;
  spoofed: number;
  total: number;
}

// Per-tab statistics
const tabStats: Map<number, TabStats> = new Map();

/**
 * Badge Manager class
 */
export class BadgeManager {
  private enabled: boolean = true;

  /**
   * Initialize the badge manager
   */
  async init(): Promise<void> {
    // Set default badge colors
    await browser.action.setBadgeBackgroundColor({ color: '#10B981' }); // Green

    // Listen for tab changes
    browser.tabs.onActivated.addListener(async (activeInfo) => {
      await this.updateBadgeForTab(activeInfo.tabId);
    });

    // Listen for tab removal
    browser.tabs.onRemoved.addListener((tabId) => {
      tabStats.delete(tabId);
    });

    // Listen for navigation (reset stats)
    browser.webNavigation.onCommitted.addListener((details) => {
      if (details.frameId === 0) {
        // Main frame navigation
        tabStats.set(details.tabId, { blocked: 0, spoofed: 0, total: 0 });
        this.updateBadgeForTab(details.tabId);
      }
    });

    console.log('[CloakfoxShield] Badge manager initialized');
  }

  /**
   * Record a fingerprint access for a tab
   */
  recordAccess(tabId: number, wasBlocked: boolean, wasSpoofed: boolean): void {
    if (!this.enabled) return;

    let stats = tabStats.get(tabId);
    if (!stats) {
      stats = { blocked: 0, spoofed: 0, total: 0 };
      tabStats.set(tabId, stats);
    }

    stats.total++;
    if (wasBlocked) stats.blocked++;
    if (wasSpoofed) stats.spoofed++;

    this.updateBadgeForTab(tabId);
  }

  /**
   * Update badge for a specific tab
   */
  async updateBadgeForTab(tabId: number): Promise<void> {
    if (!this.enabled) {
      await browser.action.setBadgeText({ text: '', tabId });
      return;
    }

    const stats = tabStats.get(tabId);

    if (!stats || stats.total === 0) {
      await browser.action.setBadgeText({ text: '', tabId });
      return;
    }

    const protectedCount = stats.blocked + stats.spoofed;

    // Show count on badge
    let badgeText = '';
    if (protectedCount > 99) {
      badgeText = '99+';
    } else if (protectedCount > 0) {
      badgeText = protectedCount.toString();
    }

    // Set badge color based on protection level
    const protectionRate = (protectedCount / stats.total) * 100;
    let badgeColor = '#10B981'; // Green - good protection

    if (protectionRate < 50) {
      badgeColor = '#EF4444'; // Red - poor protection
    } else if (protectionRate < 80) {
      badgeColor = '#F59E0B'; // Yellow - moderate protection
    }

    await browser.action.setBadgeBackgroundColor({ color: badgeColor, tabId });
    await browser.action.setBadgeText({ text: badgeText, tabId });
  }

  /**
   * Get stats for a tab
   */
  getTabStats(tabId: number): TabStats | undefined {
    return tabStats.get(tabId);
  }

  /**
   * Enable/disable badge
   */
  async setEnabled(enabled: boolean): Promise<void> {
    this.enabled = enabled;

    if (!enabled) {
      // Clear all badges
      const tabs = await browser.tabs.query({});
      for (const tab of tabs) {
        if (tab.id) {
          await browser.action.setBadgeText({ text: '', tabId: tab.id });
        }
      }
    }
  }

  /**
   * Set badge to show protection is disabled
   */
  async setDisabled(tabId: number): Promise<void> {
    await browser.action.setBadgeBackgroundColor({ color: '#6B7280', tabId }); // Gray
    await browser.action.setBadgeText({ text: 'OFF', tabId });
  }

  /**
   * Set badge to show protection is enabled
   */
  async setEnabled2(tabId: number): Promise<void> {
    await this.updateBadgeForTab(tabId);
  }
}

// Singleton instance
let badgeManagerInstance: BadgeManager | null = null;

export function getBadgeManager(): BadgeManager {
  if (!badgeManagerInstance) {
    badgeManagerInstance = new BadgeManager();
  }
  return badgeManagerInstance;
}

export function recordFingerprintAccess(tabId: number, wasBlocked: boolean, wasSpoofed: boolean): void {
  getBadgeManager().recordAccess(tabId, wasBlocked, wasSpoofed);
}
