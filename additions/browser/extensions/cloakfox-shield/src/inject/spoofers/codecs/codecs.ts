/**
 * Codec Support Spoofer
 *
 * The canPlayType() and MediaSource.isTypeSupported() APIs reveal
 * which audio/video codecs are supported, creating a fingerprint.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

// Common codec support (what a typical Chrome browser would return)
const CODEC_SUPPORT: Record<string, 'probably' | 'maybe' | ''> = {
  // Video
  'video/mp4': 'probably',
  'video/mp4; codecs="avc1.42E01E"': 'probably',
  'video/mp4; codecs="avc1.42E01E, mp4a.40.2"': 'probably',
  'video/mp4; codecs="avc1.4D401E"': 'probably',
  'video/mp4; codecs="avc1.64001E"': 'probably',
  'video/mp4; codecs="mp4a.40.2"': 'probably',
  'video/mp4; codecs="hev1"': 'probably',
  'video/mp4; codecs="hvc1"': 'probably',
  'video/webm': 'probably',
  'video/webm; codecs="vp8"': 'probably',
  'video/webm; codecs="vp8, vorbis"': 'probably',
  'video/webm; codecs="vp9"': 'probably',
  'video/webm; codecs="vp09.00.10.08"': 'probably',
  'video/ogg': 'probably',
  'video/ogg; codecs="theora"': 'probably',

  // Audio
  'audio/mp4': 'probably',
  'audio/mp4; codecs="mp4a.40.2"': 'probably',
  'audio/mpeg': 'probably',
  'audio/mp3': 'probably',
  'audio/ogg': 'probably',
  'audio/ogg; codecs="vorbis"': 'probably',
  'audio/ogg; codecs="opus"': 'probably',
  'audio/webm': 'probably',
  'audio/webm; codecs="opus"': 'probably',
  'audio/webm; codecs="vorbis"': 'probably',
  'audio/wav': 'probably',
  'audio/wave': 'probably',
  'audio/x-wav': 'probably',
  'audio/flac': 'probably',
  'audio/x-flac': 'probably',

  // Not supported in most browsers
  'video/x-matroska': '',
  'audio/x-matroska': '',
};

/**
 * Initialize codec spoofing
 */
export function initCodecSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Spoof HTMLMediaElement.canPlayType
  overrideMethod(HTMLMediaElement.prototype, 'canPlayType', (original, thisArg, args) => {
    const type = args[0] as string;
    logAccess('HTMLMediaElement.canPlayType', { spoofed: true, value: 'normalized' });

    if (mode === 'block') {
      return '';
    }

    const normalizedType = type.toLowerCase().trim();

    if (normalizedType in CODEC_SUPPORT) {
      return CODEC_SUPPORT[normalizedType];
    }

    const baseType = normalizedType.split(';')[0].trim();
    if (baseType in CODEC_SUPPORT) {
      return 'maybe';
    }

    return original.call(thisArg, type);
  });

  // Spoof MediaSource.isTypeSupported
  if (typeof MediaSource !== 'undefined' && 'isTypeSupported' in MediaSource) {
    overrideMethod(MediaSource as any, 'isTypeSupported', (original, _thisArg, args) => {
      const type = args[0] as string;
      logAccess('MediaSource.isTypeSupported', { spoofed: true, value: 'normalized' });

      if (mode === 'block') {
        return false;
      }

      const normalizedType = type.toLowerCase().trim();

      if (normalizedType in CODEC_SUPPORT) {
        return CODEC_SUPPORT[normalizedType] === 'probably';
      }

      return original.call(MediaSource, type);
    });
  }

  // Spoof RTCRtpSender.getCapabilities (WebRTC codecs)
  if (typeof RTCRtpSender !== 'undefined' && 'getCapabilities' in RTCRtpSender) {
    overrideMethod(RTCRtpSender as any, 'getCapabilities', (original, _thisArg, args) => {
      logAccess('RTCRtpSender.getCapabilities', { spoofed: true, value: 'normalized' });

      if (mode === 'block') {
        return null;
      }

      return original.call(RTCRtpSender, ...args);
    });
  }

}
