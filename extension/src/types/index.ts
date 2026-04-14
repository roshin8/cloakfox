/** Container identity from Firefox contextualIdentities API */
export interface ContainerIdentity {
  cookieStoreId: string;
  name: string;
  color: string;
  icon: string;
}

/** Assigned browser profile for a container */
export interface AssignedProfile {
  userAgent: {
    userAgent: string;
    platform: string;
    oscpu: string;
    appVersion: string;
  };
  screen: {
    width: number;
    height: number;
    availWidth: number;
    availHeight: number;
    colorDepth: number;
    pixelDepth: number;
  };
  hardwareConcurrency: number;
  deviceMemory: number;
  maxTouchPoints: number;
  language: string;
  languages: string[];
  timezone: string;
  webgl: {
    vendor: string;
    renderer: string;
  };
}

/** Per-category spoofer settings */
export interface SpooferSettings {
  graphics?: {
    canvas?: 'off' | 'noise' | 'block';
    webgl?: 'off' | 'noise' | 'block';
  };
  audio?: {
    context?: 'off' | 'noise' | 'block';
  };
  navigator?: {
    userAgent?: 'off' | 'spoof';
    platform?: 'off' | 'spoof';
    hardwareConcurrency?: 'off' | 'spoof';
  };
  hardware?: {
    screen?: 'off' | 'spoof';
  };
  fonts?: {
    enumeration?: 'off' | 'filter';
    metrics?: 'off' | 'noise';
  };
  network?: {
    webrtc?: 'off' | 'spoof' | 'block';
  };
  timing?: {
    timezone?: 'off' | 'spoof';
  };
}

/** Config injected into MAIN world via window.__CLOAKFOX__ */
export interface CloakfoxConfig {
  seed: string;
  domain: string;
  profile: AssignedProfile;
  settings: SpooferSettings;
}

/** Container entropy stored in extension storage */
export interface ContainerEntropy {
  seed: string;
  createdAt: number;
  rotateAfter?: number;
}

/** Messages between extension components */
export type CloakfoxMessage =
  | { type: 'CLOAKFOX_ACTIVE'; domain: string }
  | { type: 'CLOAKFOX_FINGERPRINT_ACCESS'; category: string; api: string }
  | { type: 'CLOAKFOX_GET_STATUS'; tabId: number }
  | { type: 'CLOAKFOX_STATUS'; active: boolean; domain: string; containerId: string };

/**
 * Cloakfox self-destructing window methods.
 * Each method is exposed via WebIDL, stores its value in RoverfoxStorageManager
 * keyed by mUserContextId, then sets itself to undefined on the global.
 */
export interface CloakfoxWindow extends Window {
  setCanvasSeed?: (seed: number) => void;
  setAudioFingerprintSeed?: (seed: number) => void;
  setNavigatorPlatform?: (platform: string) => void;
  setNavigatorUserAgent?: (ua: string) => void;
  setNavigatorOscpu?: (oscpu: string) => void;
  setNavigatorHardwareConcurrency?: (cores: number) => void;
  setScreenDimensions?: (width: number, height: number) => void;
  setScreenColorDepth?: (depth: number) => void;
  setFontList?: (fonts: string) => void;
  setFontSpacingSeed?: (seed: number) => void;
  setWebGLVendor?: (vendor: string) => void;
  setWebGLRenderer?: (renderer: string) => void;
  setWebRTCIPv4?: (ip: string) => void;
  setWebRTCIPv6?: (ip: string) => void;
  setTimezone?: (tz: string) => void;
  setSpeechVoices?: (voices: string) => void;
  __CLOAKFOX__?: CloakfoxConfig;
}
