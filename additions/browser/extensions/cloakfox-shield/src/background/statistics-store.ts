/**
 * Statistics Store
 *
 * Persists fingerprint protection statistics to browser storage
 * for long-term tracking and analysis.
 */

import browser from 'webextension-polyfill';

export interface APIAccessRecord {
  api: string;
  category: string;
  timestamp: number;
  wasBlocked: boolean;
  wasSpoofed: boolean;
  domain: string;
}

export interface DomainStats {
  domain: string;
  totalAccesses: number;
  blocked: number;
  spoofed: number;
  allowed: number;
  categories: Record<string, number>;
  firstSeen: number;
  lastSeen: number;
}

export interface ContainerStats {
  containerId: string;
  containerName: string;
  totalAccesses: number;
  blocked: number;
  spoofed: number;
  allowed: number;
  byCategory: Record<string, { blocked: number; spoofed: number; allowed: number }>;
  byDomain: Record<string, DomainStats>;
  createdAt: number;
  lastUpdated: number;
}

export interface GlobalStats {
  totalAccesses: number;
  totalBlocked: number;
  totalSpoofed: number;
  totalAllowed: number;
  byCategory: Record<string, { blocked: number; spoofed: number; allowed: number }>;
  topDomains: Array<{ domain: string; accesses: number }>;
  lastUpdated: number;
}

const STORAGE_KEY_PREFIX = 'stats_';
const GLOBAL_STATS_KEY = 'stats_global';
const MAX_DOMAINS_PER_CONTAINER = 100;
const MAX_TOP_DOMAINS = 20;

/**
 * Statistics Store for tracking fingerprint protection effectiveness
 */
export class StatisticsStore {
  private cache: Map<string, ContainerStats> = new Map();
  private globalCache: GlobalStats | null = null;
  private saveTimeout: NodeJS.Timeout | null = null;
  private isDirty = false;

  constructor() {
    this.loadGlobalStats();
  }

  /**
   * Record an API access event
   */
  async recordAccess(
    containerId: string,
    containerName: string,
    record: APIAccessRecord
  ): Promise<void> {
    // Get or create container stats
    let stats = this.cache.get(containerId);
    if (!stats) {
      const loaded = await this.loadContainerStats(containerId);
      stats = loaded ?? this.createEmptyContainerStats(containerId, containerName);
      this.cache.set(containerId, stats);
    }

    // Update container stats
    stats.totalAccesses++;
    stats.lastUpdated = Date.now();

    if (record.wasBlocked) {
      stats.blocked++;
    } else if (record.wasSpoofed) {
      stats.spoofed++;
    } else {
      stats.allowed++;
    }

    // Update by category
    if (!stats.byCategory[record.category]) {
      stats.byCategory[record.category] = { blocked: 0, spoofed: 0, allowed: 0 };
    }
    if (record.wasBlocked) {
      stats.byCategory[record.category].blocked++;
    } else if (record.wasSpoofed) {
      stats.byCategory[record.category].spoofed++;
    } else {
      stats.byCategory[record.category].allowed++;
    }

    // Update by domain
    if (!stats.byDomain[record.domain]) {
      // Limit domains per container
      if (Object.keys(stats.byDomain).length >= MAX_DOMAINS_PER_CONTAINER) {
        this.pruneOldestDomains(stats);
      }
      stats.byDomain[record.domain] = {
        domain: record.domain,
        totalAccesses: 0,
        blocked: 0,
        spoofed: 0,
        allowed: 0,
        categories: {},
        firstSeen: Date.now(),
        lastSeen: Date.now(),
      };
    }

    const domainStats = stats.byDomain[record.domain];
    domainStats.totalAccesses++;
    domainStats.lastSeen = Date.now();
    if (record.wasBlocked) {
      domainStats.blocked++;
    } else if (record.wasSpoofed) {
      domainStats.spoofed++;
    } else {
      domainStats.allowed++;
    }

    if (!domainStats.categories[record.category]) {
      domainStats.categories[record.category] = 0;
    }
    domainStats.categories[record.category]++;

    // Update global stats
    await this.updateGlobalStats(record);

    // Schedule save
    this.isDirty = true;
    this.scheduleSave();
  }

  /**
   * Get stats for a container
   */
  async getContainerStats(containerId: string): Promise<ContainerStats | null> {
    if (this.cache.has(containerId)) {
      return this.cache.get(containerId)!;
    }
    return this.loadContainerStats(containerId);
  }

  /**
   * Get global stats
   */
  async getGlobalStats(): Promise<GlobalStats> {
    if (this.globalCache) {
      return this.globalCache;
    }
    return this.loadGlobalStats();
  }

  /**
   * Get stats summary for display
   */
  async getStatsSummary(): Promise<{
    global: GlobalStats;
    containers: ContainerStats[];
  }> {
    const global = await this.getGlobalStats();

    // Load all container stats
    const allData = await browser.storage.local.get(null);
    const containers: ContainerStats[] = [];

    for (const key of Object.keys(allData)) {
      if (key.startsWith(STORAGE_KEY_PREFIX) && key !== GLOBAL_STATS_KEY) {
        containers.push(allData[key] as ContainerStats);
      }
    }

    return { global, containers };
  }

