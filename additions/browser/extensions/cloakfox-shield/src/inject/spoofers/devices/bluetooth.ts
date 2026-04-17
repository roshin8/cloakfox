/**
 * Bluetooth API Spoofer
 *
 * Bluetooth device enumeration can reveal connected devices.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize Bluetooth API spoofing
 */
export function initBluetoothSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Spoof navigator.bluetooth
  if ('bluetooth' in navigator) {
    const bluetooth = (navigator as any).bluetooth;

    if (bluetooth) {
      // Spoof getAvailability
      if (bluetooth.getAvailability) {
        const originalGetAvailability = bluetooth.getAvailability.bind(bluetooth);

        bluetooth.getAvailability = async function (): Promise<boolean> {
          logAccess('navigator.bluetooth.getAvailability', { spoofed: mode !== 'block' });

          if (mode === 'block') {
            return false; // Pretend Bluetooth is not available
          }

          return originalGetAvailability();
        };
      }

      // Spoof requestDevice
      if (bluetooth.requestDevice) {
        const originalRequestDevice = bluetooth.requestDevice.bind(bluetooth);

        bluetooth.requestDevice = async function (options?: RequestDeviceOptions): Promise<BluetoothDevice> {
          logAccess('navigator.bluetooth.requestDevice', { spoofed: mode !== 'block' });

          if (mode === 'block') {
            throw new DOMException('Permission denied', 'NotAllowedError');
          }

          return originalRequestDevice(options);
        };
      }

      // Spoof getDevices
      if (bluetooth.getDevices) {
        const originalGetDevices = bluetooth.getDevices.bind(bluetooth);

        bluetooth.getDevices = async function (): Promise<BluetoothDevice[]> {
          logAccess('navigator.bluetooth.getDevices', { spoofed: mode !== 'block' });

          if (mode === 'block') {
            return []; // No paired devices
          }

          return originalGetDevices();
        };
      }
    }
  }

}
