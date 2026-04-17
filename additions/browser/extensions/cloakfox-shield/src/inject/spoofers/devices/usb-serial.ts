/**
 * USB, Serial, and HID API Spoofer
 *
 * These APIs can enumerate connected devices for fingerprinting.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize USB API spoofing
 */
export function initUSBSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Spoof navigator.usb
  if ('usb' in navigator) {
    const usb = (navigator as any).usb;

    if (usb) {
      // Spoof getDevices
      if (usb.getDevices) {
        const originalGetDevices = usb.getDevices.bind(usb);

        usb.getDevices = async function (): Promise<any[]> {
          logAccess('navigator.usb.getDevices', { spoofed: mode !== 'block' });

          if (mode === 'block') {
            return [];
          }

          return originalGetDevices();
        };
      }

      // Spoof requestDevice
      if (usb.requestDevice) {
        const originalRequestDevice = usb.requestDevice.bind(usb);

        usb.requestDevice = async function (options?: any): Promise<any> {
          logAccess('navigator.usb.requestDevice', { spoofed: mode !== 'block' });

          if (mode === 'block') {
            throw new DOMException('No device selected', 'NotFoundError');
          }

          return originalRequestDevice(options);
        };
      }
    }
  }

}

/**
 * Initialize Serial API spoofing
 */
export function initSerialSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Spoof navigator.serial
  if ('serial' in navigator) {
    const serial = (navigator as any).serial;

    if (serial) {
      // Spoof getPorts
      if (serial.getPorts) {
        const originalGetPorts = serial.getPorts.bind(serial);

        serial.getPorts = async function (): Promise<any[]> {
          logAccess('navigator.serial.getPorts', { spoofed: mode !== 'block' });

          if (mode === 'block') {
            return [];
          }

          return originalGetPorts();
        };
      }

      // Spoof requestPort
      if (serial.requestPort) {
        const originalRequestPort = serial.requestPort.bind(serial);

        serial.requestPort = async function (options?: any): Promise<any> {
          logAccess('navigator.serial.requestPort', { spoofed: mode !== 'block' });

          if (mode === 'block') {
            throw new DOMException('No port selected', 'NotFoundError');
          }

          return originalRequestPort(options);
        };
      }
    }
  }

}

/**
 * Initialize HID API spoofing
 */
export function initHIDSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Spoof navigator.hid
  if ('hid' in navigator) {
    const hid = (navigator as any).hid;

    if (hid) {
      // Spoof getDevices
      if (hid.getDevices) {
        const originalGetDevices = hid.getDevices.bind(hid);

        hid.getDevices = async function (): Promise<any[]> {
          logAccess('navigator.hid.getDevices', { spoofed: mode !== 'block' });

          if (mode === 'block') {
            return [];
          }

          return originalGetDevices();
        };
      }

      // Spoof requestDevice
      if (hid.requestDevice) {
        const originalRequestDevice = hid.requestDevice.bind(hid);

        hid.requestDevice = async function (options?: any): Promise<any[]> {
          logAccess('navigator.hid.requestDevice', { spoofed: mode !== 'block' });

          if (mode === 'block') {
            return [];
          }

          return originalRequestDevice(options);
        };
      }
    }
  }

}
