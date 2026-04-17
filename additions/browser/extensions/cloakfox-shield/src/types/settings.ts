/**
 * Protection mode for each fingerprinting signal
 */
export type ProtectionMode = 'off' | 'noise' | 'block';

/**
 * WebRTC protection modes
 */
export type WebRTCMode = 'off' | 'public_only' | 'block';

/**
 * Protection level presets
 * 0 = Off - No protection
 * 1 = Minimal - Headers only, no JS wrapping
 * 2 = Balanced - Noise injection (recommended)
 * 3 = Strict - Block/fake all fingerprintable APIs
 */
export type ProtectionLevel = 0 | 1 | 2 | 3;

/**
 * Profile mode for browser identity
 */
export type ProfileMode = 'real' | 'preset' | 'random' | 'custom';

/**
 * Referer policy options
 */
export type RefererPolicy = 'off' | 'origin' | 'same-origin';

/**
 * Browser profile configuration
 */
export interface ProfileConfig {
  mode: ProfileMode;
  userAgent?: string;
  platform?: string;
  language?: string;
  timezone?: string | 'real' | 'ip';
  screen?: { width: number; height: number };
  hardwareConcurrency?: number;
  deviceMemory?: number;
  gpu?: { vendor: string; renderer: string };
}

/**
 * X-Forwarded-For header mode
 */
export type XForwardedForMode = 'random' | 'custom' | 'range';

/**
 * Header spoofing configuration
 */
export interface HeaderConfig {
  spoofUserAgent: boolean;
  spoofAcceptLanguage: boolean;
  refererPolicy: RefererPolicy;
  disableEtag: boolean;
  sendDNT: boolean;
  spoofXForwardedFor: boolean;
  xForwardedForMode: XForwardedForMode;
  xForwardedForValue: string;
  spoofVia: boolean;
}

/**
 * Graphics spoofer settings
 */
export interface GraphicsSpoofers {
  canvas: ProtectionMode;
  offscreenCanvas: ProtectionMode;
  webgl: ProtectionMode;
  webgl2: ProtectionMode;
  webglShaders: ProtectionMode;
  webgpu: ProtectionMode;
  svg: ProtectionMode;
  domRect: ProtectionMode;
  textMetrics: ProtectionMode;
}

/**
 * Audio spoofer settings
 */
export interface AudioSpoofers {
  audioContext: ProtectionMode;
  offlineAudio: ProtectionMode;
  latency: ProtectionMode;
  codecs: ProtectionMode;
}

/**
 * Hardware spoofer settings
 */
export interface HardwareSpoofers {
  screen: ProtectionMode;
  screenFrame: ProtectionMode;
  screenExtended: ProtectionMode;
  orientation: ProtectionMode;
  deviceMemory: ProtectionMode;
  hardwareConcurrency: ProtectionMode;
  mediaDevices: ProtectionMode;
  battery: ProtectionMode;
  gpu: ProtectionMode;
  touch: ProtectionMode;
  sensors: ProtectionMode;
  architecture: ProtectionMode;
  visualViewport: ProtectionMode;
}

/**
 * Navigator spoofer settings
 */
export interface NavigatorSpoofers {
  userAgent: ProtectionMode;
  languages: ProtectionMode;
  plugins: ProtectionMode;
  clientHints: ProtectionMode;
  clipboard: ProtectionMode;
  vibration: ProtectionMode;
  vendorFlavors: ProtectionMode;
  fontPreferences: ProtectionMode;
  windowName: ProtectionMode;
  tabHistory: ProtectionMode;
  mediaCapabilities: ProtectionMode;
}

/**
 * Timezone spoofer settings
 */
export interface TimezoneSpoofers {
  intl: ProtectionMode;
  date: ProtectionMode;
}

/**
 * Font spoofer settings
 */
export interface FontSpoofers {
  enumeration: ProtectionMode;
  cssDetection: ProtectionMode;
}

/**
 * Network spoofer settings
 */
export interface NetworkSpoofers {
  webrtc: WebRTCMode;
  connection: ProtectionMode;
  geolocation: ProtectionMode;
  websocket: ProtectionMode;
}

/**
 * Timing spoofer settings
 */
export interface TimingSpoofers {
  performance: ProtectionMode;
  memory: ProtectionMode;
  eventLoop: ProtectionMode;
}

