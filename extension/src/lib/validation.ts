/**
 * Input validation utilities
 *
 * Provides type-safe validation for messages and data
 * to ensure runtime safety and proper error handling.
 */

import type {
  ExtensionMessage,
  FingerprintAccess,
  FingerprintSummary,
  SpooferSettings,
  ContainerSettings,
} from '@/types';
import { createLogger } from './logger';

const logger = createLogger('Validation');

/**
 * Validation result
 */
export interface ValidationResult<T> {
  valid: boolean;
  data?: T;
  error?: string;
}

/**
 * Check if a value is a non-null object
 */
export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Check if a value is a non-empty string
 */
export function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

/**
 * Check if a value is a valid number
 */
export function isNumber(value: unknown): value is number {
  return typeof value === 'number' && !isNaN(value);
}

/**
 * Check if a value is a positive integer
 */
export function isPositiveInteger(value: unknown): value is number {
  return isNumber(value) && Number.isInteger(value) && value > 0;
}

/**
 * Check if a value is a valid tab ID
 */
export function isValidTabId(value: unknown): value is number {
  return isNumber(value) && Number.isInteger(value) && value >= 0;
}

/**
 * Check if a value is a valid container ID
 */
export function isValidContainerId(value: unknown): value is string {
  if (!isNonEmptyString(value)) return false;
  // Firefox container IDs are either 'firefox-default' or 'firefox-container-N'
  return value === 'firefox-default' || /^firefox-container-\d+$/.test(value);
}

/**
 * Check if a value is a valid URL
 */
export function isValidUrl(value: unknown): value is string {
  if (!isNonEmptyString(value)) return false;
  try {
    new URL(value);
    return true;
  } catch {
    return false;
  }
}

/**
 * Check if a value is a valid domain
 */
export function isValidDomain(value: unknown): value is string {
  if (!isNonEmptyString(value)) return false;
  // Basic domain validation
  return /^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$/.test(value);
}

/**
 * Check if a value is a valid protection mode
 */
export function isValidProtectionMode(value: unknown): value is 'off' | 'noise' | 'block' {
  return value === 'off' || value === 'noise' || value === 'block';
}

/**
 * Check if a value is a valid WebRTC mode
 */
export function isValidWebRTCMode(value: unknown): value is 'off' | 'public_only' | 'block' {
  return value === 'off' || value === 'public_only' || value === 'block';
}

/**
 * Check if a value is a valid protection level
 */
export function isValidProtectionLevel(value: unknown): value is 0 | 1 | 2 | 3 {
  return value === 0 || value === 1 || value === 2 || value === 3;
}

/**
 * Validate an extension message has a valid type
 */
export function validateMessageType(message: unknown): ValidationResult<ExtensionMessage> {
  if (!isObject(message)) {
    return { valid: false, error: 'Message must be an object' };
  }

  if (!isNonEmptyString(message.type)) {
    return { valid: false, error: 'Message must have a type property' };
  }

  const validTypes = [
    'GET_SETTINGS',
    'SET_SETTINGS',
    'GET_ENTROPY',
    'GET_CONTAINER_INFO',
    'GET_ALL_CONTAINERS',
    'IP_CONFLICT_CHECK',
    'INJECT_CONFIG',
    'FINGERPRINT_REPORT',
    'GET_FINGERPRINT_DATA',
    'GET_RECOMMENDATIONS',
  ];

  if (!validTypes.includes(message.type as string)) {
    return { valid: false, error: `Unknown message type: ${message.type}` };
  }

  return { valid: true, data: message as ExtensionMessage };
}

/**
 * Validate GET_SETTINGS message
 */
export function validateGetSettingsMessage(
  message: unknown
): ValidationResult<{ containerId: string; domain?: string }> {
  if (!isObject(message)) {
    return { valid: false, error: 'Message must be an object' };
  }

  if (!isValidContainerId(message.containerId)) {
    return { valid: false, error: 'Invalid containerId' };
  }

  if (message.domain !== undefined && !isValidDomain(message.domain)) {
    return { valid: false, error: 'Invalid domain' };
  }

  return {
    valid: true,
    data: {
      containerId: message.containerId as string,
      domain: message.domain as string | undefined,
    },
  };
}

/**
 * Validate fingerprint access object
 */
export function validateFingerprintAccess(
  access: unknown
): ValidationResult<FingerprintAccess> {
  if (!isObject(access)) {
    return { valid: false, error: 'Access must be an object' };
  }

  if (!isNonEmptyString(access.api)) {
    return { valid: false, error: 'Access must have an api property' };
  }

  if (!isNonEmptyString(access.category)) {
    return { valid: false, error: 'Access must have a category property' };
  }

  if (!isNumber(access.timestamp)) {
    return { valid: false, error: 'Access must have a timestamp property' };
  }

  return {
    valid: true,
    data: {
      api: access.api as string,
      category: access.category as string,
      timestamp: access.timestamp as number,
      blocked: Boolean(access.blocked),
      spoofed: Boolean(access.spoofed),
      stackTrace: access.stackTrace as string | undefined,
    },
  };
}

/**
 * Validate fingerprint summary object
 */
export function validateFingerprintSummary(
  summary: unknown
): ValidationResult<FingerprintSummary> {
  if (!isObject(summary)) {
    return { valid: false, error: 'Summary must be an object' };
  }

  const validatedSummary: FingerprintSummary = {};

  for (const [category, stats] of Object.entries(summary)) {
    if (!isObject(stats)) {
      return { valid: false, error: `Invalid stats for category: ${category}` };
    }

    validatedSummary[category] = {
      count: isNumber(stats.count) ? stats.count : 0,
      blocked: isNumber(stats.blocked) ? stats.blocked : 0,
      spoofed: isNumber(stats.spoofed) ? stats.spoofed : 0,
    };
  }

  return { valid: true, data: validatedSummary };
}

/**
 * Sanitize a string to prevent XSS
 */
export function sanitizeString(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Validate and sanitize user input
 */
export function validateAndSanitize(
  value: unknown,
  maxLength: number = 1000
): ValidationResult<string> {
  if (!isNonEmptyString(value)) {
    return { valid: false, error: 'Value must be a non-empty string' };
  }

  if (value.length > maxLength) {
    return { valid: false, error: `Value exceeds maximum length of ${maxLength}` };
  }

  return { valid: true, data: sanitizeString(value) };
}
