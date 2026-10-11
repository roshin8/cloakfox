/**
 * IP Isolation - Detects when multiple containers share the same public IP.
 *
 * If Container A and Container B both browse with the same public IP address,
 * websites can correlate those sessions as belonging to the same person.
 * This module detects that and warns the user.
 *
 * How it works:
 * 1. On main_frame navigation, detect the user's public IP for the container
 * 2. Store the mapping: containerId → publicIP
 * 3. If another container already has the same publicIP, show a warning
 */

import browser from 'webextension-polyfill';
import type { SettingsStore } from './settings-store';
import type { ContainerManager } from './container-manager';
import type { IPRecord } from '@/types';

/** Public IP echo services (lightweight, return plain text or JSON) */
const IP_SERVICES = [
  { url: 'https://api.ipify.org?format=json', parse: (d: any) => d.ip },
  { url: 'https://httpbin.org/ip', parse: (d: any) => d.origin?.split(',')[0]?.trim() },
];

export class IPIsolation {
  private settingsStore: SettingsStore;
  private containerManager: ContainerManager;

  /** Cache: containerId → { ip, expires } */
  private ipCache: Map<string, { ip: string; expires: number }> = new Map();

  /** Containers temporarily allowed (user clicked "Allow Once") */
  private allowedContainers: Set<string> = new Set();

  /** Containers permanently allowed to share IPs (user clicked "Always Allow") */
  private alwaysAllowedContainers: Set<string> = new Set();

  /** Tabs currently being checked (avoid duplicate checks) */
  private checking: Set<number> = new Set();

  constructor(settingsStore: SettingsStore, containerManager: ContainerManager) {
    this.settingsStore = settingsStore;
    this.containerManager = containerManager;
  }

  async init(): Promise<void> {
    // Load persisted always-allowed containers
    try {
      const stored = await browser.storage.local.get('ipAlwaysAllowedContainers');
      if (Array.isArray(stored.ipAlwaysAllowedContainers)) {
        this.alwaysAllowedContainers = new Set(stored.ipAlwaysAllowedContainers);
      }
    } catch {}

    // Check public IP on every main_frame navigation
    browser.webNavigation.onCommitted.addListener((details) => {
      if (details.frameId !== 0) return; // top frame only
      this.checkPublicIP(details.tabId, details.url);
    });

    // Listen for messages from warning page
    browser.runtime.onMessage.addListener((message) => {
      if ((message as any).type === 'IP_ALLOW_ONCE') {
        const { containerId } = message as any;
        this.allowedContainers.add(containerId);
        setTimeout(() => this.allowedContainers.delete(containerId), 30000);
        return Promise.resolve({ success: true });
      }
      if ((message as any).type === 'IP_RECHECK') {
        return this.handleRecheck(message as any);
      }
      if ((message as any).type === 'IP_ALWAYS_ALLOW') {
        const { containerId } = message as any;
        this.alwaysAllowedContainers.add(containerId);
        browser.storage.local.set({
          ipAlwaysAllowedContainers: [...this.alwaysAllowedContainers],
        }).catch(() => {});
        return Promise.resolve({ success: true });
      }
      return false;
    });
  }

  /**
   * Re-check the user's public IP after they claim to have changed it.
   * Clears the IP cache, fetches fresh, and checks for conflict.
   */
  async handleRecheck(
    message: { containerId: string; url: string }
  ): Promise<{ conflict: boolean; newIP?: string; oldIP?: string }> {
    const { containerId } = message;

    // Clear cached IP so we fetch fresh
    this.ipCache.delete(containerId);

    const newIP = await this.fetchPublicIP(containerId);
    if (!newIP) return { conflict: false };

    const ipDatabase = this.settingsStore.getIPDatabase();
    const ipKey = `pub:${newIP}`;
    const existingRecord = ipDatabase.ipRecords[ipKey];

    if (existingRecord && existingRecord.containerId !== containerId) {
      // Still conflicting
      return { conflict: true, newIP, oldIP: existingRecord.ip };
    }

    // No conflict — record this new IP for this container and clean up old record
    const containerName = this.containerManager.getContainerName(containerId);
    await this.recordIPAccess(ipKey, newIP, containerId, message.url);

    return { conflict: false, newIP };
  }

  /**
   * Fetch the user's public IP address.
   * Cached per container for 5 minutes (containers may use different proxies).
   */
  private async fetchPublicIP(containerId: string): Promise<string | null> {
    const cached = this.ipCache.get(containerId);
    if (cached && cached.expires > Date.now()) {
      return cached.ip;
    }

    for (const service of IP_SERVICES) {
      try {
        const response = await fetch(service.url);
        const data = await response.json();
        const ip = service.parse(data);
        if (ip && typeof ip === 'string') {
          this.ipCache.set(containerId, { ip, expires: Date.now() + 5 * 60 * 1000 });
          return ip;
        }
      } catch {
        // Try next service
      }
    }
    return null;
  }

