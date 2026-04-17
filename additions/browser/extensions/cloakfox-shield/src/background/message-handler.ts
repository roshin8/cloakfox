/**
 * Message Handler - Routes messages between extension components
 */

import browser from 'webextension-polyfill';
import type { SettingsStore } from './settings-store';
import type { ContainerManager } from './container-manager';
import type { IPIsolation } from './ip-isolation';
import type { ProfileRotation } from './profile-rotation';
import type { StatisticsStore } from './statistics-store';
import type {
  ExtensionMessage,
  InjectConfig,
  AssignedProfileData,
  FingerprintReportMessage,
  GetFingerprintDataMessage,
  GetRecommendationsMessage,
  FingerprintData,
  SpooferRecommendation,
  RecommendationsResponse,
} from '@/types';
import { ensureUniqueProfile, getAssignedProfile } from './profile-manager';
import { CollisionDetector } from './collision-detector';
import {
  MSG_GET_SETTINGS,
  MSG_SET_SETTINGS,
  MSG_GET_ENTROPY,
  MSG_GET_CONTAINER_INFO,
  MSG_GET_ALL_CONTAINERS,
  MSG_IP_CONFLICT_CHECK,
  MSG_INJECT_CONFIG,
  MSG_FINGERPRINT_REPORT,
  MSG_GET_FINGERPRINT_DATA,
  MSG_GET_RECOMMENDATIONS,
  MSG_GET_ASSIGNED_PROFILE,
  MSG_GET_IP_DATABASE,
  MSG_ADD_TRACKED_DOMAIN,
  MSG_REMOVE_TRACKED_DOMAIN,
  MSG_CLEAR_IP_RECORD,
  MSG_UPDATE_IP_SETTINGS,
  MSG_ADD_IP_EXCEPTION,
  MSG_REMOVE_IP_EXCEPTION,
  MSG_GET_ROTATION_SETTINGS,
  MSG_SET_ROTATION_SETTINGS,
  MSG_ROTATE_NOW,
  MSG_GET_STATS,
  MSG_CHECK_COLLISIONS,
} from '@/constants';
import { CATEGORY_TO_SETTING } from '@/constants/categories';

export class MessageHandler {
  private settingsStore: SettingsStore;
  private containerManager: ContainerManager;
  private ipIsolation: IPIsolation;
  private profileRotation: ProfileRotation;
  private statisticsStore: StatisticsStore;
  private fingerprintData: Map<number, FingerprintData> = new Map();

  constructor(
    settingsStore: SettingsStore,
    containerManager: ContainerManager,
    ipIsolation: IPIsolation,
    profileRotation: ProfileRotation,
    statisticsStore: StatisticsStore
  ) {
    this.settingsStore = settingsStore;
    this.containerManager = containerManager;
    this.ipIsolation = ipIsolation;
    this.profileRotation = profileRotation;
    this.statisticsStore = statisticsStore;

    browser.tabs.onRemoved.addListener((tabId) => {
      this.fingerprintData.delete(tabId);
    });
  }

  init(): void {
    browser.runtime.onMessage.addListener((message: unknown, sender: browser.Runtime.MessageSender) => {
      return this.handleMessage(message as ExtensionMessage, sender);
    });
  }

