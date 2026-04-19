/**
 * Background script entry point for Cloakfox Shield
 */

import browser from 'webextension-polyfill';
import { ContainerManager } from './container-manager';
import { SettingsStore } from './settings-store';
import { HeaderSpoofer } from './header-spoofer';
import { IPIsolation } from './ip-isolation';
import { MessageHandler } from './message-handler';
import { initProfileManager } from './profile-manager';
import { ProfileRotation } from './profile-rotation';
import { StatisticsStore } from './statistics-store';
import { getBadgeManager } from './badge-manager';
import { ContextMenuManager } from './context-menu';
import { KeyboardShortcuts } from './keyboard-shortcuts';
import { EXTENSION_VERSION, STORAGE_KEYS } from '@/lib/constants';
// SW injection via filterResponseData doesn't work in Firefox (can't intercept SW scripts)
// ServiceWorker spoof mode rejects SW → falls back to SharedWorker (spoofed)

async function init(): Promise<void> {
  console.log(`[Cloakfox Shield] Initializing v${EXTENSION_VERSION}`);

  try {
    const settingsStore = new SettingsStore();
    await settingsStore.init();

    const containerManager = new ContainerManager(settingsStore);
    await containerManager.init();

    await initProfileManager();

    const headerSpoofer = new HeaderSpoofer(settingsStore, containerManager);
    await headerSpoofer.init();


    const ipIsolation = new IPIsolation(settingsStore, containerManager);
    await ipIsolation.init();

    const profileRotation = new ProfileRotation(settingsStore);
    await profileRotation.init();

    const statisticsStore = new StatisticsStore();
    // StatisticsStore lazily loads on first access, no explicit init needed.

    const messageHandler = new MessageHandler(
      settingsStore, containerManager, ipIsolation, profileRotation, statisticsStore
    );
    messageHandler.init();

    const badgeManager = getBadgeManager();
    await badgeManager.init();

    const contextMenuManager = new ContextMenuManager(settingsStore, containerManager);
    await contextMenuManager.init();

    const keyboardShortcuts = new KeyboardShortcuts(settingsStore);
    keyboardShortcuts.init();

    await checkFirstRun();
    await checkTestMode();

    await browser.storage.local.set({ [STORAGE_KEYS.VERSION]: EXTENSION_VERSION });
  } catch (error) {
    console.error('[Cloakfox Shield] Initialization failed:', error);
  }
}

async function checkFirstRun(): Promise<void> {
  const { onboardingComplete } = await browser.storage.local.get('onboardingComplete');
  if (!onboardingComplete) {
    await browser.tabs.create({ url: browser.runtime.getURL('pages/onboarding.html') });
  }
}

/** Listen for test runner open requests */
async function checkTestMode(): Promise<void> {
  browser.runtime.onMessage.addListener((msg: any) => {
    if (msg.type === 'OPEN_TEST_RUNNER') {
      browser.storage.local.set({ onboardingComplete: true });
      const only = msg.only ? `?only=${encodeURIComponent(msg.only)}` : '';
      browser.tabs.create({ url: browser.runtime.getURL(`pages/test-runner.html${only}`) });
      return Promise.resolve({ opened: true });
    }
  });
}

init();