/**
 * CSS spoofer settings
 */
export interface CssSpoofers {
  mediaQueries: ProtectionMode;
}

/**
 * Speech spoofer settings
 */
export interface SpeechSpoofers {
  synthesis: ProtectionMode;
}

/**
 * Permissions spoofer settings
 */
export interface PermissionsSpoofers {
  query: ProtectionMode;
  notification: ProtectionMode;
}

/**
 * Storage spoofer settings
 */
export interface StorageSpoofers {
  estimate: ProtectionMode;
  indexedDB: ProtectionMode;
  webSQL: ProtectionMode;
  privateModeProtection: ProtectionMode;
}

/**
 * Math spoofer settings
 */
export interface MathSpoofers {
  functions: ProtectionMode;
}

/**
 * Keyboard spoofer settings
 */
export interface KeyboardSpoofers {
  layout: ProtectionMode;
  cadence: ProtectionMode;
}

/**
 * Workers spoofer settings
 */
export interface WorkersSpoofers {
  fingerprint: ProtectionMode;
  serviceWorker: ProtectionMode;
}

/**
 * Errors spoofer settings
 */
export interface ErrorsSpoofers {
  stackTrace: ProtectionMode;
}

/**
 * Rendering spoofer settings
 */
export interface RenderingSpoofers {
  emoji: ProtectionMode;
  mathml: ProtectionMode;
}

/**
 * Intl spoofer settings
 */
export interface IntlSpoofers {
  apis: ProtectionMode;
}

/**
 * Crypto spoofer settings
 */
export interface CryptoSpoofers {
  webCrypto: ProtectionMode;
}

/**
 * Devices spoofer settings
 */
export interface DevicesSpoofers {
  gamepad: ProtectionMode;
  midi: ProtectionMode;
  bluetooth: ProtectionMode;
  usb: ProtectionMode;
  serial: ProtectionMode;
  hid: ProtectionMode;
}

/**
 * Features spoofer settings
 */
export interface FeaturesSpoofers {
  detection: ProtectionMode;
}

/**
 * Payment spoofer settings
 */
export interface PaymentSpoofers {
  applePay: ProtectionMode;
}

/**
 * All spoofer settings organized by category
 */
export interface SpooferSettings {
  graphics: GraphicsSpoofers;
  audio: AudioSpoofers;
  hardware: HardwareSpoofers;
  navigator: NavigatorSpoofers;
  timezone: TimezoneSpoofers;
  fonts: FontSpoofers;
  network: NetworkSpoofers;
  timing: TimingSpoofers;
  css: CssSpoofers;
  speech: SpeechSpoofers;
  permissions: PermissionsSpoofers;
  storage: StorageSpoofers;
  math: MathSpoofers;
  keyboard: KeyboardSpoofers;
  workers: WorkersSpoofers;
  errors: ErrorsSpoofers;
  rendering: RenderingSpoofers;
  intl: IntlSpoofers;
  crypto: CryptoSpoofers;
  devices: DevicesSpoofers;
  features: FeaturesSpoofers;
  payment: PaymentSpoofers;
}

/**
 * Settings for a single container
 */
export interface ContainerSettings {
  enabled: boolean;
  protectionLevel: ProtectionLevel;
  useCoreEngine: boolean; // Use C++ Core spoofing when available (falls back to JS if off)
  profile: ProfileConfig;
  headers: HeaderConfig;
  spoofers: SpooferSettings;
  domainRules: Record<string, Partial<ContainerSettings>>;
}

/**
 * Per-container entropy (cryptographic seed for fingerprint generation)
 */
export interface ContainerEntropy {
  cookieStoreId: string;
  seed: string; // Base64-encoded 32-byte seed
  createdAt: number;
  rotatedAt?: number;
}

/**
 * IP address record for IP isolation feature
 */
export interface IPRecord {
  ip: string;
  containerId: string;
  containerName: string;
  firstAccessed: number;
  lastAccessed: number;
  accessCount: number;
  urls: string[];
}

/**
 * IP isolation settings
 */
export interface IPIsolationSettings {
  enabled: boolean;
  warnOnly: boolean;
  trackLocalIPs: boolean;
  trackLocalhostIPs: boolean;
  maxUrlHistory: number;
  autoProtectNewContainers: boolean;
  similarityThreshold: number;
}