  private async handleMessage(
    message: ExtensionMessage,
    sender: browser.Runtime.MessageSender
  ): Promise<unknown> {
    try {
      switch (message.type) {
      case MSG_GET_SETTINGS:
        return this.handleGetSettings(message);

      case MSG_SET_SETTINGS:
        return this.handleSetSettings(message);

      case MSG_GET_ENTROPY:
        return this.handleGetEntropy(message);

      case MSG_GET_CONTAINER_INFO:
        return this.handleGetContainerInfo(message, sender);

      case MSG_GET_ALL_CONTAINERS:
        return this.handleGetAllContainers();

      case MSG_IP_CONFLICT_CHECK:
        return this.handleIPConflictCheck(message);

      case MSG_INJECT_CONFIG:
        return this.handleGetInjectConfig(sender);

      case MSG_FINGERPRINT_REPORT:
        return this.handleFingerprintReport(message, sender);

      case 'ACTIVE_PROFILE':
        return this.handleActiveProfile(message, sender);

      case MSG_GET_FINGERPRINT_DATA:
        return this.handleGetFingerprintData(message, sender);

      case MSG_GET_RECOMMENDATIONS:
        return this.handleGetRecommendations(message, sender);

      case MSG_GET_ASSIGNED_PROFILE:
        return this.handleGetAssignedProfile(message);

      case MSG_GET_IP_DATABASE:
        return this.settingsStore.getIPDatabase();

      case MSG_ADD_TRACKED_DOMAIN:
        await this.ipIsolation.addTrackedDomain((message as any).domain);
        return { success: true };

      case MSG_REMOVE_TRACKED_DOMAIN:
        await this.ipIsolation.removeTrackedDomain((message as any).domain);
        return { success: true };

      case MSG_CLEAR_IP_RECORD:
        await this.ipIsolation.clearIPRecord((message as any).ip);
        return { success: true };

      case MSG_UPDATE_IP_SETTINGS:
        await this.settingsStore.updateIPDatabase({ settings: (message as any).settings });
        return { success: true };

      case MSG_ADD_IP_EXCEPTION:
        await this.ipIsolation.addException((message as any).ip);
        return { success: true };

      case MSG_REMOVE_IP_EXCEPTION:
        await this.ipIsolation.removeException((message as any).ip);
        return { success: true };

      case MSG_GET_ROTATION_SETTINGS:
        return this.profileRotation.getSettings();

      case MSG_SET_ROTATION_SETTINGS:
        await this.profileRotation.updateSettings((message as any).settings);
        return { success: true };

      case MSG_ROTATE_NOW:
        await this.profileRotation.rotateAllContainers();
        return { success: true };

      case MSG_GET_STATS:
        return this.statisticsStore.getStatsSummary();

      case MSG_CHECK_COLLISIONS:
        return this.handleCheckCollisions();

      default:
        return null;
      }
    } catch (error) {
      console.error('[MessageHandler] Error handling message:', (message as any).type, error);
      return null;
    }
  }

  private handleGetSettings(message: import('@/types').GetSettingsMessage) {
    const { containerId, domain } = message;
    if (domain) {
      return this.settingsStore.getSettingsForDomain(containerId, domain);
    }
    return this.settingsStore.getContainerSettings(containerId);
  }

  private async handleSetSettings(message: import('@/types').SetSettingsMessage) {
    const { containerId, settings } = message;
    await this.settingsStore.updateContainerSettings(containerId, settings);
    return { success: true };
  }

  private handleGetEntropy(message: import('@/types').GetEntropyMessage) {
    return this.settingsStore.getEntropy(message.containerId);
  }

  private async handleGetContainerInfo(
    message: import('@/types').GetContainerInfoMessage,
    sender: browser.Runtime.MessageSender
  ) {
    const tabId = message.tabId ?? sender.tab?.id;
    if (!tabId) {
      return { containerId: 'firefox-default', containerName: 'Default' };
    }

    const containerId = await this.containerManager.getContainerForTab(tabId);
    const container = this.containerManager.getContainer(containerId);

    return {
      containerId,
      containerName: container?.name || 'Unknown',
      containerColor: container?.color || 'toolbar',
      containerIcon: container?.icon || 'circle',
    };
  }

  private handleGetAllContainers() {
    return this.containerManager.getAllContainers();
  }

  private handleIPConflictCheck(message: import('@/types').IPConflictCheckMessage) {
    return this.ipIsolation.checkIPConflict(message.ip, message.containerId);
  }