  /**
   * Clear all statistics
   */
  async clearAll(): Promise<void> {
    const allData = await browser.storage.local.get(null);
    const keysToRemove = Object.keys(allData).filter((key) =>
      key.startsWith(STORAGE_KEY_PREFIX)
    );

    await browser.storage.local.remove(keysToRemove);
    this.cache.clear();
    this.globalCache = null;
  }

  /**
   * Clear stats for a specific container
   */
  async clearContainer(containerId: string): Promise<void> {
    await browser.storage.local.remove(`${STORAGE_KEY_PREFIX}${containerId}`);
    this.cache.delete(containerId);
  }

  // Private methods

  private createEmptyContainerStats(
    containerId: string,
    containerName: string
  ): ContainerStats {
    return {
      containerId,
      containerName,
      totalAccesses: 0,
      blocked: 0,
      spoofed: 0,
      allowed: 0,
      byCategory: {},
      byDomain: {},
      createdAt: Date.now(),
      lastUpdated: Date.now(),
    };
  }

  private async loadContainerStats(
    containerId: string
  ): Promise<ContainerStats | null> {
    try {
      const key = `${STORAGE_KEY_PREFIX}${containerId}`;
      const result = await browser.storage.local.get(key);
      return (result[key] as ContainerStats | undefined) ?? null;
    } catch (error) {
      console.error('Failed to load container stats:', error);
      return null;
    }
  }

  private async loadGlobalStats(): Promise<GlobalStats> {
    try {
      const result = await browser.storage.local.get(GLOBAL_STATS_KEY);
      this.globalCache = (result[GLOBAL_STATS_KEY] as GlobalStats | undefined) ?? this.createEmptyGlobalStats();
      return this.globalCache;
    } catch (error) {
      console.error('Failed to load global stats:', error);
      return this.createEmptyGlobalStats();
    }
  }

  private createEmptyGlobalStats(): GlobalStats {
    return {
      totalAccesses: 0,
      totalBlocked: 0,
      totalSpoofed: 0,
      totalAllowed: 0,
      byCategory: {},
      topDomains: [],
      lastUpdated: Date.now(),
    };
  }

  private async updateGlobalStats(record: APIAccessRecord): Promise<void> {
    if (!this.globalCache) {
      this.globalCache = await this.loadGlobalStats();
    }

    this.globalCache.totalAccesses++;
    this.globalCache.lastUpdated = Date.now();

    if (record.wasBlocked) {
      this.globalCache.totalBlocked++;
    } else if (record.wasSpoofed) {
      this.globalCache.totalSpoofed++;
    } else {
      this.globalCache.totalAllowed++;
    }

    // Update by category
    if (!this.globalCache.byCategory[record.category]) {
      this.globalCache.byCategory[record.category] = {
        blocked: 0,
        spoofed: 0,
        allowed: 0,
      };
    }
    if (record.wasBlocked) {
      this.globalCache.byCategory[record.category].blocked++;
    } else if (record.wasSpoofed) {
      this.globalCache.byCategory[record.category].spoofed++;
    } else {
      this.globalCache.byCategory[record.category].allowed++;
    }

    // Update top domains
    const existingDomain = this.globalCache.topDomains.find(
      (d) => d.domain === record.domain
    );
    if (existingDomain) {
      existingDomain.accesses++;
    } else if (this.globalCache.topDomains.length < MAX_TOP_DOMAINS) {
      this.globalCache.topDomains.push({ domain: record.domain, accesses: 1 });
    }

    // Sort and trim top domains
    this.globalCache.topDomains.sort((a, b) => b.accesses - a.accesses);
    this.globalCache.topDomains = this.globalCache.topDomains.slice(
      0,
      MAX_TOP_DOMAINS
    );
  }

  private pruneOldestDomains(stats: ContainerStats): void {
    const domains = Object.entries(stats.byDomain)
      .map(([domain, data]) => ({ domain, lastSeen: data.lastSeen }))
      .sort((a, b) => a.lastSeen - b.lastSeen);

    // Remove oldest 20%
    const toRemove = Math.floor(domains.length * 0.2);
    for (let i = 0; i < toRemove; i++) {
      delete stats.byDomain[domains[i].domain];
    }
  }

  private scheduleSave(): void {
    if (this.saveTimeout) {
      return;
    }

    this.saveTimeout = setTimeout(async () => {
      this.saveTimeout = null;
      if (this.isDirty) {
        await this.save();
        this.isDirty = false;
      }
    }, 5000); // Save every 5 seconds max
  }

  private async save(): Promise<void> {
    try {
      const dataToSave: Record<string, any> = {};

      // Save all cached container stats
      for (const [containerId, stats] of this.cache) {
        dataToSave[`${STORAGE_KEY_PREFIX}${containerId}`] = stats;
      }

      // Save global stats
      if (this.globalCache) {
        dataToSave[GLOBAL_STATS_KEY] = this.globalCache;
      }

      await browser.storage.local.set(dataToSave);
    } catch (error) {
      console.error('Failed to save statistics:', error);
    }
  }
}

// Singleton instance
let instance: StatisticsStore | null = null;

export function getStatisticsStore(): StatisticsStore {
  if (!instance) {
    instance = new StatisticsStore();
  }
  return instance;
}

export default StatisticsStore;
