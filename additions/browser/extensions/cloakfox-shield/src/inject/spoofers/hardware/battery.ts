/**
 * Battery API Spoofer - Blocks or spoofs battery information
 * Battery status can be used for fingerprinting based on:
 * - Charging state
 * - Battery level
 * - Charge/discharge times
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize Battery API spoofing
 */
export function initBatterySpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Check if Battery API exists
  if (!('getBattery' in navigator)) {
    return;
  }

  if (mode === 'block') {
    // Remove getBattery entirely
    Object.defineProperty(navigator, 'getBattery', {
      value: undefined,
      configurable: true,
      writable: true,
    });

    return;
  }

  // Noise mode - return fake battery info
  const originalGetBattery = (navigator.getBattery as () => Promise<any>).bind(navigator);

  // Generate consistent fake battery values for this container+domain
  const fakeBattery = {
    charging: prng.nextFloat() > 0.5,
    chargingTime: prng.nextFloat() > 0.5 ? Infinity : prng.nextInt(0, 7200),
    dischargingTime: prng.nextFloat() > 0.5 ? Infinity : prng.nextInt(3600, 36000),
    level: Math.round(prng.nextFloatRange(0.2, 1.0) * 100) / 100,
  };

  // Create a fake BatteryManager-like object
  const createFakeBatteryManager = (): BatteryManager => {
    const eventTarget = new EventTarget();

    const batteryManager = {
      charging: fakeBattery.charging,
      chargingTime: fakeBattery.chargingTime,
      dischargingTime: fakeBattery.dischargingTime,
      level: fakeBattery.level,

      // Event handlers
      onchargingchange: null as ((this: BatteryManager, ev: Event) => any) | null,
      onchargingtimechange: null as ((this: BatteryManager, ev: Event) => any) | null,
      ondischargingtimechange: null as ((this: BatteryManager, ev: Event) => any) | null,
      onlevelchange: null as ((this: BatteryManager, ev: Event) => any) | null,

      // EventTarget methods
      addEventListener: eventTarget.addEventListener.bind(eventTarget),
      removeEventListener: eventTarget.removeEventListener.bind(eventTarget),
      dispatchEvent: eventTarget.dispatchEvent.bind(eventTarget),
    };

    return batteryManager as BatteryManager;
  };

  // Override getBattery
  Object.defineProperty(navigator, 'getBattery', {
    value: async function (): Promise<BatteryManager> {
      logAccess('navigator.getBattery', { spoofed: true, value: `${Math.round(fakeBattery.level * 100)}% ${fakeBattery.charging ? 'charging' : 'discharging'}` });
      return createFakeBatteryManager();
    },
    configurable: true,
    writable: true,
  });

}