  /**
   * Prepare config for page context injection
   */
  private async handleGetInjectConfig(
    sender: browser.Runtime.MessageSender
  ): Promise<InjectConfig | null> {
    const tabId = sender.tab?.id;
    const url = sender.tab?.url || sender.url;

    if (!tabId || !url) return null;

    try {
      const domain = new URL(url).hostname;
      const containerId = await this.containerManager.getContainerForTab(tabId);

      await this.settingsStore.ensureContainerSettings(containerId);

      const settings = this.settingsStore.getSettingsForDomain(containerId, domain);
      const entropy = this.settingsStore.getEntropy(containerId);

      if (!entropy) return null;

      const assignedProfile = await ensureUniqueProfile(entropy);

      const assignedProfileData: AssignedProfileData = {
        userAgent: {
          id: assignedProfile.userAgent.id,
          name: assignedProfile.userAgent.name,
          userAgent: assignedProfile.userAgent.userAgent,
          platform: assignedProfile.userAgent.platform,
          vendor: assignedProfile.userAgent.vendor,
          appVersion: assignedProfile.userAgent.appVersion,
          oscpu: assignedProfile.userAgent.oscpu,
          mobile: assignedProfile.userAgent.mobile,
          platformName: assignedProfile.userAgent.platformName,
          platformVersion: assignedProfile.userAgent.platformVersion,
          brands: assignedProfile.userAgent.brands,
        },
        screen: {
          width: assignedProfile.screen.width,
          height: assignedProfile.screen.height,
          availWidth: assignedProfile.screen.availWidth,
          availHeight: assignedProfile.screen.availHeight,
          colorDepth: assignedProfile.screen.colorDepth,
          pixelDepth: assignedProfile.screen.pixelDepth,
          devicePixelRatio: assignedProfile.screen.devicePixelRatio,
        },
        hardwareConcurrency: assignedProfile.hardwareConcurrency,
        deviceMemory: assignedProfile.deviceMemory,
        timezoneOffset: assignedProfile.timezoneOffset,
        languages: assignedProfile.languages,
      };

      return {
        containerId,
        domain,
        seed: entropy.seed,
        settings: settings.spoofers,
        profile: settings.profile,
        assignedProfile: assignedProfileData,
      };
    } catch (error) {
      console.error('[MessageHandler] Error preparing inject config:', error);
      return null;
    }
  }

  private async handleFingerprintReport(
    message: FingerprintReportMessage,
    sender: browser.Runtime.MessageSender
  ): { success: boolean } | null {
    const tabId = sender.tab?.id;
    if (!tabId) return null;

    const fpData = {
      summary: message.summary,
      detail: message.detail,
      url: message.url,
      lastUpdated: Date.now(),
    };
    this.fingerprintData.set(tabId, fpData);

    // Also persist to storage (event page may suspend and lose in-memory data)
    try {
      await browser.storage.local.set({ [`fpData:${tabId}`]: fpData });
    } catch {}

    // Feed stats store
    try {
      const containerId = await this.containerManager.getContainerForTab(tabId);
      const containerName = this.containerManager.getContainerName(containerId);
      const domain = message.url ? new URL(message.url).hostname : 'unknown';
      for (const d of message.detail) {
        this.statisticsStore.recordAccess(containerId, containerName, {
          api: d.api, category: d.category, timestamp: d.timestamp,
          wasBlocked: d.blocked, wasSpoofed: d.spoofed, domain,
        });
      }
    } catch {}

    // Update badge with count of UNIQUE spoofed/blocked APIs
    if (message.detail?.length) {
      const uniqueAPIs = new Map<string, { spoofed: boolean; blocked: boolean }>();
      for (const d of message.detail) {
        if (!uniqueAPIs.has(d.api)) {
          uniqueAPIs.set(d.api, { spoofed: d.spoofed, blocked: d.blocked });
        }
      }
      const activeCount = Array.from(uniqueAPIs.values()).filter(d => d.spoofed || d.blocked).length;
      const total = uniqueAPIs.size;
      try {
        const badgeText = activeCount > 0 ? String(activeCount) : '';
        const rate = total > 0 ? (activeCount / total) * 100 : 100;
        const color = rate >= 80 ? '#10B981' : rate >= 50 ? '#F59E0B' : '#EF4444';
        browser.action.setBadgeBackgroundColor({ color, tabId });
        browser.action.setBadgeText({ text: badgeText, tabId });
      } catch {}
    }

    return { success: true };
  }

  /**
   * Store the inject script's active profile so the popup can display
   * the actual spoofed values (not the background's assigned profile).
   */
  private async handleActiveProfile(
    message: any,
    sender: browser.Runtime.MessageSender
  ): Promise<{ success: boolean }> {
    const tabId = sender.tab?.id;
    if (tabId && message.profile) {
      await browser.storage.local.set({
        [`activeProfile:${tabId}`]: {
          profile: message.profile,
          domain: message.domain,
          timestamp: Date.now(),
        },
      });
    }
    return { success: true };
  }

  private handleGetFingerprintData(
    message: GetFingerprintDataMessage,
    sender: browser.Runtime.MessageSender
  ): FingerprintData | null {
    const tabId = message.tabId ?? sender.tab?.id;
    if (!tabId) return null;
    return this.fingerprintData.get(tabId) || null;
  }

