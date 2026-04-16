/**
 * Notification API Spoofer
 *
 * Spoofs Notification.permission and requestPermission to prevent
 * fingerprinting via notification permission state.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize Notification API spoofing
 */
export function initNotificationSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  if (typeof Notification === 'undefined') return;

  // Spoof Notification.permission
  const spoofedPermission: NotificationPermission = mode === 'block' ? 'default' : 'default';

  try {
    Object.defineProperty(Notification, 'permission', {
      get: function () {
        logAccess('Notification.permission', { spoofed: true, value: spoofedPermission });
        return spoofedPermission;
      },
      configurable: true,
    });
  } catch {
    // Can't override
  }

  // Spoof Notification.requestPermission
  const originalRequestPermission = Notification.requestPermission;

  Notification.requestPermission = function (
    deprecatedCallback?: NotificationPermissionCallback
  ): Promise<NotificationPermission> {
    logAccess('Notification.requestPermission', { spoofed: true, value: spoofedPermission });

    if (mode === 'block') {
      const result: NotificationPermission = 'denied';
      if (deprecatedCallback) {
        deprecatedCallback(result);
      }
      return Promise.resolve(result);
    }

    return originalRequestPermission.call(Notification, deprecatedCallback);
  };

  // Spoof maxActions
  try {
    Object.defineProperty(Notification, 'maxActions', {
      get: function () {
        logAccess('Notification.maxActions', { spoofed: true, value: spoofedPermission });
        return 2; // Common value
      },
      configurable: true,
    });
  } catch {
    // Can't override
  }

}
