// Re-export all types
export * from './settings';

/**
 * Message types for communication between extension components
 */
export type MessageType =
  | 'GET_SETTINGS'
  | 'SET_SETTINGS'
  | 'GET_ENTROPY'
  | 'GET_CONTAINER_INFO'
  | 'GET_ALL_CONTAINERS'
  | 'IP_CONFLICT_CHECK'
  | 'GET_SPOOF_CONFIG'
  | 'FINGERPRINT_REPORT'
  | 'GET_FINGERPRINT_DATA'
  | 'GET_RECOMMENDATIONS'
  | 'GET_ASSIGNED_PROFILE'
  | 'CHECK_COLLISIONS';

/**
 * Fingerprint access record
 */
export interface FingerprintAccess {
  api: string;
  category: string;
  timestamp: number;
  blocked: boolean;
  spoofed: boolean;
  stackTrace?: string;
  value?: string;
}

/**
 * Fingerprint access summary
 */
export interface FingerprintSummary {
  [category: string]: {
    count: number;
    blocked: number;
    spoofed: number;
  };
}

/**
 * Fingerprint data stored per tab
 */
export interface FingerprintData {
  summary: FingerprintSummary;
  detail: FingerprintAccess[];
  url: string;
  lastUpdated: number;
}

/**
 * Spoofer recommendation
 */
export interface SpooferRecommendation {
  api: string;
  category: string;
  settingPath: string;
  currentValue: string;
}

/**
 * Recommendations response
 */
export interface RecommendationsResponse {
  recommendations: SpooferRecommendation[];
  accessedCategories: string[];
  accessedAPIs: FingerprintAccess[];  // Specific API accesses for detailed view
  totalAccesses: number;
  url: string;
}

/**
 * Base message structure
 */
export interface BaseMessage {
  type: MessageType;
}

/**
 * Get settings request
 */
export interface GetSettingsMessage extends BaseMessage {
  type: 'GET_SETTINGS';
  containerId: string;
  domain?: string;
}

/**
 * Set settings request
 */
export interface SetSettingsMessage extends BaseMessage {
  type: 'SET_SETTINGS';
  containerId: string;
  settings: Partial<import('./settings').ContainerSettings>;
}

/**
 * Get entropy request
 */
export interface GetEntropyMessage extends BaseMessage {
  type: 'GET_ENTROPY';
  containerId: string;
}

/**
 * Get container info request
 */
export interface GetContainerInfoMessage extends BaseMessage {
  type: 'GET_CONTAINER_INFO';
  tabId?: number;
}

/**
 * Get all containers request
 */
export interface GetAllContainersMessage extends BaseMessage {
  type: 'GET_ALL_CONTAINERS';
}

/**
 * IP conflict check request
 */
export interface IPConflictCheckMessage extends BaseMessage {
  type: 'IP_CONFLICT_CHECK';
  ip: string;
  containerId: string;
}

/**
 * Assigned profile for a container (unique across all containers)
 */
export interface AssignedProfileData {
  userAgent: {
    id: string;
    name: string;
    userAgent: string;
    platform: string;
    vendor: string;
    appVersion: string;
    oscpu?: string;
    mobile: boolean;
    platformName: string;
    platformVersion: string;
    brands?: { brand: string; version: string }[];
  };
  screen: {
    width: number;
    height: number;
    availWidth: number;
    availHeight: number;
    colorDepth: number;
    pixelDepth: number;
    devicePixelRatio: number;
  };
  hardwareConcurrency: number;
  deviceMemory?: number; // undefined for Firefox profiles (Firefox doesn't expose this API)
  timezoneOffset: number;
  languages: string[];
}

/**
 * Config to inject into page context
 */
export interface InjectConfig {
  containerId: string;
  domain: string;
  seed: string;
  settings: import('./settings').SpooferSettings;
  profile: import('./settings').ProfileConfig;
  assignedProfile?: AssignedProfileData;
}

/**
 * Inject config message
 */
export interface InjectConfigMessage extends BaseMessage {
  type: 'GET_SPOOF_CONFIG';
}

/**
 * Fingerprint report message
 */
export interface FingerprintReportMessage extends BaseMessage {
  type: 'FINGERPRINT_REPORT';
  summary: FingerprintSummary;
  detail: FingerprintAccess[];
  url: string;
}

/**
 * Get fingerprint data message
 */
export interface GetFingerprintDataMessage extends BaseMessage {
  type: 'GET_FINGERPRINT_DATA';
  tabId?: number;
}

/**
 * Get recommendations message
 */
export interface GetRecommendationsMessage extends BaseMessage {
  type: 'GET_RECOMMENDATIONS';
  tabId?: number;
}

/**
 * Union of all message types
 */
/**
 * Get assigned profile message
 */
export interface GetAssignedProfileMessage extends BaseMessage {
  type: 'GET_ASSIGNED_PROFILE';
  containerId: string;
}

/**
 * Check collisions message
 */
export interface CheckCollisionsMessage extends BaseMessage {
  type: 'CHECK_COLLISIONS';
}

export type ExtensionMessage =
  | GetSettingsMessage
  | SetSettingsMessage
  | GetEntropyMessage
  | GetContainerInfoMessage
  | GetAllContainersMessage
  | IPConflictCheckMessage
  | InjectConfigMessage
  | FingerprintReportMessage
  | GetFingerprintDataMessage
  | GetRecommendationsMessage
  | GetAssignedProfileMessage
  | CheckCollisionsMessage;

/**
 * Firefox container identity
 */
export interface ContainerIdentity {
  cookieStoreId: string;
  name: string;
  color: string;
  colorCode: string;
  icon: string;
}
