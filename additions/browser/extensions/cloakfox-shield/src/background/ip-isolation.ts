/**
 * IP Isolation - Tracks IP addresses per container and warns on conflicts.
 *
 * Supports both raw IP navigation and domain-based tracking:
 * - Tracked domains get their IP resolved via DNS before navigation
 * - If the resolved IP was used in another container, warn/block
 */

import browser from 'webextension-polyfill';
import type { SettingsStore } from './settings-store';
import type { ContainerManager } from './container-manager';
import type { IPRecord } from '@/types';
import { IP_PATTERNS, MAX_IP_URL_HISTORY } from '@/lib/constants';

export class IPIsolation {
  private settingsStore: SettingsStore;
  private containerManager: ContainerManager;
  // Cache DNS lookups (domain -> IP) for 5 minutes
  private dnsCache: Map<string, { ip: string; expires: number }> = new Map();

  constructor(settingsStore: SettingsStore, containerManager: ContainerManager) {
    this.settingsStore = settingsStore;
    this.containerManager = containerManager;
  }

  // Domains temporarily allowed (user clicked "Allow Once")
  private allowedOnce: Set<string> = new Set();

  async init(): Promise<void> {
    // Use webRequest.onBeforeRequest with blocking to intercept tracked domain requests
    browser.webRequest.onBeforeRequest.addListener(
      (details) => this.handleBeforeRequest(details),
      { urls: ['<all_urls>'], types: ['main_frame'] },
      ['blocking']
    );

    // Listen for "allow once" messages from warning page
    browser.runtime.onMessage.addListener((message: unknown) => {
      if ((message as any).type === 'IP_ALLOW_ONCE') {
        const { ip, url, containerId, containerName } = message as any;
        this.allowedOnce.add(ip);
        this.recordIPAccess(ip, containerId, containerName, url);
        // Clear the allowance after 10 seconds
        setTimeout(() => this.allowedOnce.delete(ip), 10000);
        return Promise.resolve({ success: true });
      }
      return false;
    });
  }

  isIPAddress(hostname: string): boolean {
    return IP_PATTERNS.IPV4.test(hostname) || IP_PATTERNS.IPV6.test(hostname);
  }

  isLocalIP(ip: string): boolean {
    return IP_PATTERNS.LOCAL_IPV4.test(ip);
  }

  isLocalhostIP(ip: string): boolean {
    return IP_PATTERNS.LOCALHOST.test(ip);
  }

  /**
   * Resolve domain to IP using DNS via fetch to a public DNS API.
   * Cached for 5 minutes to avoid excessive lookups.
   */
  private async resolveDomain(domain: string): Promise<string | null> {
    // Check cache
    const cached = this.dnsCache.get(domain);
    if (cached && cached.expires > Date.now()) {
      return cached.ip;
    }

    try {
      // Use DNS-over-HTTPS (Cloudflare)
      const response = await fetch(`https://cloudflare-dns.com/dns-query?name=${encodeURIComponent(domain)}&type=A`, {
        headers: { 'Accept': 'application/dns-json' },
      });
      const data = await response.json();
      const answer = data.Answer?.find((a: any) => a.type === 1); // Type 1 = A record
      if (answer?.data) {
        this.dnsCache.set(domain, { ip: answer.data, expires: Date.now() + 5 * 60 * 1000 });
        return answer.data;
      }
    } catch {
      // DNS lookup failed - skip IP check
    }
    return null;
  }

  /**
   * Check if a domain is in the tracked domains list
   */
  private isTrackedDomain(hostname: string): boolean {
    const ipDatabase = this.settingsStore.getIPDatabase();
    const trackedDomains = ipDatabase.trackedDomains || [];
    return trackedDomains.some(d => {
      if (d.startsWith('*.')) {
        return hostname.endsWith(d.slice(1)) || hostname === d.slice(2);
      }
      return hostname === d;
    });
  }

  /**
   * Handle request before it's sent. Returns { cancel: true } to block,
   * or { redirectUrl: ... } to show warning page, or {} to allow.
   */
  private handleBeforeRequest(
    details: browser.WebRequest.OnBeforeRequestDetailsType
  ): browser.WebRequest.BlockingResponse | void {
    if (details.tabId === -1) return;

    try {
      const url = new URL(details.url);
      const hostname = url.hostname;

      // Skip extension pages
      if (url.protocol === 'moz-extension:' || url.protocol === 'chrome-extension:') return;

      const ipDatabase = this.settingsStore.getIPDatabase();
      const settings = ipDatabase.settings;
      if (!settings.enabled) return;

      // Only check tracked domains and raw IPs
      const isIP = this.isIPAddress(hostname);
      const isTracked = this.isTrackedDomain(hostname);
      if (!isIP && !isTracked) return;

      // For tracked domains, we need async DNS resolution.
      // webRequest blocking can't be async, so we use a two-phase approach:
      // Phase 1: Resolve DNS and check conflict (async, in background)
      // Phase 2: If conflict, redirect to warning page
      this.checkAndHandleConflict(details, hostname, isIP);

      // Can't block synchronously for DNS resolution, so we let the first request through
      // and handle conflicts via redirect on subsequent loads.
      // For raw IPs, we can check synchronously.
      if (isIP) {
        if (this.isLocalhostIP(hostname) && !settings.trackLocalhostIPs) return;
        if (this.isLocalIP(hostname) && !settings.trackLocalIPs) return;
        if (ipDatabase.exceptions.includes(hostname)) return;
        if (this.allowedOnce.has(hostname)) return;

        const existingRecord = ipDatabase.ipRecords[hostname];
        // We need containerId which is async - can't get it synchronously
        // Fall through to async handler
      }
    } catch {
      // Don't block on errors
    }
  }

