/**
 * Sensor APIs Spoofer
 *
 * Spoofs device sensor APIs which can reveal hardware characteristics:
 * - Accelerometer
 * - Gyroscope
 * - Magnetometer
 * - AbsoluteOrientationSensor
 * - RelativeOrientationSensor
 * - LinearAccelerationSensor
 * - GravitySensor
 * - AmbientLightSensor
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Create a fake sensor class that blocks or returns noise
 */
function createFakeSensor(
  sensorName: string,
  mode: ProtectionMode,
  prng: PRNG,
  readingProperties: string[]
): any {
  return class FakeSensor {
    private _activated = false;
    private _hasReading = false;
    private _timestamp: number | null = null;
    private _onreading: ((event: Event) => void) | null = null;
    private _onactivate: ((event: Event) => void) | null = null;
    private _onerror: ((event: Event) => void) | null = null;

    constructor(options?: any) {
      logAccess(`${sensorName}.constructor`, { spoofed: true });

      // Generate fake reading values
      for (const prop of readingProperties) {
        Object.defineProperty(this, prop, {
          get: () => {
            if (!this._hasReading) return null;
            // Return small noise values
            return (prng.nextFloat() - 0.5) * 0.01;
          },
          configurable: true,
        });
      }
    }

    get activated() {
      return this._activated;
    }

    get hasReading() {
      return this._hasReading;
    }

    get timestamp() {
      return this._timestamp;
    }

    set onreading(handler: ((event: Event) => void) | null) {
      this._onreading = handler;
    }

    get onreading() {
      return this._onreading;
    }

    set onactivate(handler: ((event: Event) => void) | null) {
      this._onactivate = handler;
    }

    get onactivate() {
      return this._onactivate;
    }

    set onerror(handler: ((event: Event) => void) | null) {
      this._onerror = handler;
    }

    get onerror() {
      return this._onerror;
    }

    start() {
      logAccess(`${sensorName}.start`, { spoofed: true });

      if (mode === 'block') {
        // Fire error event
        setTimeout(() => {
          if (this._onerror) {
            const errorEvent = new Event('error');
            (errorEvent as any).error = new DOMException(
              'Sensor access denied',
              'NotAllowedError'
            );
            this._onerror(errorEvent);
          }
        }, 0);
        return;
      }

      this._activated = true;
      this._hasReading = true;
      this._timestamp = performance.now();

      // Fire activate event
      setTimeout(() => {
        if (this._onactivate) {
          this._onactivate(new Event('activate'));
        }
        // Fire initial reading
        if (this._onreading) {
          this._onreading(new Event('reading'));
        }
      }, 0);
    }

    stop() {
      logAccess(`${sensorName}.stop`, { spoofed: true });
      this._activated = false;
    }

    addEventListener(type: string, listener: EventListener) {
      if (type === 'reading') this._onreading = listener;
      if (type === 'activate') this._onactivate = listener;
      if (type === 'error') this._onerror = listener;
    }

    removeEventListener(type: string, listener: EventListener) {
      if (type === 'reading' && this._onreading === listener) this._onreading = null;
      if (type === 'activate' && this._onactivate === listener) this._onactivate = null;
      if (type === 'error' && this._onerror === listener) this._onerror = null;
    }
  };
}

/**
 * Initialize sensor API spoofing
 */
export function initSensorSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Accelerometer
  if ('Accelerometer' in window) {
    try {
      (window as any).Accelerometer = createFakeSensor(
        'Accelerometer',
        mode,
        prng,
        ['x', 'y', 'z']
      );
    } catch {
      // Can't override
    }
  }

  // LinearAccelerationSensor
  if ('LinearAccelerationSensor' in window) {
    try {
      (window as any).LinearAccelerationSensor = createFakeSensor(
        'LinearAccelerationSensor',
        mode,
        prng,
        ['x', 'y', 'z']
      );
    } catch {
      // Can't override
    }
  }

  // GravitySensor
  if ('GravitySensor' in window) {
    try {
      (window as any).GravitySensor = createFakeSensor(
        'GravitySensor',
        mode,
        prng,
        ['x', 'y', 'z']
      );
    } catch {
      // Can't override
    }
  }

  // Gyroscope
  if ('Gyroscope' in window) {
    try {
      (window as any).Gyroscope = createFakeSensor(
        'Gyroscope',
        mode,
        prng,
        ['x', 'y', 'z']
      );
    } catch {
      // Can't override
    }
  }

  // Magnetometer
  if ('Magnetometer' in window) {
    try {
      (window as any).Magnetometer = createFakeSensor(
        'Magnetometer',
        mode,
        prng,
        ['x', 'y', 'z']
      );
    } catch {
      // Can't override
    }
  }

  // AbsoluteOrientationSensor
  if ('AbsoluteOrientationSensor' in window) {
    try {
      (window as any).AbsoluteOrientationSensor = createFakeSensor(
        'AbsoluteOrientationSensor',
        mode,
        prng,
        ['quaternion']
      );
    } catch {
      // Can't override
    }
  }

  // RelativeOrientationSensor
  if ('RelativeOrientationSensor' in window) {
    try {
      (window as any).RelativeOrientationSensor = createFakeSensor(
        'RelativeOrientationSensor',
        mode,
        prng,
        ['quaternion']
      );
    } catch {
      // Can't override
    }
  }

  // AmbientLightSensor
  if ('AmbientLightSensor' in window) {
    try {
      (window as any).AmbientLightSensor = createFakeSensor(
        'AmbientLightSensor',
        mode,
        prng,
        ['illuminance']
      );
    } catch {
      // Can't override
    }
  }

  // DeviceMotionEvent
  if ('DeviceMotionEvent' in window) {
    const originalAddEventListener = window.addEventListener;
    window.addEventListener = function (
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | AddEventListenerOptions
    ) {
      if (type === 'devicemotion') {
        logAccess('DeviceMotionEvent', { spoofed: true, blocked: mode === 'block' });
        if (mode === 'block') {
          return; // Don't add the listener
        }
      }
      return originalAddEventListener.call(window, type, listener, options);
    };
  }

  // DeviceOrientationEvent
  if ('DeviceOrientationEvent' in window) {
    const originalAddEventListener = window.addEventListener;
    window.addEventListener = function (
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | AddEventListenerOptions
    ) {
      if (type === 'deviceorientation' || type === 'deviceorientationabsolute') {
        logAccess('DeviceOrientationEvent', { spoofed: true, blocked: mode === 'block' });
        if (mode === 'block') {
          return; // Don't add the listener
        }
      }
      return originalAddEventListener.call(window, type, listener, options);
    };
  }

}
