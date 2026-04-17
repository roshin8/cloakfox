/**
 * OfflineAudioContext Spoofer
 *
 * OfflineAudioContext is commonly used for audio fingerprinting
 * by rendering audio and analyzing the output.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize OfflineAudioContext spoofing
 */
export function initOfflineAudioSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  if (typeof OfflineAudioContext === 'undefined') return;

  const OriginalOfflineAudioContext = OfflineAudioContext;

  // @ts-ignore - Replacing constructor
  window.OfflineAudioContext = function (
    numberOfChannels: number,
    length: number,
    sampleRate: number
  ): OfflineAudioContext {
    logAccess('OfflineAudioContext.constructor', { spoofed: true });

    const context = new OriginalOfflineAudioContext(numberOfChannels, length, sampleRate);

    if (mode === 'block') {
      // Override startRendering to return silence
      const originalStartRendering = context.startRendering.bind(context);

      context.startRendering = async function (): Promise<AudioBuffer> {
        logAccess('OfflineAudioContext.startRendering', { blocked: true });

        // Create silent buffer
        const silentBuffer = new OriginalOfflineAudioContext(
          numberOfChannels,
          length,
          sampleRate
        );
        return silentBuffer.startRendering();
      };

      return context;
    }

    // Noise mode - add subtle noise to rendered audio
    const originalStartRendering = context.startRendering.bind(context);

    context.startRendering = async function (): Promise<AudioBuffer> {
      logAccess('OfflineAudioContext.startRendering', { spoofed: true });

      const buffer = await originalStartRendering();

      // Add noise to each channel
      for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
        const data = buffer.getChannelData(channel);
        for (let i = 0; i < data.length; i++) {
          // Add very small noise that doesn't affect audio quality
          data[i] += (prng.nextFloat() - 0.5) * 0.0001;
        }
      }

      return buffer;
    };

    return context;
  };

  // Copy static properties
  (window.OfflineAudioContext as any).prototype = OriginalOfflineAudioContext.prototype;

}
