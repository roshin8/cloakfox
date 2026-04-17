/**
 * SpeechSynthesis Spoofer
 *
 * The voices available for speech synthesis are highly unique
 * and can be used for fingerprinting.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

// Common voices that appear on most systems
const COMMON_VOICES = [
  { name: 'Google US English', lang: 'en-US', localService: false },
  { name: 'Google UK English Female', lang: 'en-GB', localService: false },
  { name: 'Google UK English Male', lang: 'en-GB', localService: false },
  { name: 'Microsoft David - English (United States)', lang: 'en-US', localService: true },
  { name: 'Microsoft Zira - English (United States)', lang: 'en-US', localService: true },
];

/**
 * Create a fake SpeechSynthesisVoice object
 */
function createFakeVoice(
  name: string,
  lang: string,
  localService: boolean,
  isDefault: boolean
): SpeechSynthesisVoice {
  return {
    name,
    lang,
    localService,
    default: isDefault,
    voiceURI: name,
  };
}

/**
 * Initialize SpeechSynthesis spoofing
 */
export function initSpeechSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  if (!('speechSynthesis' in window)) return;

  const originalGetVoices = speechSynthesis.getVoices;

  if (mode === 'block') {
    // Return empty voice list
    speechSynthesis.getVoices = function (): SpeechSynthesisVoice[] {
      logAccess('speechSynthesis.getVoices', { blocked: true, value: '0 voices' });
      return [];
    };
  } else {
    // Return a common subset of voices
    const numVoices = prng.nextInt(2, 5);
    const selectedVoices = COMMON_VOICES.slice(0, numVoices);

    const fakeVoices = selectedVoices.map((v, i) =>
      createFakeVoice(v.name, v.lang, v.localService, i === 0)
    );

    speechSynthesis.getVoices = function (): SpeechSynthesisVoice[] {
      logAccess('speechSynthesis.getVoices', { spoofed: true, value: `${fakeVoices.length} voices` });
      return fakeVoices;
    };
  }

  // Also handle the voiceschanged event
  const originalAddEventListener = speechSynthesis.addEventListener;
  speechSynthesis.addEventListener = function (
    type: string,
    listener: EventListenerOrEventListenerObject,
    options?: boolean | AddEventListenerOptions
  ) {
    if (type === 'voiceschanged') {
      // Fire immediately with our fake voices
      setTimeout(() => {
        if (typeof listener === 'function') {
          listener(new Event('voiceschanged'));
        } else {
          listener.handleEvent(new Event('voiceschanged'));
        }
      }, 0);
      return;
    }
    return originalAddEventListener.call(this, type, listener, options);
  };

}
