/**
 * MediaDevices Spoofer - Spoofs available media devices
 * enumerateDevices reveals:
 * - Number of cameras/microphones
 * - Device IDs (persistent identifiers)
 * - Device labels (can reveal hardware info)
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize MediaDevices spoofing
 */
export function initMediaDevicesSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Check if MediaDevices API exists
  if (!navigator.mediaDevices?.enumerateDevices) {
    return;
  }

  const originalEnumerateDevices = navigator.mediaDevices.enumerateDevices.bind(
    navigator.mediaDevices
  );

  if (mode === 'block') {
    // Return empty device list
    navigator.mediaDevices.enumerateDevices = async function (): Promise<
      MediaDeviceInfo[]
    > {
      logAccess('navigator.mediaDevices.enumerateDevices', { spoofed: false, blocked: true, value: '0 devices' });
      return [];
    };

    return;
  }

  // Noise mode - return fake devices with randomized IDs
  navigator.mediaDevices.enumerateDevices = async function (): Promise<
    MediaDeviceInfo[]
  > {
    const realDevices = await originalEnumerateDevices();
    logAccess('navigator.mediaDevices.enumerateDevices', { spoofed: true, value: `${realDevices.length} devices` });

    // Generate consistent fake device IDs based on seed
    const fakeDevices: MediaDeviceInfo[] = realDevices.map((device, index) => {
      // Generate a fake device ID
      const fakeId = generateFakeDeviceId(prng, device.kind, index);

      // Create a fake MediaDeviceInfo-like object
      return {
        deviceId: fakeId,
        groupId: generateFakeDeviceId(prng, 'group', index),
        kind: device.kind,
        label: '', // Hide device labels for privacy
        toJSON: function () {
          return {
            deviceId: this.deviceId,
            groupId: this.groupId,
            kind: this.kind,
            label: this.label,
          };
        },
      } as MediaDeviceInfo;
    });

    // Optionally add or remove devices to mask the real count
    const shouldModifyCount = prng.nextFloat() > 0.7;

    if (shouldModifyCount) {
      const hasVideoInput = fakeDevices.some((d) => d.kind === 'videoinput');
      const hasAudioInput = fakeDevices.some((d) => d.kind === 'audioinput');
      const hasAudioOutput = fakeDevices.some((d) => d.kind === 'audiooutput');

      // Add a fake device if missing
      if (!hasVideoInput && prng.nextFloat() > 0.5) {
        fakeDevices.push(createFakeDevice(prng, 'videoinput', fakeDevices.length));
      }
      if (!hasAudioInput && prng.nextFloat() > 0.5) {
        fakeDevices.push(createFakeDevice(prng, 'audioinput', fakeDevices.length));
      }
      if (!hasAudioOutput && prng.nextFloat() > 0.5) {
        fakeDevices.push(createFakeDevice(prng, 'audiooutput', fakeDevices.length));
      }
    }

    return fakeDevices;
  };

}

/**
 * Generate a fake device ID
 */
function generateFakeDeviceId(prng: PRNG, prefix: string, index: number): string {
  const chars = '0123456789abcdef';
  let id = '';

  // Generate 64-character hex string
  for (let i = 0; i < 64; i++) {
    id += chars[prng.nextInt(0, 15)];
  }

  return id;
}

/**
 * Create a fake MediaDeviceInfo object
 */
function createFakeDevice(
  prng: PRNG,
  kind: MediaDeviceKind,
  index: number
): MediaDeviceInfo {
  return {
    deviceId: generateFakeDeviceId(prng, kind, index),
    groupId: generateFakeDeviceId(prng, 'group', index),
    kind,
    label: '',
    toJSON: function () {
      return {
        deviceId: this.deviceId,
        groupId: this.groupId,
        kind: this.kind,
        label: this.label,
      };
    },
  } as MediaDeviceInfo;
}
