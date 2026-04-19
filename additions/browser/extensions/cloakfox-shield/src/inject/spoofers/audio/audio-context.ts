/**
 * Audio Context Spoofer - Adds noise to AudioContext fingerprinting
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { farbleFloatArray } from '@/lib/farbling';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize audio context spoofing
 */
export function initAudioSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Wrap AnalyserNode.getFloatFrequencyData
  overrideMethod(AnalyserNode.prototype, 'getFloatFrequencyData', (original, thisArg, args) => {
    const array = args[0] as Float32Array;
    logAccess('AnalyserNode.getFloatFrequencyData', { blocked: mode === 'block', spoofed: mode === 'noise' });

    if (mode === 'block') {
      array.fill(-Infinity);
      return;
    }

    original.call(thisArg, array);
    farbleFloatArray(array, prng, 0.0001);
  });

  // Wrap AnalyserNode.getByteFrequencyData
  overrideMethod(AnalyserNode.prototype, 'getByteFrequencyData', (original, thisArg, args) => {
    const array = args[0] as Uint8Array;

    if (mode === 'block') {
      array.fill(0);
      return;
    }

    original.call(thisArg, array);

    // Add small noise to byte values
    for (let i = 0; i < array.length; i++) {
      const noise = Math.round(prng.nextNoise(2));
      array[i] = Math.max(0, Math.min(255, array[i] + noise));
    }
  });

  // Wrap AnalyserNode.getFloatTimeDomainData
  overrideMethod(AnalyserNode.prototype, 'getFloatTimeDomainData', (original, thisArg, args) => {
    const array = args[0] as Float32Array;

    if (mode === 'block') {
      array.fill(0);
      return;
    }

    original.call(thisArg, array);
    farbleFloatArray(array, prng, 0.0001);
  });

  // Wrap AudioBuffer.getChannelData
  overrideMethod(AudioBuffer.prototype, 'getChannelData', (original, thisArg, args) => {
    const channel = args[0] as number;
    const data = original.call(thisArg, channel) as Float32Array;

    if (mode === 'block') {
      return new Float32Array(data.length);
    }

    // Create a copy and add noise
    const noisyData = new Float32Array(data);
    farbleFloatArray(noisyData, prng, 0.0001);
    return noisyData;
  });

  // Wrap OfflineAudioContext.startRendering
  if (typeof OfflineAudioContext !== 'undefined') {
    overrideMethod(OfflineAudioContext.prototype, 'startRendering', async (original, thisArg, _args) => {
      logAccess('OfflineAudioContext.startRendering', { blocked: mode === 'block', spoofed: mode === 'noise' });

      const buffer = await original.call(thisArg) as AudioBuffer;

      if (mode === 'block') {
        // Return silent buffer
        return buffer;
      }

      // Add noise to all channels
      for (let c = 0; c < buffer.numberOfChannels; c++) {
        const channelData = buffer.getChannelData(c);
        farbleFloatArray(channelData, prng, 0.0001);
      }

      return buffer;
    });
  }

  // Patch getOutputTimestamp to add noise
  if (typeof AudioContext !== 'undefined' && 'getOutputTimestamp' in AudioContext.prototype) {
    overrideMethod(AudioContext.prototype, 'getOutputTimestamp', (original, thisArg, _args) => {
      const ts = original.call(thisArg);
      logAccess('AudioContext.getOutputTimestamp', { spoofed: true });
      if (mode === 'block') return { contextTime: 0, performanceTime: 0 };
      return {
        contextTime: ts.contextTime + prng.nextFloat() * 0.0001,
        performanceTime: ts.performanceTime + prng.nextFloat() * 0.01,
      };
    });
  }

}
