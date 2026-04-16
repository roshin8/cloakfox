/**
 * Maps signal category.key to protection type.
 *
 * "core" = Handled at browser engine level via C++ patches (window.setXxx())
 * "js"   = Handled by extension JS spoofers
 *
 * Signals with "core" have both Core and JS implementations.
 * User can choose which to use. Default is Core when available.
 */

export type SignalType = 'core' | 'js';

/** Signals that have C++ Core implementation via window.setXxx() WebIDL methods */
export const CORE_SIGNALS: Record<string, SignalType> = {
  // Graphics
  'graphics.canvas': 'core',         // setCanvasSeed
  'graphics.webgl': 'core',          // setWebGLVendor + setWebGLRenderer

  // Audio
  'audio.audioContext': 'core',       // setAudioFingerprintSeed

  // Hardware
  'hardware.screen': 'core',          // setScreenDimensions + setScreenColorDepth
  'hardware.hardwareConcurrency': 'core', // setNavigatorHardwareConcurrency
  'hardware.battery': 'core',         // setBatteryStatus
  'hardware.mediaDevices': 'core',    // setMediaDeviceCounts

  // Navigator
  'navigator.userAgent': 'core',      // setNavigatorUserAgent + setNavigatorPlatform + setNavigatorOscpu

  // Fonts
  'fonts.enumeration': 'core',        // setFontList
  'fonts.cssDetection': 'core',       // setFontSpacingSeed

  // Network
  'network.webrtc': 'core',           // setWebRTCIPv4 + setWebRTCIPv6

  // Timezone
  'timezone.intl': 'core',            // setTimezone
  'timezone.date': 'core',            // setTimezone

  // Speech
  'speech.synthesis': 'core',         // setSpeechVoices
};

/** Get the protection type for a signal */
export function getSignalType(cat: string, key: string): SignalType {
  return CORE_SIGNALS[`${cat}.${key}`] || 'js';
}

/** Check if a signal has Core (C++) implementation */
export function hasCore(cat: string, key: string): boolean {
  return `${cat}.${key}` in CORE_SIGNALS;
}

/** Count signals by type */
export function countByType(
  spoofers: Record<string, Record<string, string>>
): { core: number; js: number; off: number } {
  let core = 0, js = 0, off = 0;
  for (const [cat, signals] of Object.entries(spoofers)) {
    for (const [key, mode] of Object.entries(signals)) {
      if (mode === 'off') { off++; continue; }
      if (hasCore(cat, key)) core++;
      else js++;
    }
  }
  return { core, js, off };
}
