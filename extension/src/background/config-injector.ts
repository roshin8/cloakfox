/**
 * Config Injector — delivers container-specific seeds and profiles
 * to the MAIN world inject script before page scripts run.
 *
 * Uses browser.scripting.executeScript with injectImmediately: true
 * to win the race against page scripts.
 */

import type { CloakfoxConfig } from '@/types';

interface ConfigDeps {
  getContainerForTab(tabId: number): Promise<string>;
  getEntropySeed(cookieStoreId: string): Promise<string>;
  getAssignedProfile(cookieStoreId: string): Promise<CloakfoxConfig['profile']>;
  getSettingsForDomain(
    cookieStoreId: string,
    domain: string
  ): Promise<CloakfoxConfig['settings']>;
}

export class ConfigInjector {
  private deps: ConfigDeps;

  constructor(deps: ConfigDeps) {
    this.deps = deps;

    browser.webNavigation.onCommitted.addListener((details) => {
      // Only inject for top-level and subframe navigations
      if (details.url.startsWith('http://') || details.url.startsWith('https://')) {
        this.injectConfig(details.tabId, details.frameId, details.url);
      }
    });
  }

  private async injectConfig(
    tabId: number,
    frameId: number,
    url: string
  ): Promise<void> {
    try {
      const domain = new URL(url).hostname;
      const cookieStoreId = await this.deps.getContainerForTab(tabId);
      const [seed, profile, settings] = await Promise.all([
        this.deps.getEntropySeed(cookieStoreId),
        this.deps.getAssignedProfile(cookieStoreId),
        this.deps.getSettingsForDomain(cookieStoreId, domain),
      ]);

      const config: CloakfoxConfig = { seed, domain, profile, settings };

      await browser.scripting.executeScript({
        target: { tabId, frameIds: [frameId] },
        world: 'MAIN',
        injectImmediately: true,
        func: (cfg: CloakfoxConfig) => {
          (window as Record<string, unknown>).__CLOAKFOX__ = cfg;
        },
        args: [config],
      });
    } catch {
      // Tab may have closed or navigated away — silently ignore
    }
  }
}
