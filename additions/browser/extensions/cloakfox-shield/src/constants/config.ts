/**
 * Configuration constants
 *
 * All magic numbers, timeouts, limits, and other configuration values
 * should be defined here.
 */

// Fingerprint monitor settings
export const FINGERPRINT_REPORT_INTERVAL_MS = 5000;
export const FINGERPRINT_MAX_LOG_SIZE = 1000;
export const FINGERPRINT_STACK_TRACE_LINES = 4;

// Popup refresh interval
export const POPUP_REFRESH_INTERVAL_MS = 5000;

// Entropy/Seed settings
export const SEED_LENGTH_BYTES = 32;
export const HASH_LENGTH_BYTES = 32;

// Profile manager settings
export const MAX_PROFILE_COLLISION_ATTEMPTS = 100;

// Storage keys
export const STORAGE_KEY_CONTAINERS = 'containers';
export const STORAGE_KEY_ENTROPY = 'entropy';
export const STORAGE_KEY_DEFAULTS = 'defaults';
export const STORAGE_KEY_IP_DATABASE = 'ipDatabase';
export const STORAGE_KEY_VERSION = 'version';

// IP isolation settings
export const DEFAULT_MAX_URL_HISTORY = 10;

// Common screen resolutions (used by screen spoofer)
export const COMMON_SCREEN_RESOLUTIONS = [
  { width: 1920, height: 1080 },
  { width: 1366, height: 768 },
  { width: 1536, height: 864 },
  { width: 1440, height: 900 },
  { width: 1280, height: 720 },
  { width: 2560, height: 1440 },
  { width: 1680, height: 1050 },
  { width: 1280, height: 800 },
] as const;

// Common device memory values (GB)
export const COMMON_DEVICE_MEMORY_VALUES = [2, 4, 8, 16] as const;

// Common hardware concurrency values (CPU cores)
export const COMMON_HARDWARE_CONCURRENCY_VALUES = [2, 4, 6, 8, 12, 16] as const;

// Common timezone offsets (minutes)
export const COMMON_TIMEZONE_OFFSETS = [
  -480, // PST
  -420, // MST
  -360, // CST
  -300, // EST
  0,    // UTC
  60,   // CET
  120,  // EET
  330,  // IST
  480,  // CST (China)
  540,  // JST
] as const;

// Audio latency values (seconds)
export const COMMON_AUDIO_LATENCIES = [
  0.005333333333333333, // ~256 samples at 48kHz
  0.010666666666666666, // ~512 samples at 48kHz
  0.021333333333333333, // ~1024 samples at 48kHz
  0.002666666666666667, // ~128 samples at 48kHz
] as const;

// Extension version
export const EXTENSION_VERSION = '0.3.0';

// Console log prefix
export const LOG_PREFIX = '[CloakfoxShield]';
