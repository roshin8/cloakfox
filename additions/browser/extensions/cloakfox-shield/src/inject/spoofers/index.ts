/**
 * Spoofer Registry - Orchestrates all fingerprint spoofers
 */

import type { InjectConfig } from '@/types';
import { PRNG, base64ToUint8Array } from '@/lib/crypto';
import { applyCoreProtections } from '../core-bridge';

// Graphics
import { initCanvasSpoofer } from './graphics/canvas';
import { initOffscreenCanvasSpoofer } from './canvas/offscreen';
import { initWebGLSpoofer, getSelectedGPU } from './graphics/webgl';
import { initWebGLShaderSpoofer } from './graphics/webgl-shaders';
import { initWebGPUSpoofer } from './graphics/webgpu';
import { initDOMRectSpoofer } from './graphics/domrect';
import { initTextMetricsSpoofer } from './graphics/text-metrics';
import { initSVGSpoofer } from './graphics/svg';

// Audio
import { initAudioSpoofer } from './audio/audio-context';
import { initOfflineAudioSpoofer } from './audio/offline-audio';
import { initAudioLatencySpoofer } from './audio/audio-latency';

// Hardware
import { initScreenSpoofer } from './hardware/screen';
import { initScreenFrameSpoofer } from './hardware/screen-frame';
import { initScreenExtendedSpoofer } from './hardware/screen-extended';
import { initScreenOrientationSpoofer } from './hardware/screen-orientation';
import { initDeviceSpoofer } from './hardware/device';
import { initBatterySpoofer } from './hardware/battery';
import { initMediaDevicesSpoofer } from './hardware/media-devices';
import { initTouchSpoofer } from './hardware/touch';
import { initSensorSpoofer } from './hardware/sensors';
import { initArchitectureSpoofer } from './hardware/architecture';
import { initVisualViewportSpoofer } from './hardware/visual-viewport';

// Navigator
import { initNavigatorSpoofer } from './navigator/user-agent';
import { initClipboardSpoofer } from './navigator/clipboard';
import { initVibrationSpoofer } from './navigator/vibration';
import { initVendorFlavorSpoofer } from './navigator/vendor-flavors';
import { initFontPreferencesSpoofer } from './navigator/font-preferences';
import { initWindowNameSpoofer } from './navigator/window-name';
import { initTabHistorySpoofer } from './navigator/tab-history';
import { initMediaCapabilitiesSpoofer } from './navigator/media-capabilities';

// Timezone
import { initTimezoneSpoofer } from './timezone/intl';

// Fonts
import { initFontSpoofer } from './fonts/font-enum';
import { initCSSFontSpoofer } from './fonts/css-fonts';

// Network
import { initWebRTCSpoofer } from './network/webrtc';
import { initNetworkSpoofer } from './network/connection';
import { initGeolocationSpoofer } from './network/geolocation';
import { initWebSocketSpoofer } from './network/websocket';

// Keyboard (import cadence)
import { initKeyboardCadenceSpoofer } from './keyboard/cadence';

// Timing
import { initPerformanceSpoofer } from './timing/performance';
import { initMemorySpoofer } from './timing/memory';
import { initEventLoopJitter } from './timing/event-loop';

// CSS
import { initCSSSpoofer } from './css/media-queries';

// Speech
import { initSpeechSpoofer } from './speech/synthesis';

// Permissions
import { initPermissionsSpoofer } from './permissions/permissions';
import { initNotificationSpoofer } from './permissions/notification';

// Storage
import { initStorageSpoofer } from './storage/storage-estimate';
import { initIndexedDBSpoofer } from './storage/indexeddb';
import { initWebSQLSpoofer } from './storage/websql';
import { initPrivateModeProtection } from './storage/private-mode';

// Codecs
import { initCodecSpoofer } from './codecs/codecs';

// Math
import { initMathSpoofer } from './math/math';

// Keyboard
import { initKeyboardSpoofer } from './keyboard/keyboard';

// Workers
import { initWorkerSpoofer } from './workers/worker-fingerprint';

// Errors
import { initErrorSpoofer } from './errors/stack-trace';

// Rendering
import { initEmojiSpoofer } from './rendering/emoji';
import { initMathMLSpoofer } from './rendering/mathml';

// Intl
import { initIntlSpoofer } from './intl/intl-apis';

// Crypto
import { initCryptoSpoofer } from './crypto/webcrypto';

// Devices
import { initGamepadSpoofer } from './devices/gamepad';
import { initMIDISpoofer } from './devices/midi';
import { initBluetoothSpoofer } from './devices/bluetooth';
import { initUSBSpoofer, initSerialSpoofer, initHIDSpoofer } from './devices/usb-serial';

// Features
import { initFeatureSpoofer } from './features/feature-detection';

