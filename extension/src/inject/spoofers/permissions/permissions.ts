/**
 * Permissions API Spoofer
 *
 * The permissions.query() API can reveal which permissions have been
 * granted, denied, or prompted, creating a unique fingerprint.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

type PermissionState = 'granted' | 'denied' | 'prompt';

// Default permission states that look normal
const DEFAULT_PERMISSIONS: Record<string, PermissionState> = {
  'geolocation': 'prompt',
  'notifications': 'prompt',
  'push': 'prompt',
  'midi': 'prompt',
  'camera': 'prompt',
  'microphone': 'prompt',
  'speaker-selection': 'prompt',
  'device-info': 'prompt',
  'background-fetch': 'prompt',
  'background-sync': 'prompt',
  'bluetooth': 'prompt',
  'persistent-storage': 'prompt',
  'ambient-light-sensor': 'prompt',
  'accelerometer': 'prompt',
  'gyroscope': 'prompt',
  'magnetometer': 'prompt',
  'clipboard-read': 'prompt',
  'clipboard-write': 'granted', // Usually granted by default
  'payment-handler': 'prompt',
  'idle-detection': 'prompt',
  'periodic-background-sync': 'prompt',
  'screen-wake-lock': 'prompt',
  'nfc': 'prompt',
};

/**
 * Initialize Permissions API spoofing
 */
export function initPermissionsSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  if (!('permissions' in navigator)) return;

  const originalQuery = navigator.permissions.query.bind(navigator.permissions);

  navigator.permissions.query = async function (
    permissionDesc: PermissionDescriptor
  ): Promise<PermissionStatus> {
    logAccess('navigator.permissions.query', { spoofed: true, value: 'spoofed' });

    const name = permissionDesc.name;

    if (mode === 'block') {
      // Always return 'prompt' to hide actual state
      return createFakePermissionStatus('prompt', name);
    }

    // Return a realistic default state
    const state = DEFAULT_PERMISSIONS[name] || 'prompt';
    return createFakePermissionStatus(state, name);
  };

}

/**
 * Create a fake PermissionStatus object
 */
function createFakePermissionStatus(
  state: PermissionState,
  name: string
): PermissionStatus {
  const status = {
    state,
    name,
    onchange: null as ((this: PermissionStatus, ev: Event) => void) | null,
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => true,
  };

  return status as unknown as PermissionStatus;
}
