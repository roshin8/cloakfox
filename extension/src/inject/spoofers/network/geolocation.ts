/**
 * Geolocation Spoofer
 *
 * Modes:
 *   off   - No protection, real location returned
 *   noise - JShelter-style precision reduction (fuzzy location)
 *           Calls the real API, then rounds lat/lng to city-level (~1.1km)
 *           with a PRNG-based random offset so the center isn't predictable
 *   block - Deny permission (PERMISSION_DENIED error)
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

/** Fuzzed accuracy radius in meters (5 km) */
const FUZZED_ACCURACY = 5000;

/** Number of decimal places to round to (~1.1km grid) */
const ROUND_DECIMALS = 2;

/**
 * Create a Proxy-wrapped GeolocationCoordinates that returns fuzzed values.
 * Using a Proxy ensures property access looks native (no own-property leaks).
 */
function fuzzCoordinates(
  realCoords: GeolocationCoordinates,
  prng: PRNG
): GeolocationCoordinates {
  // Round to ~1.1km grid then add PRNG offset (+-0.005 deg ~ +-500m)
  const factor = Math.pow(10, ROUND_DECIMALS);
  const latRounded = Math.round(realCoords.latitude * factor) / factor;
  const lngRounded = Math.round(realCoords.longitude * factor) / factor;

  const latOffset = prng.nextNoise(0.005);
  const lngOffset = prng.nextNoise(0.005);

  const fuzzedLat = latRounded + latOffset;
  const fuzzedLng = lngRounded + lngOffset;

  const overrides: Record<string, number | null> = {
    latitude: fuzzedLat,
    longitude: fuzzedLng,
    accuracy: FUZZED_ACCURACY,
    altitude: null as unknown as number,
    altitudeAccuracy: null as unknown as number,
    heading: null as unknown as number,
    speed: null as unknown as number,
  };

  return new Proxy(realCoords, {
    get(target, prop, receiver) {
      if (typeof prop === 'string' && prop in overrides) {
        return overrides[prop];
      }
      const val = Reflect.get(target, prop, receiver);
      return typeof val === 'function' ? val.bind(target) : val;
    },
  });
}

/**
 * Create a Proxy-wrapped GeolocationPosition with fuzzed coords and
 * optional timing noise applied to the timestamp.
 */
function fuzzPosition(
  realPosition: GeolocationPosition,
  prng: PRNG
): GeolocationPosition {
  const fuzzedCoords = fuzzCoordinates(realPosition.coords, prng);

  // Small timing noise: +-50ms
  const timestampNoise = Math.round(prng.nextNoise(50));
  const fuzzedTimestamp = realPosition.timestamp + timestampNoise;

  return new Proxy(realPosition, {
    get(target, prop, receiver) {
      if (prop === 'coords') return fuzzedCoords;
      if (prop === 'timestamp') return fuzzedTimestamp;
      const val = Reflect.get(target, prop, receiver);
      return typeof val === 'function' ? val.bind(target) : val;
    },
  });
}

/**
 * Build a PERMISSION_DENIED error object matching the GeolocationPositionError shape.
 */
function makeDeniedError(): GeolocationPositionError {
  return {
    code: 1, // PERMISSION_DENIED
    message: 'User denied geolocation',
    PERMISSION_DENIED: 1,
    POSITION_UNAVAILABLE: 2,
    TIMEOUT: 3,
  } as GeolocationPositionError;
}

export function initGeolocationSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off' || !navigator.geolocation) return;

  // --- block mode: deny everything ---
  if (mode === 'block') {
    overrideMethod(navigator.geolocation, 'getCurrentPosition', (_original, _thisArg, args) => {
      logAccess('navigator.geolocation.getCurrentPosition', { blocked: true, value: 'blocked' });
      const errorCallback = args[1] as PositionErrorCallback | undefined;
      if (errorCallback) {
        errorCallback(makeDeniedError());
      }
    });

    overrideMethod(navigator.geolocation, 'watchPosition', (_original, _thisArg, args) => {
      logAccess('navigator.geolocation.watchPosition', { blocked: true, value: 'blocked' });
      const errorCallback = args[1] as PositionErrorCallback | undefined;
      if (errorCallback) {
        errorCallback(makeDeniedError());
      }
      return 0; // watchId
    });

    return;
  }

  // --- noise mode: call real API, then fuzz the result ---

  overrideMethod(navigator.geolocation, 'getCurrentPosition', (original, thisArg, args) => {
    const successCb = args[0] as PositionCallback;
    const errorCb = args[1] as PositionErrorCallback | undefined;
    const options = args[2] as PositionOptions | undefined;

    logAccess('navigator.geolocation.getCurrentPosition', { spoofed: true, value: 'city-level' });

    // Wrap the success callback to intercept the real position
    const wrappedSuccess: PositionCallback = (position) => {
      successCb(fuzzPosition(position, prng));
    };

    // Call the real API
    original.call(thisArg, wrappedSuccess, errorCb, options);
  });

  overrideMethod(navigator.geolocation, 'watchPosition', (original, thisArg, args) => {
    const successCb = args[0] as PositionCallback;
    const errorCb = args[1] as PositionErrorCallback | undefined;
    const options = args[2] as PositionOptions | undefined;

    logAccess('navigator.geolocation.watchPosition', { spoofed: true, value: 'city-level' });

    const wrappedSuccess: PositionCallback = (position) => {
      successCb(fuzzPosition(position, prng));
    };

    // Call the real watchPosition, return the real watchId so clearWatch works
    return original.call(thisArg, wrappedSuccess, errorCb, options);
  });
}
