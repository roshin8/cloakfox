/**
 * Shared noise utilities used by main spoofers, iframe patcher, and worker preamble.
 * Keeps noise injection DRY across all contexts.
 */

/** Add minimal pixel noise to canvas ImageData (1 byte change) */
export function addCanvasNoise(data: Uint8ClampedArray): void {
  if (data.length > 0) {
    data[0] = (data[0] + 1) % 256;
  }
}

/** Add minimal noise to a Float32Array (audio fingerprint) */
export function addAudioNoise(data: Float32Array, amount = 0.0000001): void {
  if (data.length > 0) {
    data[0] += amount;
  }
}

/**
 * Override a property on both prototype and instance with a getter.
 * Handles cases where Object.defineProperty fails on one level.
 */
export function overridePropWithGetter<T>(
  proto: object | null,
  instance: object | null,
  prop: string,
  getter: () => T
): void {
  if (proto) {
    try { Object.defineProperty(proto, prop, { get: getter, configurable: true }); } catch {}
  }
  if (instance) {
    try { Object.defineProperty(instance, prop, { get: getter, configurable: true }); } catch {}
  }
}

/**
 * Override a method on both prototype and instance.
 * Tries defineProperty first, then direct assignment.
 */
export function overrideMethodDirect(
  proto: object,
  methodName: string,
  replacement: Function
): void {
  try { Object.defineProperty(proto, methodName, { value: replacement, writable: true, configurable: true }); } catch {}
  try { (proto as any)[methodName] = replacement; } catch {}
}
