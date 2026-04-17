/**
 * Network Information Spoofer
 *
 * The Network Information API reveals connection type, speed,
 * and data saver mode which can be used for fingerprinting.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

type ConnectionType = 'bluetooth' | 'cellular' | 'ethernet' | 'none' | 'wifi' | 'wimax' | 'other' | 'unknown';
type EffectiveType = 'slow-2g' | '2g' | '3g' | '4g';

interface NetworkInformationLike {
  type: ConnectionType;
  effectiveType: EffectiveType;
  downlink: number;
  downlinkMax: number;
  rtt: number;
  saveData: boolean;
  onchange: ((this: any, ev: Event) => void) | null;
  addEventListener: (type: string, listener: EventListener) => void;
  removeEventListener: (type: string, listener: EventListener) => void;
}

/**
 * Initialize Network Information spoofing
 */
export function initNetworkSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Check if Network Information API exists
  if (!('connection' in navigator)) return;

  // Common connection profiles
  const profiles = [
    { type: 'wifi' as ConnectionType, effectiveType: '4g' as EffectiveType, downlink: 10, rtt: 50 },
    { type: 'wifi' as ConnectionType, effectiveType: '4g' as EffectiveType, downlink: 5, rtt: 100 },
    { type: 'ethernet' as ConnectionType, effectiveType: '4g' as EffectiveType, downlink: 100, rtt: 20 },
    { type: 'wifi' as ConnectionType, effectiveType: '3g' as EffectiveType, downlink: 1.5, rtt: 200 },
  ];

  const selectedProfile = prng.pick(profiles);

  if (mode === 'block') {
    // Remove the connection property entirely
    try {
      Object.defineProperty(navigator, 'connection', {
        value: undefined,
        configurable: true,
      });
    } catch {
      // Can't remove, leave as is
    }
    return;
  }

  // Create a fake NetworkInformation object
  const fakeConnection: NetworkInformationLike = {
    type: selectedProfile.type,
    effectiveType: selectedProfile.effectiveType,
    downlink: selectedProfile.downlink,
    downlinkMax: Infinity,
    rtt: selectedProfile.rtt,
    saveData: false,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
  };

  // Create a proxy to log access
  const proxyHandler: ProxyHandler<NetworkInformationLike> = {
    get(target, prop) {
      logAccess('navigator.connection', { spoofed: true, value: `${selectedProfile.type}/${selectedProfile.effectiveType}` });
      return target[prop as keyof NetworkInformationLike];
    },
  };

  const fakeConnectionProxy = new Proxy(fakeConnection, proxyHandler);

  // Override on both prototype and instance for maximum coverage
  try {
    Object.defineProperty(Navigator.prototype, 'connection', {
      get: () => fakeConnectionProxy,
      configurable: true,
      enumerable: true,
    });
  } catch {}
  try {
    Object.defineProperty(navigator, 'connection', {
      get: () => fakeConnectionProxy,
      configurable: true,
      enumerable: true,
    });
  } catch {}

}
