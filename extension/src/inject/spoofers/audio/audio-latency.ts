/**
 * Audio Latency Spoofer
 *
 * Spoofs AudioContext latency properties which can be used for fingerprinting.
 * - audioContext.baseLatency
 * - audioContext.outputLatency
 * - audioContext.sampleRate (already covered but included for completeness)
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

// Common base latency values (in seconds)
const COMMON_LATENCIES = [
  0.005333333333333333, // ~256 samples at 48kHz
  0.010666666666666666, // ~512 samples at 48kHz
  0.021333333333333333, // ~1024 samples at 48kHz
  0.002666666666666667, // ~128 samples at 48kHz
];

/**
 * Initialize audio latency spoofing
 */
export function initAudioLatencySpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Select consistent spoofed values
  const latencyIndex = Math.floor(prng.nextFloat() * COMMON_LATENCIES.length);
  const spoofedBaseLatency = mode === 'block' ? 0 : COMMON_LATENCIES[latencyIndex];
  const spoofedOutputLatency = mode === 'block' ? 0 : spoofedBaseLatency * (1 + prng.nextFloat() * 0.5);
  const spoofedSampleRate = prng.pick([44100, 48000]);

  // Store original AudioContext
  const OriginalAudioContext = window.AudioContext || (window as any).webkitAudioContext;

  if (!OriginalAudioContext) return;

  // Create a proxy for AudioContext
  const AudioContextProxy = function (this: any, options?: AudioContextOptions) {
    const ctx = new OriginalAudioContext(options);

    // Spoof baseLatency
    try {
      Object.defineProperty(ctx, 'baseLatency', {
        get: function () {
          logAccess('AudioContext.baseLatency', { spoofed: true, value: `${spoofedSampleRate}Hz, ${spoofedBaseLatency.toFixed(4)}s` });
          return spoofedBaseLatency;
        },
        configurable: true,
      });
    } catch {
      // Can't override
    }

    // Spoof outputLatency
    try {
      Object.defineProperty(ctx, 'outputLatency', {
        get: function () {
          logAccess('AudioContext.outputLatency', { spoofed: true, value: `${spoofedOutputLatency.toFixed(4)}s` });
          return spoofedOutputLatency;
        },
        configurable: true,
      });
    } catch {}

    // Spoof sampleRate
    try {
      Object.defineProperty(ctx, 'sampleRate', {
        get: function () {
          return spoofedSampleRate;
        },
        configurable: true,
      });
    } catch {}

    return ctx;
  };

  // Copy static properties and prototype
  AudioContextProxy.prototype = OriginalAudioContext.prototype;
  Object.setPrototypeOf(AudioContextProxy, OriginalAudioContext);

  // Replace AudioContext
  try {
    (window as any).AudioContext = AudioContextProxy;
    if ((window as any).webkitAudioContext) {
      (window as any).webkitAudioContext = AudioContextProxy;
    }
  } catch {
    // Can't replace
  }

}