  /**
   * Async conflict check - runs after the initial request.
   * If conflict found, redirects the tab to the warning page.
   */
  private async checkAndHandleConflict(
    details: browser.WebRequest.OnBeforeRequestDetailsType,
    hostname: string,
    isIP: boolean
  ): Promise<void> {
    try {
      const ipDatabase = this.settingsStore.getIPDatabase();
      const settings = ipDatabase.settings;

      let ipToCheck: string | null = null;

      if (isIP) {
        ipToCheck = hostname;
      } else {
        ipToCheck = await this.resolveDomain(hostname);
      }

      if (!ipToCheck) return;
      if (this.allowedOnce.has(ipToCheck)) return;
      if (this.isLocalhostIP(ipToCheck) && !settings.trackLocalhostIPs) return;
      if (this.isLocalIP(ipToCheck) && !settings.trackLocalIPs) return;
      if (ipDatabase.exceptions.includes(ipToCheck)) return;

      const containerId = await this.containerManager.getContainerForTab(details.tabId);
      const containerName = this.containerManager.getContainerName(containerId);
      const existingRecord = ipDatabase.ipRecords[ipToCheck];

      if (existingRecord && existingRecord.containerId !== containerId) {
        // CONFLICT - redirect to warning page which blocks until user decides
        const warningUrl = browser.runtime.getURL(
          `pages/ip-warning.html?${new URLSearchParams({
            ip: ipToCheck,
            domain: hostname,
            url: details.url,
            currentContainer: containerName,
            currentContainerId: containerId,
            originalContainer: existingRecord.containerName,
            originalContainerId: existingRecord.containerId,
            lastAccessed: existingRecord.lastAccessed.toString(),
          }).toString()}`
        );
        await browser.tabs.update(details.tabId, { url: warningUrl });
      } else {
        // No conflict - record this access
        await this.recordIPAccess(ipToCheck, containerId, containerName, details.url);
      }
    } catch (error) {
      console.error('[IPIsolation] Conflict check error:', error);
    }
  }

  async recordIPAccess(ip: string, containerId: string, containerName: string, url: string): Promise<void> {
    const ipDatabase = this.settingsStore.getIPDatabase();
    const existing = ipDatabase.ipRecords[ip];
    const urls = existing?.urls || [];
    urls.unshift(url);

    await this.settingsStore.updateIPDatabase({
      ipRecords: {
        ...ipDatabase.ipRecords,
        [ip]: {
          ip, containerId, containerName,
          firstAccessed: existing?.firstAccessed || Date.now(),
          lastAccessed: Date.now(),
          accessCount: (existing?.accessCount || 0) + 1,
          urls: urls.slice(0, MAX_IP_URL_HISTORY),
        },
      },
    });
  }


  checkIPConflict(ip: string, containerId: string): { hasConflict: boolean; originalRecord?: IPRecord } {
    const ipDatabase = this.settingsStore.getIPDatabase();
    const record = ipDatabase.ipRecords[ip];
    if (record && record.containerId !== containerId) {
      return { hasConflict: true, originalRecord: record };
    }
    return { hasConflict: false };
  }

  async clearIPRecord(ip: string): Promise<void> {
    const ipDatabase = this.settingsStore.getIPDatabase();
    const { [ip]: _, ...remaining } = ipDatabase.ipRecords;
    await this.settingsStore.updateIPDatabase({ ipRecords: remaining });
  }

  async addException(ip: string): Promise<void> {
    const ipDatabase = this.settingsStore.getIPDatabase();
    if (!ipDatabase.exceptions.includes(ip)) {
      await this.settingsStore.updateIPDatabase({ exceptions: [...ipDatabase.exceptions, ip] });
    }
  }

  async removeException(ip: string): Promise<void> {
    const ipDatabase = this.settingsStore.getIPDatabase();
    await this.settingsStore.updateIPDatabase({ exceptions: ipDatabase.exceptions.filter(e => e !== ip) });
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
    await this.settingsStore.updateIPDatabase({ trackedDomains: tracked.filter(d => d !== domain) } as any);
  }

  async reassignIP(ip: string, newContainerId: string): Promise<void> {
    const ipDatabase = this.settingsStore.getIPDatabase();
    const record = ipDatabase.ipRecords[ip];
    if (record) {
      const containerName = this.containerManager.getContainerName(newContainerId);
      await this.settingsStore.updateIPDatabase({
        ipRecords: { ...ipDatabase.ipRecords, [ip]: { ...record, containerId: newContainerId, containerName } },
      });
    }
  }
}