  /**
   * Check the user's public IP for this container and warn if another
   * container shares the same IP (identity correlation risk).
   */
  private async checkPublicIP(tabId: number, url: string): Promise<void> {
    if (this.checking.has(tabId)) return;
    this.checking.add(tabId);

    try {
      // Skip extension pages
      if (url.startsWith('moz-extension:') || url.startsWith('about:')) return;

      const ipDatabase = this.settingsStore.getIPDatabase();
      const settings = ipDatabase.settings;
      if (!settings.enabled) return;

      const containerId = await this.containerManager.getContainerForTab(tabId);
      if (this.allowedContainers.has(containerId)) return;
      if (this.alwaysAllowedContainers.has(containerId)) return;

      // Fetch our public IP
      const publicIP = await this.fetchPublicIP(containerId);
      if (!publicIP) return;

      // Skip if this IP is permanently allowed
      if (ipDatabase.exceptions.includes(publicIP)) return;

      // Check if this IP is already claimed by a DIFFERENT container
      const ipKey = `pub:${publicIP}`;
      const existingRecord = ipDatabase.ipRecords[ipKey];

      if (existingRecord && existingRecord.containerId !== containerId) {
        // CONFLICT — same public IP used in multiple containers
        const containerName = this.containerManager.getContainerName(containerId);
        const originalContainerName = this.containerManager.getContainerName(existingRecord.containerId)
          || existingRecord.containerName;

        const warningUrl = browser.runtime.getURL(
          `pages/ip-warning.html?${new URLSearchParams({
            ip: publicIP,
            domain: new URL(url).hostname,
            url,
            currentContainer: containerName,
            currentContainerId: containerId,
            originalContainer: originalContainerName,
            originalContainerId: existingRecord.containerId,
            lastAccessed: existingRecord.lastAccessed.toString(),
          }).toString()}`
        );
        await browser.tabs.update(tabId, { url: warningUrl });
      } else if (!existingRecord) {
        // No record — claim this IP for this container
        await this.recordIPAccess(ipKey, publicIP, containerId, url);
      } else {
        // Same container — update access time
        await this.recordIPAccess(ipKey, publicIP, containerId, url);
      }
    } catch (error) {
      console.error('[IPIsolation] Public IP check error:', error);
    } finally {
      this.checking.delete(tabId);
    }
  }

  private async recordIPAccess(
    key: string, ip: string, containerId: string, url: string
  ): Promise<void> {
    const containerName = this.containerManager.getContainerName(containerId);
    const ipDatabase = this.settingsStore.getIPDatabase();
    const existing = ipDatabase.ipRecords[key];
    const urls = existing?.urls || [];
    urls.unshift(url);

    await this.settingsStore.updateIPDatabase({
      ipRecords: {
        ...ipDatabase.ipRecords,
        [key]: {
          ip, containerId, containerName,
          firstAccessed: existing?.firstAccessed || Date.now(),
          lastAccessed: Date.now(),
          accessCount: (existing?.accessCount || 0) + 1,
          urls: urls.slice(0, 10),
        },
      },
    });
  }

  checkIPConflict(
    ip: string, containerId: string
  ): { hasConflict: boolean; originalRecord?: IPRecord } {
    const ipDatabase = this.settingsStore.getIPDatabase();
    const record = ipDatabase.ipRecords[`pub:${ip}`];
    if (record && record.containerId !== containerId) {
      return { hasConflict: true, originalRecord: record };
    }
    return { hasConflict: false };
  }

  async clearIPRecord(ip: string): Promise<void> {
    const ipDatabase = this.settingsStore.getIPDatabase();
    // Clear by key (pub:ip) or raw ip
    const keyToRemove = ipDatabase.ipRecords[`pub:${ip}`] ? `pub:${ip}` : ip;
    const { [keyToRemove]: _, ...remaining } = ipDatabase.ipRecords;
    await this.settingsStore.updateIPDatabase({ ipRecords: remaining });
  }

  async clearAllRecords(): Promise<void> {
    await this.settingsStore.updateIPDatabase({ ipRecords: {} });
    this.ipCache.clear();
  }

  async addException(ip: string): Promise<void> {
    const ipDatabase = this.settingsStore.getIPDatabase();
    if (!ipDatabase.exceptions.includes(ip)) {
      await this.settingsStore.updateIPDatabase({ exceptions: [...ipDatabase.exceptions, ip] });
    }
  }

  async removeException(ip: string): Promise<void> {
    const ipDatabase = this.settingsStore.getIPDatabase();
    await this.settingsStore.updateIPDatabase({
      exceptions: ipDatabase.exceptions.filter(e => e !== ip),
    });
  }

  async addTrackedDomain(domain: string): Promise<void> {
    const ipDatabase = this.settingsStore.getIPDatabase();
    const tracked = ipDatabase.trackedDomains || [];
    if (!tracked.includes(domain)) {
      await this.settingsStore.updateIPDatabase({ trackedDomains: [...tracked, domain] } as any);
    }
  }

  async removeTrackedDomain(domain: string): Promise<void> {
    const ipDatabase = this.settingsStore.getIPDatabase();
    const tracked = ipDatabase.trackedDomains || [];
    await this.settingsStore.updateIPDatabase({
      trackedDomains: tracked.filter(d => d !== domain),
    } as any);
  }

  async reassignIP(ip: string, newContainerId: string): Promise<void> {
    const ipDatabase = this.settingsStore.getIPDatabase();
    const key = `pub:${ip}`;
    const record = ipDatabase.ipRecords[key];
    if (record) {
      const containerName = this.containerManager.getContainerName(newContainerId);
      await this.settingsStore.updateIPDatabase({
        ipRecords: {
          ...ipDatabase.ipRecords,
          [key]: { ...record, containerId: newContainerId, containerName },
        },
      });
    }
  }
}
