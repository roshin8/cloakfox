/**
 * Device Spoofer - Spoofs hardware concurrency and device memory
 * Uses assigned profile for guaranteed uniqueness across containers
 */

import type { ProtectionMode, AssignedProfileData } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { farbleDeviceMemory, farbleHardwareConcurrency } from '@/lib/farbling';
import { logAccess, markHardwareSpoofed } from '../../monitor/fingerprint-monitor';

/**
 * Initialize device spoofing
 */
export function initDeviceSpoofer(
  deviceMemoryMode: ProtectionMode,
  hardwareConcurrencyMode: ProtectionMode,
  prng: PRNG,
  assignedProfile?: AssignedProfileData
): void {
  // Update any early monitoring entries to reflect spoofed status
  if (deviceMemoryMode !== 'off' || hardwareConcurrencyMode !== 'off') {
    markHardwareSpoofed(deviceMemoryMode !== 'off' ? deviceMemoryMode : hardwareConcurrencyMode);
  }

  // Spoof deviceMemory - use assigned profile for guaranteed uniqueness
  if (deviceMemoryMode !== 'off') {
    let spoofedMemory: number;

    if (assignedProfile?.deviceMemory) {
      // Use assigned profile value - guaranteed unique across containers
      spoofedMemory = assignedProfile.deviceMemory;
    } else if (deviceMemoryMode === 'block') {
      spoofedMemory = 8;
    } else {
      spoofedMemory = farbleDeviceMemory(prng);
    }

    Object.defineProperty(navigator, 'deviceMemory', {
      get: () => { logAccess('navigator.deviceMemory', { spoofed: true, value: `${spoofedMemory}GB` }); return spoofedMemory; },
      configurable: true,
      enumerable: true,
    });

  }

  // Spoof hardwareConcurrency - use assigned profile for guaranteed uniqueness
  if (hardwareConcurrencyMode !== 'off') {
    let spoofedConcurrency: number;

    if (assignedProfile?.hardwareConcurrency) {
      // Use assigned profile value - guaranteed unique across containers
      spoofedConcurrency = assignedProfile.hardwareConcurrency;
    } else if (hardwareConcurrencyMode === 'block') {
      spoofedConcurrency = 4;
    } else {
      spoofedConcurrency = farbleHardwareConcurrency(prng);
    }

    Object.defineProperty(navigator, 'hardwareConcurrency', {
      get: () => { logAccess('navigator.hardwareConcurrency', { spoofed: true, value: `${spoofedConcurrency} cores` }); return spoofedConcurrency; },
      configurable: true,
      enumerable: true,
    });

  }

  // maxTouchPoints is handled by the touch spoofer (hardware/touch.ts)
}
