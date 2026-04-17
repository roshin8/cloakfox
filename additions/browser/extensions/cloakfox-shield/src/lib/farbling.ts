/**
 * Farbling utilities - Brave-style noise injection
 * Adds deterministic noise to fingerprinting API outputs
 */

import { PRNG } from './crypto';

/**
 * Add noise to a single pixel value (0-255)
 * Used for canvas/image data farbling
 */
export function farblePixel(value: number, prng: PRNG, maxNoise: number = 3): number {
  const noise = prng.nextNoise(maxNoise);
  const result = Math.round(value + noise);
  return Math.max(0, Math.min(255, result));
}

/**
 * Add noise to ImageData pixel array
 * Modifies the data in place
 */
export function farbleImageData(
  imageData: Uint8ClampedArray,
  prng: PRNG,
  maxNoise: number = 3
): void {
  // Process RGB values (skip alpha channel)
  for (let i = 0; i < imageData.length; i += 4) {
    imageData[i] = farblePixel(imageData[i], prng, maxNoise); // R
    imageData[i + 1] = farblePixel(imageData[i + 1], prng, maxNoise); // G
    imageData[i + 2] = farblePixel(imageData[i + 2], prng, maxNoise); // B
    // imageData[i + 3] = alpha, unchanged
  }
}

/**
 * Add noise to a float value (e.g., AudioContext samples)
 */
export function farbleFloat(value: number, prng: PRNG, maxNoise: number = 0.0001): number {
  return value + prng.nextNoise(maxNoise);
}

/**
 * Add noise to an array of float values
 * Modifies the array in place
 */
export function farbleFloatArray(
  array: Float32Array | Float64Array,
  prng: PRNG,
  maxNoise: number = 0.0001
): void {
  for (let i = 0; i < array.length; i++) {
    array[i] = farbleFloat(array[i], prng, maxNoise);
  }
}

/**
 * Add noise to DOMRect-like values
 */
export function farbleDOMRect(
  rect: { x: number; y: number; width: number; height: number },
  prng: PRNG,
  maxNoise: number = 0.5
): { x: number; y: number; width: number; height: number } {
  return {
    x: rect.x + prng.nextNoise(maxNoise),
    y: rect.y + prng.nextNoise(maxNoise),
    width: rect.width + prng.nextNoise(maxNoise),
    height: rect.height + prng.nextNoise(maxNoise),
  };
}

/**
 * Add noise to TextMetrics-like values
 */
export function farbleTextMetrics(
  metrics: { width: number },
  prng: PRNG,
  maxNoise: number = 0.5
): { width: number } {
  return {
    width: metrics.width + prng.nextNoise(maxNoise),
  };
}

/**
 * Generate a noisy integer value within a range
 * Used for hardware values like deviceMemory, hardwareConcurrency
 */
export function farbleInteger(
  originalValue: number,
  prng: PRNG,
  minValue: number,
  maxValue: number
): number {
  // Pick a value within the valid range, biased toward the original
  const range = maxValue - minValue;
  const offset = prng.nextInt(-Math.floor(range / 4), Math.floor(range / 4));
  const result = originalValue + offset;
  return Math.max(minValue, Math.min(maxValue, result));
}

/**
 * Common screen resolution values for farbling
 */
export const COMMON_SCREEN_RESOLUTIONS = [
  { width: 1920, height: 1080 },
  { width: 1366, height: 768 },
  { width: 1536, height: 864 },
  { width: 1440, height: 900 },
  { width: 1280, height: 720 },
  { width: 1600, height: 900 },
  { width: 2560, height: 1440 },
  { width: 1280, height: 800 },
  { width: 1680, height: 1050 },
  { width: 1024, height: 768 },
];

/**
 * Pick a random screen resolution
 */
export function farbleScreenResolution(
  prng: PRNG
): { width: number; height: number } {
  return prng.pick(COMMON_SCREEN_RESOLUTIONS);
}

/**
 * Common device memory values (in GB)
 */
export const COMMON_DEVICE_MEMORY = [2, 4, 8, 16, 32];

/**
 * Pick a random device memory value
 */
export function farbleDeviceMemory(prng: PRNG): number {
  return prng.pick(COMMON_DEVICE_MEMORY);
}

/**
 * Common hardware concurrency values (CPU cores)
 */
export const COMMON_HARDWARE_CONCURRENCY = [2, 4, 6, 8, 12, 16];

/**
 * Pick a random hardware concurrency value
 */
export function farbleHardwareConcurrency(prng: PRNG): number {
  return prng.pick(COMMON_HARDWARE_CONCURRENCY);
}

/**
 * Generate noise for WebGL parameters
 * Returns consistent but different values per container+domain
 */
export function farbleWebGLParameter(
  paramName: string,
  originalValue: number | string,
  prng: PRNG
): number | string {
  if (typeof originalValue === 'string') {
    // For string values like RENDERER, we don't modify
    return originalValue;
  }

  // Add small noise to numeric parameters
  if (Number.isInteger(originalValue)) {
    return farbleInteger(originalValue, prng, Math.floor(originalValue * 0.8), Math.ceil(originalValue * 1.2));
  }

  return farbleFloat(originalValue, prng, originalValue * 0.01);
}

/**
 * Generate consistent timezone offset
 * Returns an offset in minutes (e.g., -480 for UTC-8)
 */
export const COMMON_TIMEZONE_OFFSETS = [
  -720, // UTC-12
  -660, // UTC-11
  -600, // UTC-10 (Hawaii)
  -540, // UTC-9 (Alaska)
  -480, // UTC-8 (Pacific)
  -420, // UTC-7 (Mountain)
  -360, // UTC-6 (Central)
  -300, // UTC-5 (Eastern)
  -240, // UTC-4 (Atlantic)
  -180, // UTC-3 (Brazil)
  0, // UTC
  60, // UTC+1 (Central Europe)
  120, // UTC+2 (Eastern Europe)
  180, // UTC+3 (Moscow)
  330, // UTC+5:30 (India)
  480, // UTC+8 (China/Singapore)
  540, // UTC+9 (Japan/Korea)
  600, // UTC+10 (Australia East)
];

/**
 * Pick a random timezone offset
 */
export function farbleTimezoneOffset(prng: PRNG): number {
  return prng.pick(COMMON_TIMEZONE_OFFSETS);
}