/**
 * IP database stored in browser.storage.local
 */
export interface IPDatabase {
  ipRecords: Record<string, IPRecord>;
  settings: IPIsolationSettings;
  exceptions: string[];
  trackedDomains: string[];
}

/**
 * Global extension storage
 */
export interface GlobalStorage {
  containers: Record<string, ContainerSettings>;
  entropy: Record<string, ContainerEntropy>;
  defaults: ContainerSettings;
  ipDatabase: IPDatabase;
  version: string;
}

/**
 * Default settings factory
 */
export function createDefaultSettings(): ContainerSettings {
  return {
    enabled: true,
    protectionLevel: 2, // Balanced
    useCoreEngine: true, // Use C++ Core when available
    profile: {
      mode: 'random',
    },
    headers: {
      spoofUserAgent: true,
      spoofAcceptLanguage: true,
      refererPolicy: 'same-origin',
      disableEtag: true,
      sendDNT: false,
      spoofXForwardedFor: false,
      xForwardedForMode: 'random',
      xForwardedForValue: '',
      spoofVia: false,
    },
    spoofers: {
      graphics: {
        canvas: 'noise',
        offscreenCanvas: 'noise',
        webgl: 'noise',
        webgl2: 'noise',
        webglShaders: 'noise',
        webgpu: 'noise',
        svg: 'noise',
        domRect: 'noise',
        textMetrics: 'noise',
      },
      audio: {
        audioContext: 'noise',
        offlineAudio: 'noise',
        latency: 'noise',
        codecs: 'noise',
      },
      hardware: {
        screen: 'noise',
        screenFrame: 'noise',
        screenExtended: 'noise',
        orientation: 'noise',
        deviceMemory: 'noise',
        hardwareConcurrency: 'noise',
        mediaDevices: 'noise',
        battery: 'noise',
        gpu: 'noise',
        touch: 'noise',
        sensors: 'noise',
        architecture: 'noise',
        visualViewport: 'noise',
      },
      navigator: {
        userAgent: 'noise',
        languages: 'noise',
        plugins: 'noise',
        clientHints: 'noise',
        clipboard: 'noise',
        vibration: 'noise',
        vendorFlavors: 'noise',
        fontPreferences: 'noise',
        windowName: 'noise',
        tabHistory: 'noise',
        mediaCapabilities: 'noise',
      },
      timezone: {
        intl: 'noise',
        date: 'noise',
      },
      fonts: {
        enumeration: 'noise',
        cssDetection: 'noise',
      },
      network: {
        webrtc: 'public_only',
        connection: 'noise',
        geolocation: 'noise',
        websocket: 'noise',
      },
      timing: {
        performance: 'noise',
        memory: 'noise',
        eventLoop: 'noise',
      },
      css: {
        mediaQueries: 'noise',
      },
      speech: {
        synthesis: 'noise',
      },
      permissions: {
        query: 'noise',
        notification: 'noise',
      },
      storage: {
        estimate: 'noise',
        indexedDB: 'noise',
        webSQL: 'noise',
        privateModeProtection: 'noise',
      },
      math: {
        functions: 'noise',
      },
      keyboard: {
        layout: 'noise',
        cadence: 'noise',
      },
      workers: {
        fingerprint: 'noise',
        serviceWorker: 'noise',
      },
      errors: {
        stackTrace: 'noise',
      },
      rendering: {
        emoji: 'noise',
        mathml: 'noise',
      },
      intl: {
        apis: 'noise',
      },
      crypto: {
        webCrypto: 'noise',
      },
      devices: {
        gamepad: 'noise',
        midi: 'noise',
        bluetooth: 'noise',
        usb: 'noise',
        serial: 'noise',
        hid: 'noise',
      },
      features: {
        detection: 'noise',
      },
      payment: {
        applePay: 'noise',
      },
    },
    domainRules: {},
  };
}

/**
 * Create default IP isolation settings
 */
export function createDefaultIPSettings(): IPIsolationSettings {
  return {
    enabled: true,
    warnOnly: false,
    trackLocalIPs: true,
    trackLocalhostIPs: false,
    maxUrlHistory: 10,
    autoProtectNewContainers: true,
    similarityThreshold: 30,
  };
}
