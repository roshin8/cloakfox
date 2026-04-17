/**
 * Shared constants for Cloakfox Shield
 */

/**
 * Default cookie store ID for non-containerized tabs
 */
export const DEFAULT_COOKIE_STORE_ID = 'firefox-default';

/**
 * Private browsing cookie store ID
 */
export const PRIVATE_COOKIE_STORE_ID = 'firefox-private';

/**
 * Storage keys
 */
export const STORAGE_KEYS = {
  GLOBAL_SETTINGS: 'cloakfox_shield_global_settings',
  CONTAINER_SETTINGS: 'cloakfox_shield_container_settings',
  ENTROPY: 'cloakfox_shield_entropy',
  IP_DATABASE: 'cloakfox_shield_ip_database',
  VERSION: 'cloakfox_shield_version',
} as const;

/**
 * Extension version
 */
export const EXTENSION_VERSION = '0.5.0';

/**
 * Protection level names
 */
export const PROTECTION_LEVEL_NAMES = {
  0: 'Off',
  1: 'Minimal',
  2: 'Balanced',
  3: 'Strict',
} as const;

/**
 * Protection level descriptions
 */
export const PROTECTION_LEVEL_DESCRIPTIONS = {
  0: 'No protection - all APIs work normally',
  1: 'Header spoofing only - no JavaScript wrapping',
  2: 'Noise injection for fingerprinting APIs (recommended)',
  3: 'Block or fake all fingerprintable APIs',
} as const;

/**
 * Firefox container colors
 */
export const CONTAINER_COLORS = {
  blue: '#37adff',
  turquoise: '#00c79a',
  green: '#51cd00',
  yellow: '#ffcb00',
  orange: '#ff9f00',
  red: '#ff613d',
  pink: '#ff4bda',
  purple: '#af51f5',
} as const;

/**
 * Firefox container icons
 */
export const CONTAINER_ICONS = [
  'fingerprint',
  'briefcase',
  'dollar',
  'cart',
  'circle',
  'gift',
  'vacation',
  'food',
  'fruit',
  'pet',
  'tree',
  'chill',
  'fence',
] as const;

/**
 * Message passing timeout (ms)
 */
export const MESSAGE_TIMEOUT = 5000;

/**
 * Maximum URLs to store per IP in the IP database
 */
export const MAX_IP_URL_HISTORY = 10;

/**
 * Regex patterns for IP address detection
 */
export const IP_PATTERNS = {
  IPV4: /^(\d{1,3}\.){3}\d{1,3}$/,
  IPV6: /^(\[)?([0-9a-fA-F:]+)(\])?$/,
  LOCAL_IPV4: /^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)/,
  LOCALHOST: /^(127\.|::1|localhost)/i,
} as const;

/**
 * WebRTC IP handling policy values
 */
export const WEBRTC_POLICIES = {
  DEFAULT: 'default',
  PUBLIC_ONLY: 'default_public_interface_only',
  DISABLE: 'disable_non_proxied_udp',
} as const;

/**
 * WebGL parameter constants
 */
export const GL = {
  VENDOR: 0x1F00,
  RENDERER: 0x1F01,
  UNMASKED_VENDOR: 0x9245,
  UNMASKED_RENDERER: 0x9246,
} as const;

/**
 * Timezone offset-to-IANA mapping (standard offsets, not DST-adjusted)
 */
export const TIMEZONE_IANA: Record<number, string> = {
  [-720]: 'Etc/GMT+12',
  [-660]: 'Pacific/Midway',
  [-600]: 'Pacific/Honolulu',
  [-570]: 'Pacific/Marquesas',
  [-540]: 'America/Anchorage',
  [-480]: 'America/Los_Angeles',
  [-420]: 'America/Denver',
  [-360]: 'America/Chicago',
  [-300]: 'America/New_York',
  [-240]: 'America/Halifax',
  [-210]: 'America/St_Johns',
  [-180]: 'America/Sao_Paulo',
  [-120]: 'Atlantic/South_Georgia',
  [-60]: 'Atlantic/Azores',
  [0]: 'UTC',
  [60]: 'Europe/Paris',
  [120]: 'Europe/Helsinki',
  [180]: 'Europe/Moscow',
  [210]: 'Asia/Tehran',
  [240]: 'Asia/Dubai',
  [270]: 'Asia/Kabul',
  [300]: 'Asia/Karachi',
  [330]: 'Asia/Kolkata',
  [345]: 'Asia/Kathmandu',
  [360]: 'Asia/Dhaka',
  [390]: 'Asia/Yangon',
  [420]: 'Asia/Bangkok',
  [480]: 'Asia/Shanghai',
  [540]: 'Asia/Tokyo',
  [570]: 'Australia/Adelaide',
  [600]: 'Australia/Sydney',
  [660]: 'Pacific/Guadalcanal',
  [720]: 'Pacific/Auckland',
  [780]: 'Pacific/Apia',
};