// Payment
import { initApplePaySpoofer } from './payment/apple-pay';

// Iframe
import { initIframePatcher } from './iframe/iframe-patcher';

// Monitor
import { initFingerprintMonitor, reportToBackground, markSpoofersInitialized } from '../monitor/fingerprint-monitor';

let pagePRNG: PRNG | null = null;

export function getPagePRNG(): PRNG | null {
  return pagePRNG;
}

/**
 * Initialize all spoofers based on configuration
 */
export function initializeSpoofers(config: InjectConfig): void {
  markSpoofersInitialized();

  // Create page-specific PRNG by combining container seed with domain
  const seedBytes = base64ToUint8Array(config.seed);
  const domainBytes = new TextEncoder().encode(config.domain);
  const combined = new Uint8Array(seedBytes.length + domainBytes.length);
  combined.set(seedBytes);
  combined.set(domainBytes, seedBytes.length);

  // XOR-fold into 32 bytes
  const hashedSeed = new Uint8Array(32);
  for (let i = 0; i < combined.length; i++) {
    hashedSeed[i % 32] ^= combined[i];
  }

  pagePRNG = new PRNG(hashedSeed);

  const { settings, assignedProfile } = config;

  // Try C++ Core protections first (unless user disabled Core engine)
  let coreHandled = new Set<string>();
  if (config.useCoreEngine !== false) {
    coreHandled = applyCoreProtections(
      hashedSeed,
      assignedProfile,
      settings as unknown as Record<string, Record<string, string>>
    );
    if (coreHandled.size > 0) {
      console.log(`[Cloakfox] Core engine handled ${coreHandled.size} signals:`, [...coreHandled].join(', '));
    }
  } else {
    console.log('[Cloakfox] Core engine disabled — using JS spoofing for all signals');
  }

  // Skip JS spoofer if Core already handled the signal
  const skip = (key: string) => coreHandled.has(key);

  // Wrap each spoofer init so one failure doesn't crash all others
  const safe = (name: string, fn: () => void) => {
    try { fn(); } catch (e) {
      console.warn(`[Cloakfox] Spoofer "${name}" failed to initialize:`, e);
    }
  };

  // Graphics (skip canvas/webgl if Core handled them)
  safe('canvas', () => { if (settings.graphics.canvas !== 'off' && !skip('graphics.canvas')) initCanvasSpoofer(settings.graphics.canvas, pagePRNG); });
  let selectedGPURef: { vendor: string; renderer: string } | null = null;
  safe('webgl', () => {
    if ((settings.graphics.webgl !== 'off' || settings.graphics.webgl2 !== 'off') && !skip('graphics.webgl')) {
      initWebGLSpoofer(settings.graphics.webgl, settings.graphics.webgl2, pagePRNG, assignedProfile);
      selectedGPURef = getSelectedGPU();
    }
  });
  safe('offscreen', () => { if (settings.graphics.offscreenCanvas !== 'off' && !skip('graphics.offscreenCanvas')) initOffscreenCanvasSpoofer(settings.graphics.offscreenCanvas, pagePRNG); });
  safe('webglShaders', () => { if (settings.graphics.webglShaders !== 'off' && !skip('graphics.webglShaders')) initWebGLShaderSpoofer(settings.graphics.webglShaders, pagePRNG); });
  safe('webgpu', () => { if (settings.graphics.webgpu !== 'off') initWebGPUSpoofer(settings.graphics.webgpu, pagePRNG); });
  safe('domRect', () => { if (settings.graphics.domRect !== 'off') initDOMRectSpoofer(settings.graphics.domRect, pagePRNG); });
  safe('textMetrics', () => { if (settings.graphics.textMetrics !== 'off') initTextMetricsSpoofer(settings.graphics.textMetrics, pagePRNG); });
  safe('svg', () => { if (settings.graphics.svg !== 'off') initSVGSpoofer(settings.graphics.svg, pagePRNG); });

  safe('audio', () => { if (settings.audio.audioContext !== 'off' && !skip('audio.audioContext')) initAudioSpoofer(settings.audio.audioContext, pagePRNG); });
  safe('offlineAudio', () => { if (settings.audio.offlineAudio !== 'off' && !skip('audio.offlineAudio')) initOfflineAudioSpoofer(settings.audio.offlineAudio, pagePRNG); });
  safe('audioLatency', () => { if (settings.audio.latency !== 'off' && !skip('audio.latency')) initAudioLatencySpoofer(settings.audio.latency, pagePRNG); });
  safe('codecs', () => { if (settings.audio.codecs !== 'off') initCodecSpoofer(settings.audio.codecs, pagePRNG); });

  safe('screen', () => { if (settings.hardware.screen !== 'off' && !skip('hardware.screen')) initScreenSpoofer(settings.hardware.screen, pagePRNG, assignedProfile?.screen); });
  safe('screenFrame', () => { if (settings.hardware.screenFrame !== 'off' && !skip('hardware.screenFrame')) initScreenFrameSpoofer(settings.hardware.screenFrame, pagePRNG); });
  safe('orientation', () => { if (settings.hardware.orientation !== 'off' && !skip('hardware.orientation')) initScreenOrientationSpoofer(settings.hardware.orientation, pagePRNG); });
  safe('device', () => {
    if ((settings.hardware.deviceMemory !== 'off' || settings.hardware.hardwareConcurrency !== 'off') && !skip('hardware.hardwareConcurrency')) {
      initDeviceSpoofer(settings.hardware.deviceMemory, settings.hardware.hardwareConcurrency, pagePRNG, assignedProfile);
    }
  });
  safe('battery', () => { if (settings.hardware.battery !== 'off') initBatterySpoofer(settings.hardware.battery, pagePRNG); });
  safe('mediaDevices', () => { if (settings.hardware.mediaDevices !== 'off') initMediaDevicesSpoofer(settings.hardware.mediaDevices, pagePRNG); });
  safe('touch', () => { if (settings.hardware.touch !== 'off') initTouchSpoofer(settings.hardware.touch, pagePRNG, assignedProfile); });
  safe('sensors', () => { if (settings.hardware.sensors !== 'off') initSensorSpoofer(settings.hardware.sensors, pagePRNG); });
  safe('architecture', () => { if (settings.hardware.architecture !== 'off') initArchitectureSpoofer(settings.hardware.architecture, pagePRNG); });
  safe('viewport', () => { if (settings.hardware.visualViewport !== 'off') initVisualViewportSpoofer(settings.hardware.visualViewport, pagePRNG); });
  safe('screenExt', () => { if (settings.hardware.screenExtended !== 'off' && !skip('hardware.screenExtended')) initScreenExtendedSpoofer(settings.hardware.screenExtended, pagePRNG); });

  safe('navigator', () => { if (settings.navigator.userAgent !== 'off' && !skip('navigator.userAgent')) initNavigatorSpoofer(settings.navigator, pagePRNG, config.profile, assignedProfile); });
  safe('clipboard', () => { if (settings.navigator.clipboard !== 'off' && !skip('navigator.clipboard')) initClipboardSpoofer(settings.navigator.clipboard, pagePRNG); });
  safe('vibration', () => { if (settings.navigator.vibration !== 'off' && !skip('navigator.vibration')) initVibrationSpoofer(settings.navigator.vibration, pagePRNG); });
  safe('vendorFlavors', () => { if (settings.navigator.vendorFlavors !== 'off') initVendorFlavorSpoofer(settings.navigator.vendorFlavors, pagePRNG); });
  safe('fontPrefs', () => { if (settings.navigator.fontPreferences !== 'off') initFontPreferencesSpoofer(settings.navigator.fontPreferences, pagePRNG); });
  safe('windowName', () => { if (settings.navigator.windowName !== 'off') initWindowNameSpoofer(settings.navigator.windowName, pagePRNG); });
  safe('tabHistory', () => { if (settings.navigator.tabHistory !== 'off' && !skip('navigator.tabHistory')) initTabHistorySpoofer(settings.navigator.tabHistory, pagePRNG); });
  safe('mediaCapabilities', () => { if (settings.navigator.mediaCapabilities !== 'off') initMediaCapabilitiesSpoofer(settings.navigator.mediaCapabilities, pagePRNG); });

  safe('timezone', () => {
    if ((settings.timezone.intl !== 'off' || settings.timezone.date !== 'off') && !skip('timezone.intl')) {
      initTimezoneSpoofer(settings.timezone, pagePRNG, assignedProfile);
    }
  });

  safe('fonts', () => { if (settings.fonts.enumeration !== 'off') initFontSpoofer(settings.fonts.enumeration, pagePRNG, assignedProfile); });
  safe('cssFonts', () => { if (settings.fonts.cssDetection !== 'off' && !skip('fonts.cssDetection')) initCSSFontSpoofer(settings.fonts.cssDetection, pagePRNG); });

  safe('webrtc', () => { if (settings.network.webrtc !== 'off' && !skip('network.webrtc')) initWebRTCSpoofer(settings.network.webrtc, pagePRNG); });
  safe('connection', () => { if (settings.network.connection !== 'off') initNetworkSpoofer(settings.network.connection, pagePRNG); });
  safe('geolocation', () => { if (settings.network.geolocation !== 'off' && !skip('network.geolocation')) initGeolocationSpoofer(settings.network.geolocation, pagePRNG); });
  safe('websocket', () => { if (settings.network.websocket !== 'off') initWebSocketSpoofer(settings.network.websocket, pagePRNG); });

  safe('performance', () => { if (settings.timing.performance !== 'off') initPerformanceSpoofer(settings.timing.performance, pagePRNG); });
  safe('memory', () => { if (settings.timing.memory !== 'off') initMemorySpoofer(settings.timing.memory, pagePRNG); });
  safe('eventLoop', () => { if (settings.timing.eventLoop !== 'off') initEventLoopJitter(settings.timing.eventLoop, pagePRNG); });

  safe('css', () => { if (settings.css.mediaQueries !== 'off') initCSSSpoofer(settings.css.mediaQueries, pagePRNG, assignedProfile); });
  safe('speech', () => { if (settings.speech.synthesis !== 'off' && !skip('speech.synthesis')) initSpeechSpoofer(settings.speech.synthesis, pagePRNG); });
  safe('permissions', () => { if (settings.permissions.query !== 'off') initPermissionsSpoofer(settings.permissions.query, pagePRNG); });
  safe('notification', () => { if (settings.permissions.notification !== 'off') initNotificationSpoofer(settings.permissions.notification, pagePRNG); });
  safe('storage', () => { if (settings.storage.estimate !== 'off') initStorageSpoofer(settings.storage.estimate, pagePRNG); });
  safe('indexedDB', () => { if (settings.storage.indexedDB !== 'off') initIndexedDBSpoofer(settings.storage.indexedDB, pagePRNG); });
  safe('webSQL', () => { if (settings.storage.webSQL !== 'off') initWebSQLSpoofer(settings.storage.webSQL, pagePRNG); });
  safe('privateMode', () => { if (settings.storage.privateModeProtection !== 'off') initPrivateModeProtection(settings.storage.privateModeProtection, pagePRNG); });
  safe('math', () => { if (settings.math.functions !== 'off') initMathSpoofer(settings.math.functions, pagePRNG); });
  safe('keyboard', () => { if (settings.keyboard.layout !== 'off') initKeyboardSpoofer(settings.keyboard.layout, pagePRNG); });
  safe('cadence', () => { if (settings.keyboard.cadence !== 'off') initKeyboardCadenceSpoofer(settings.keyboard.cadence, pagePRNG); });
  safe('workers', () => { if (settings.workers.fingerprint !== 'off') initWorkerSpoofer(settings.workers.fingerprint, pagePRNG, assignedProfile, settings.workers.serviceWorker); });
  safe('errors', () => { if (settings.errors.stackTrace !== 'off') initErrorSpoofer(settings.errors.stackTrace, pagePRNG); });
  safe('emoji', () => { if (settings.rendering.emoji !== 'off') initEmojiSpoofer(settings.rendering.emoji, pagePRNG); });
  safe('mathml', () => { if (settings.rendering.mathml !== 'off') initMathMLSpoofer(settings.rendering.mathml, pagePRNG); });
  safe('intl', () => { if (settings.intl.apis !== 'off') initIntlSpoofer(settings.intl.apis, pagePRNG, assignedProfile); });
  safe('crypto', () => { if (settings.crypto.webCrypto !== 'off') initCryptoSpoofer(settings.crypto.webCrypto, pagePRNG); });

  // Devices
  safe('gamepad', () => { if (settings.devices.gamepad !== 'off') initGamepadSpoofer(settings.devices.gamepad, pagePRNG); });
  safe('midi', () => { if (settings.devices.midi !== 'off') initMIDISpoofer(settings.devices.midi, pagePRNG); });
  safe('bluetooth', () => { if (settings.devices.bluetooth !== 'off') initBluetoothSpoofer(settings.devices.bluetooth, pagePRNG); });
  safe('usb', () => { if (settings.devices.usb !== 'off') initUSBSpoofer(settings.devices.usb, pagePRNG); });
  safe('serial', () => { if (settings.devices.serial !== 'off') initSerialSpoofer(settings.devices.serial, pagePRNG); });
  safe('hid', () => { if (settings.devices.hid !== 'off') initHIDSpoofer(settings.devices.hid, pagePRNG); });

  // Features
  safe('features', () => { if (settings.features.detection !== 'off') initFeatureSpoofer(settings.features.detection, pagePRNG); });

  // Payment
  safe('applePay', () => { if (settings.payment.applePay !== 'off') initApplePaySpoofer(settings.payment.applePay, pagePRNG); });

  // Intercept iframe creation to apply overrides to iframe contexts.
  initIframePatcher({ settings, assignedProfile, selectedGPU: selectedGPURef });

  // Initialize monitor and send initial report
  initFingerprintMonitor();
  setTimeout(reportToBackground, 50);
}
