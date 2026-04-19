/**
 * Firefox-specific WebExtension types
 * Augments the webextension-polyfill types
 */

import 'webextension-polyfill';

declare module 'webextension-polyfill' {
  namespace ContextualIdentities {
    interface ContextualIdentity {
      cookieStoreId: string;
      name: string;
      color: string;
      colorCode: string;
      icon: string;
    }
  }

  namespace Tabs {
    interface Tab {
      cookieStoreId?: string;
    }
  }

  namespace Privacy {
    interface NetworkPrivacyProperties {
      webRTCIPHandlingPolicy: {
        get: (details: object) => Promise<{ value: string }>;
        set: (details: { value: string }) => Promise<void>;
        clear: (details: object) => Promise<void>;
      };
    }
  }

  interface Browser {
    contextualIdentities: {
      query: (details: { name?: string }) => Promise<ContextualIdentities.ContextualIdentity[]>;
      get: (cookieStoreId: string) => Promise<ContextualIdentities.ContextualIdentity>;
      create: (details: { name: string; color: string; icon: string }) => Promise<ContextualIdentities.ContextualIdentity>;
      update: (cookieStoreId: string, details: { name?: string; color?: string; icon?: string }) => Promise<ContextualIdentities.ContextualIdentity>;
      remove: (cookieStoreId: string) => Promise<ContextualIdentities.ContextualIdentity>;
      onCreated: Events.Event<(changeInfo: { contextualIdentity: ContextualIdentities.ContextualIdentity }) => void>;
      onUpdated: Events.Event<(changeInfo: { contextualIdentity: ContextualIdentities.ContextualIdentity }) => void>;
      onRemoved: Events.Event<(changeInfo: { contextualIdentity: ContextualIdentities.ContextualIdentity }) => void>;
    };
  }
}

/**
 * WebGPU types — not yet in the standard TS DOM lib because the spec
 * is still working-draft. Cast-only shapes we use in spoofers.
 */
declare global {
  type GPUAdapter = any;
  type GPUAdapterInfo = any;
  type GPUDevice = any;
  type GPUDeviceDescriptor = any;
  type GPUSupportedLimits = any;
  type GPUSupportedFeatures = any;
  type GPURequestAdapterOptions = any;

  /**
   * BatteryManager — deprecated API Firefox removed from content but
   * which spoofers still target for fingerprint attempts.
   */
  type BatteryManager = any;
}

export {};