  private async handleGetRecommendations(
    message: GetRecommendationsMessage,
    sender: browser.Runtime.MessageSender
  ): Promise<RecommendationsResponse> {
    const empty: RecommendationsResponse = {
      recommendations: [],
      accessedCategories: [],
      accessedAPIs: [],
      totalAccesses: 0,
      url: '',
    };

    const tabId = message.tabId ?? sender.tab?.id;
    if (!tabId) return empty;

    let data = this.fingerprintData.get(tabId);
    // Fallback: check storage (event page may have restarted)
    if (!data) {
      try {
        const stored = await browser.storage.local.get(`fpData:${tabId}`) as Record<string, any>;
        data = stored[`fpData:${tabId}`];
        if (data) this.fingerprintData.set(tabId, data);
      } catch {}
    }
    if (!data) return empty;

    const containerId = await this.containerManager.getContainerForTab(tabId);
    const settings = this.settingsStore.getContainerSettings(containerId);

    const recommendations: SpooferRecommendation[] = [];
    const categorySet = new Set<string>();
    const seenCategories = new Set<string>();

    for (const access of data.detail) {
      if (access.category) categorySet.add(access.category);
      if (seenCategories.has(access.category)) continue;

      const settingInfo = CATEGORY_TO_SETTING[access.category];
      if (!settingInfo) continue;

      const { category, setting } = settingInfo;
      const spooferSettings = (settings.spoofers as any)[category];

      if (spooferSettings && spooferSettings[setting] === 'off') {
        recommendations.push({
          api: access.api,
          category: access.category,
          settingPath: `${category}.${setting}`,
          currentValue: 'off',
        });
        seenCategories.add(access.category);
      }
    }

    return {
      recommendations,
      accessedCategories: Array.from(categorySet),
      accessedAPIs: data.detail,
      totalAccesses: data.detail.length,
      url: data.url,
    };
  }

  /**
   * Get the assigned profile for a container, with user overrides applied
   */
  private async handleGetAssignedProfile(
    message: { containerId: string }
  ): Promise<AssignedProfileData | null> {
    const { containerId } = message;
    const settings = this.settingsStore.getContainerSettings(containerId);
    const profileSettings = settings.profile;

    let profile = getAssignedProfile(containerId);

    if (!profile) {
      const entropy = this.settingsStore.getEntropy(containerId);
      if (!entropy) return null;
      profile = await ensureUniqueProfile(entropy);
    }

    return {
      userAgent: {
        id: profile.userAgent.id,
        name: profile.userAgent.name,
        userAgent: profileSettings.userAgent || profile.userAgent.userAgent,
        platform: profileSettings.platform || profile.userAgent.platform,
        vendor: profile.userAgent.vendor,
        appVersion: profile.userAgent.appVersion,
        oscpu: profile.userAgent.oscpu,
        mobile: profile.userAgent.mobile,
        platformName: profile.userAgent.platformName,
        platformVersion: profile.userAgent.platformVersion,
        brands: profile.userAgent.brands,
      },
      screen: profileSettings.screen
        ? {
            width: profileSettings.screen.width,
            height: profileSettings.screen.height,
            availWidth: profileSettings.screen.width,
            availHeight: profileSettings.screen.height - 40,
            colorDepth: profile.screen.colorDepth || 24,
            pixelDepth: profile.screen.pixelDepth || 24,
            devicePixelRatio: profile.screen.devicePixelRatio || 1,
          }
        : {
            width: profile.screen.width,
            height: profile.screen.height,
            availWidth: profile.screen.availWidth,
            availHeight: profile.screen.availHeight,
            colorDepth: profile.screen.colorDepth,
            pixelDepth: profile.screen.pixelDepth,
            devicePixelRatio: profile.screen.devicePixelRatio,
          },
      hardwareConcurrency: profileSettings.hardwareConcurrency || profile.hardwareConcurrency,
      deviceMemory: profileSettings.deviceMemory || profile.deviceMemory,
      timezoneOffset: profileSettings.timezone && profileSettings.timezone !== 'real' && profileSettings.timezone !== 'ip'
        ? parseInt(profileSettings.timezone, 10)
        : profile.timezoneOffset,
      languages: profileSettings.language
        ? profileSettings.language.split(', ').map(l => l.trim())
        : profile.languages,
    };
  }

  /**
   * Check for fingerprint collisions between containers
   */
  private async handleCheckCollisions() {
    const detector = new CollisionDetector(this.settingsStore, this.containerManager);
    return detector.checkAllContainers();
  }
}
