/**
 * MediaCapabilities Spoofer
 *
 * navigator.mediaCapabilities.decodingInfo/encodingInfo reveals codec
 * support which fingerprints the device (different OS/hardware = different codecs).
 * Override to return platform-consistent capabilities.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

export function initMediaCapabilitiesSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;
  if (!('mediaCapabilities' in navigator)) return;

  const mc = navigator.mediaCapabilities;

  // Override decodingInfo to normalize results
  if (mc.decodingInfo) {
    const origDecoding = mc.decodingInfo.bind(mc);
    mc.decodingInfo = async function(config: MediaDecodingConfiguration): Promise<MediaCapabilitiesDecodingInfo> {
      logAccess('navigator.mediaCapabilities.decodingInfo', { spoofed: true });

      if (mode === 'block') {
        return {
          supported: false,
          smooth: false,
          powerEfficient: false,
        } as MediaCapabilitiesDecodingInfo;
      }

      const result = await origDecoding(config);
      // Normalize: always report supported codecs as smooth and power-efficient
      // to prevent fingerprinting based on hardware acceleration differences
      return {
        supported: result.supported,
        smooth: result.supported,
        powerEfficient: result.supported,
      } as MediaCapabilitiesDecodingInfo;
    };
  }

  // Override encodingInfo similarly
  if (mc.encodingInfo) {
    const origEncoding = mc.encodingInfo.bind(mc);
    mc.encodingInfo = async function(config: MediaEncodingConfiguration): Promise<MediaCapabilitiesEncodingInfo> {
      logAccess('navigator.mediaCapabilities.encodingInfo', { spoofed: true });

      if (mode === 'block') {
        return {
          supported: false,
          smooth: false,
          powerEfficient: false,
        } as MediaCapabilitiesEncodingInfo;
      }

      const result = await origEncoding(config);
      return {
        supported: result.supported,
        smooth: result.supported,
        powerEfficient: result.supported,
      } as MediaCapabilitiesEncodingInfo;
    };
  }
}
