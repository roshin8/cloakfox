/**
 * Fingerprint Access Monitor
 *
 * Tracks which fingerprinting APIs are being accessed by websites.
 * Sends reports back to the background script for display in the popup.
 */

import { overrideMethod, overrideGetter } from '@/lib/stealth';
import {
  PAGE_MSG_FINGERPRINT_REPORT,
  PAGE_MSG_GET_REPORT,
  PAGE_MSG_GET_RECOMMENDATIONS,
  PAGE_MSG_RECOMMENDATIONS,
  FINGERPRINT_REPORT_INTERVAL_MS,
  FINGERPRINT_MAX_LOG_SIZE,
  FINGERPRINT_STACK_TRACE_LINES,
} from '@/constants';
import { CATEGORY_TO_SETTING } from '@/constants/categories';

// Re-export for consumers that imported from here
export { CATEGORY_TO_SETTING };

export interface FingerprintAccess {
  api: string;
  category: string;
  timestamp: number;
  blocked: boolean;
  spoofed: boolean;
  stackTrace?: string;
  value?: string;
}

const accessLog: FingerprintAccess[] = [];

// Categories for fingerprinting APIs
export const API_CATEGORIES: Record<string, string> = {
  // Canvas
  'HTMLCanvasElement.toDataURL': 'Canvas',
  'HTMLCanvasElement.toBlob': 'Canvas',
  'CanvasRenderingContext2D.getImageData': 'Canvas',
  'OffscreenCanvas.convertToBlob': 'OffscreenCanvas',
  'OffscreenCanvas.getContext': 'OffscreenCanvas',

  // WebGL
  'WebGLRenderingContext.getParameter': 'WebGL',
  'WebGL2RenderingContext.getParameter': 'WebGL',
  'WebGLRenderingContext.getExtension': 'WebGL',
  'WebGLRenderingContext.getSupportedExtensions': 'WebGL',
  'WEBGL_debug_renderer_info': 'WebGL',
  'WebGLRenderingContext.getShaderPrecisionFormat': 'WebGL Shaders',
  'WebGL2RenderingContext.getShaderPrecisionFormat': 'WebGL Shaders',

  // WebGPU
  'navigator.gpu.requestAdapter': 'WebGPU',
  'GPUAdapter.requestAdapterInfo': 'WebGPU',

  // Audio
  'AudioContext.createAnalyser': 'Audio',
  'AudioContext.createOscillator': 'Audio',
  'AnalyserNode.getFloatFrequencyData': 'Audio',
  'AudioContext.baseLatency': 'Audio Latency',
  'AudioContext.outputLatency': 'Audio Latency',
  'OfflineAudioContext.startRendering': 'Offline Audio',
  'OfflineAudioContext': 'Offline Audio',

  // Screen/Display
  'screen.width': 'Screen',
  'screen.height': 'Screen',
  'screen.colorDepth': 'Screen',
  'window.devicePixelRatio': 'Screen',
  'window.innerWidth': 'Screen',
  'window.innerHeight': 'Screen',
  'window.screenX': 'Screen Frame',
  'window.screenY': 'Screen Frame',
  'window.screenLeft': 'Screen Frame',
  'window.screenTop': 'Screen Frame',
  'window.outerWidth': 'Screen Frame',
  'window.outerHeight': 'Screen Frame',
  'screen.orientation': 'Screen Orientation',
  'screen.orientation.type': 'Screen Orientation',
  'screen.orientation.angle': 'Screen Orientation',

  // Navigator
  'navigator.userAgent': 'Navigator',
  'navigator.platform': 'Navigator',
  'navigator.languages': 'Navigator',
  'navigator.hardwareConcurrency': 'Hardware',
  'navigator.deviceMemory': 'Hardware',
  'navigator.plugins': 'Navigator',
  'navigator.mimeTypes': 'Navigator',
  'navigator.userAgentData': 'Client Hints',
  'navigator.userAgentData.getHighEntropyValues': 'Client Hints',
  'navigator.maxTouchPoints': 'Touch',
  'navigator.webdriver': 'Features',
  'navigator.doNotTrack': 'Features',
  'navigator.globalPrivacyControl': 'Features',
  'navigator.cookieEnabled': 'Features',
  'navigator.onLine': 'Features',
  'navigator.javaEnabled': 'Features',
  'navigator.pdfViewerEnabled': 'Features',

  // Timing
  'performance.now': 'Timing',
  'Date.getTimezoneOffset': 'Timezone',

  // DOMRect
  'Element.getBoundingClientRect': 'DOMRect',
  'Element.getClientRects': 'DOMRect',
  'Range.getBoundingClientRect': 'DOMRect',

  // Fonts
  'FontFace': 'Fonts',
  'document.fonts': 'Fonts',
  'CSS font detection': 'CSS Fonts',

  // Media
  'navigator.mediaDevices.enumerateDevices': 'Media Devices',
  'MediaDevices.enumerateDevices': 'Media Devices',
  'HTMLMediaElement.canPlayType': 'Codecs',
  'MediaSource.isTypeSupported': 'Codecs',

  // Speech
  'speechSynthesis.getVoices': 'Speech',

  // Storage
  'navigator.storage.estimate': 'Storage',
  'StorageManager.estimate': 'Storage',
  'IDBFactory.databases': 'IndexedDB',
  'indexedDB.databases': 'IndexedDB',
  'openDatabase': 'WebSQL',

  // Permissions
  'navigator.permissions.query': 'Permissions',
  'Permissions.query': 'Permissions',
  'Notification.permission': 'Notification',
  'Notification.requestPermission': 'Notification',
  'Notification.maxActions': 'Notification',

  // Clipboard
  'navigator.clipboard': 'Clipboard',
  'navigator.clipboard.readText': 'Clipboard',
  'navigator.clipboard.read': 'Clipboard',
  'navigator.clipboard.writeText': 'Clipboard',
  'navigator.clipboard.write': 'Clipboard',

  // Vibration
  'navigator.vibrate': 'Vibration',

  // Sensors
  'Accelerometer': 'Sensors',
  'Accelerometer.constructor': 'Sensors',
  'Accelerometer.start': 'Sensors',
  'LinearAccelerationSensor': 'Sensors',
  'GravitySensor': 'Sensors',
  'Gyroscope': 'Sensors',
  'Magnetometer': 'Sensors',
  'AbsoluteOrientationSensor': 'Sensors',
  'RelativeOrientationSensor': 'Sensors',
  'AmbientLightSensor': 'Sensors',
  'DeviceMotionEvent': 'Sensors',
  'DeviceOrientationEvent': 'Sensors',

  // Payment
  'ApplePaySession.canMakePayments': 'Apple Pay',
  'ApplePaySession.canMakePaymentsWithActiveCard': 'Apple Pay',
  'ApplePaySession.supportsVersion': 'Apple Pay',
  'PaymentRequest': 'Apple Pay',

  // Network
  'navigator.connection': 'Network',
  'NetworkInformation': 'Network',
  'RTCPeerConnection': 'WebRTC',

  // Battery
  'navigator.getBattery': 'Battery',

  // Intl
  'Intl.DateTimeFormat': 'Timezone',
  'Intl.DateTimeFormat.resolvedOptions': 'Timezone',
  'Intl.ListFormat': 'Intl',
  'Intl.RelativeTimeFormat': 'Intl',
  'Intl.PluralRules': 'Intl',
  'Intl.Segmenter': 'Intl',
  'Intl.DisplayNames': 'Intl',
  'Intl.supportedValuesOf': 'Intl',

  // Math
  'Math.tan': 'Math',
  'Math.sin': 'Math',
  'Math.cos': 'Math',
  'Math.exp': 'Math',
  'Math.log': 'Math',
  'Math.acos': 'Math',

  // CSS
  'matchMedia': 'CSS',
  'getComputedStyle': 'CSS',
  'CSS.supports': 'Features',
  'document.implementation.hasFeature': 'Features',

  // Keyboard
  'navigator.keyboard.getLayoutMap': 'Keyboard',

  // Touch
  'TouchEvent': 'Touch',

  // Workers
  'Worker': 'Workers',
  'SharedWorker': 'Workers',

  // Errors
  'Error.stack': 'Errors',

  // Rendering
  'emoji rendering': 'Emoji',
  'MathML rendering': 'MathML',

  // Crypto
  'crypto.subtle.digest': 'Crypto',
  'crypto.getRandomValues': 'Crypto',

  // Devices
  'navigator.getGamepads': 'Gamepad',
  'Gamepad': 'Gamepad',
  'navigator.requestMIDIAccess': 'MIDI',
  'MIDIAccess': 'MIDI',
  'navigator.bluetooth': 'Bluetooth',
  'navigator.bluetooth.getAvailability': 'Bluetooth',
  'navigator.bluetooth.requestDevice': 'Bluetooth',
  'navigator.bluetooth.getDevices': 'Bluetooth',
  'navigator.usb': 'USB',
  'navigator.usb.getDevices': 'USB',
  'navigator.usb.requestDevice': 'USB',
  'navigator.serial': 'Serial',
  'navigator.serial.getPorts': 'Serial',
  'navigator.serial.requestPort': 'Serial',
  'navigator.hid': 'HID',
  'navigator.hid.getDevices': 'HID',
  'navigator.hid.requestDevice': 'HID',
};

/**
 * Log a fingerprint API access
 */
export function logAccess(
  api: string,
  options: { blocked?: boolean; spoofed?: boolean; captureStack?: boolean; value?: string } = {}
): void {
  const { blocked = false, spoofed = true, captureStack = false, value } = options;

  const access: FingerprintAccess = {
    api,
    category: API_CATEGORIES[api] || 'Unknown',
    timestamp: Date.now(),
    blocked,
    spoofed,
  };

  if (value) {
    access.value = value.length > 40 ? value.substring(0, 40) : value;
  }

  if (captureStack) {
    try {
      const stack = new Error().stack;
      if (stack) {
        access.stackTrace = stack
          .split('\n')
          .slice(2, 2 + FINGERPRINT_STACK_TRACE_LINES)
          .join('\n');
      }
    } catch {
      // Stack trace not available
    }
  }

  accessLog.push(access);

  if (accessLog.length > FINGERPRINT_MAX_LOG_SIZE) {
    accessLog.shift();
  }
}

export function getAccessLog(): FingerprintAccess[] {
  return [...accessLog];
}

export function getAccessSummary(): Record<string, { count: number; blocked: number; spoofed: number }> {
  const summary: Record<string, { count: number; blocked: number; spoofed: number }> = {};
  for (const access of accessLog) {
    if (!summary[access.category]) {
      summary[access.category] = { count: 0, blocked: 0, spoofed: 0 };
    }
    summary[access.category].count++;
    if (access.blocked) summary[access.category].blocked++;
    if (access.spoofed) summary[access.category].spoofed++;
  }
  return summary;
}

export function clearAccessLog(): void {
  accessLog.length = 0;
}

/**
 * Update spoofed/blocked status for entries matching specific APIs.
 * Called when spoofers initialize to correct early monitoring entries.
 */
function updateApiStatus(
  apiNames: string[],
  status: { spoofed?: boolean; blocked?: boolean }
): void {
  for (const access of accessLog) {
    if (apiNames.includes(access.api)) {
      if (status.spoofed !== undefined) access.spoofed = status.spoofed;
      if (status.blocked !== undefined) access.blocked = status.blocked;
    }
  }
}

/**
 * Send access report to background script via content script bridge
 */
export function reportToBackground(): void {
  window.postMessage({
    type: PAGE_MSG_FINGERPRINT_REPORT,
    summary: getAccessSummary(),
    detail: getAccessLog(),
    url: window.location.href,
  }, '*');
}

// Auto-report periodically when new accesses are logged
let lastReportedCount = 0;

setInterval(() => {
  if (accessLog.length > lastReportedCount) {
    reportToBackground();
    lastReportedCount = accessLog.length;
  }
}, FINGERPRINT_REPORT_INTERVAL_MS);

window.addEventListener('beforeunload', () => reportToBackground());

/**
 * Get recommendations for spoofers that should be enabled
 */
export function getRecommendations(
  settings: Record<string, Record<string, string>>
): { api: string; category: string; setting: string }[] {
  const recommendations: { api: string; category: string; setting: string }[] = [];
  const seenCategories = new Set<string>();

  for (const access of accessLog) {
    if (seenCategories.has(access.category)) continue;

    const settingInfo = CATEGORY_TO_SETTING[access.category];
    if (!settingInfo) continue;

    const { category, setting } = settingInfo;
    const spooferSettings = settings[category];
    if (spooferSettings && spooferSettings[setting] === 'off') {
      recommendations.push({ api: access.api, category: access.category, setting: `${category}.${setting}` });
      seenCategories.add(access.category);
    }
  }

  return recommendations;
}

export function getAccessedCategories(): string[] {
  return [...new Set(accessLog.map(a => a.category))];
}

/**
 * Install passive monitoring wrappers for key fingerprinting APIs.
 * These only log accesses without modifying behavior.
 * Replaced by full spoofers when config arrives.
 */
function installEarlyMonitoringWrappers(): void {
  // Use stealth overrides so monitoring wrappers are also undetectable
  overrideMethod(HTMLCanvasElement.prototype, 'toDataURL', (orig, thisArg, args) => {
    if (!spoofersInitialized) logAccess('HTMLCanvasElement.toDataURL', { spoofed: false });
    return orig.apply(thisArg, args);
  });

  overrideMethod(HTMLCanvasElement.prototype, 'toBlob', (orig, thisArg, args) => {
    if (!spoofersInitialized) logAccess('HTMLCanvasElement.toBlob', { spoofed: false });
    return orig.apply(thisArg, args);
  });

  overrideMethod(CanvasRenderingContext2D.prototype, 'getImageData', (orig, thisArg, args) => {
    if (!spoofersInitialized) logAccess('CanvasRenderingContext2D.getImageData', { spoofed: false });
    return orig.apply(thisArg, args);
  });

  const monitorProp = (proto: object, prop: string, apiName: string) => {
    try {
      overrideGetter(proto, prop, (origGet, thisArg) => {
        if (!spoofersInitialized) logAccess(apiName, { spoofed: false });
        return origGet.call(thisArg);
      });
    } catch {
      // Property may not be writable
    }
  };

  monitorProp(Navigator.prototype, 'userAgent', 'navigator.userAgent');
  monitorProp(Navigator.prototype, 'platform', 'navigator.platform');
  monitorProp(Navigator.prototype, 'languages', 'navigator.languages');
  monitorProp(Navigator.prototype, 'hardwareConcurrency', 'navigator.hardwareConcurrency');
  monitorProp(Navigator.prototype, 'deviceMemory', 'navigator.deviceMemory');
  monitorProp(Navigator.prototype, 'maxTouchPoints', 'navigator.maxTouchPoints');

  monitorProp(Screen.prototype, 'width', 'screen.width');
  monitorProp(Screen.prototype, 'height', 'screen.height');
  monitorProp(Screen.prototype, 'colorDepth', 'screen.colorDepth');

  try {
    overrideMethod(WebGLRenderingContext.prototype, 'getParameter', (orig, thisArg, args) => {
      if (!spoofersInitialized) logAccess('WebGLRenderingContext.getParameter', { spoofed: false });
      return orig.apply(thisArg, args);
    });
  } catch {
    // WebGL may not be available
  }
}


let isMonitorInitialized = false;
let spoofersInitialized = false;

export function markSpoofersInitialized(): void {
  spoofersInitialized = true;
  lastReportedCount = 0;
}

export function initFingerprintMonitor(): void {
  if (isMonitorInitialized) return;
  isMonitorInitialized = true;

  installEarlyMonitoringWrappers();

  setTimeout(reportToBackground, 100);

  window.addEventListener('message', (event) => {
    if (event.data?.type === PAGE_MSG_GET_REPORT) {
      reportToBackground();
    }
    if (event.data?.type === PAGE_MSG_GET_RECOMMENDATIONS) {
      const recommendations = getRecommendations(event.data.settings);
      window.postMessage({
        type: PAGE_MSG_RECOMMENDATIONS,
        recommendations,
        accessedCategories: getAccessedCategories(),
      }, '*');
    }
  });
}

// Mark functions for individual spoofer categories
export function markCanvasSpoofed(mode: string): void {
  updateApiStatus(
    ['HTMLCanvasElement.toDataURL', 'HTMLCanvasElement.toBlob', 'CanvasRenderingContext2D.getImageData'],
    { spoofed: mode === 'noise', blocked: mode === 'block' }
  );
}

export function markWebGLSpoofed(mode: string): void {
  updateApiStatus(
    ['WebGLRenderingContext.getParameter', 'WebGL2RenderingContext.getParameter', 'WebGLRenderingContext.getExtension', 'WebGLRenderingContext.getSupportedExtensions', 'WEBGL_debug_renderer_info'],
    { spoofed: mode === 'noise', blocked: mode === 'block' }
  );
}

export function markNavigatorSpoofed(mode: string): void {
  updateApiStatus(
    ['navigator.userAgent', 'navigator.platform', 'navigator.languages'],
    { spoofed: mode !== 'off' }
  );
}

export function markScreenSpoofed(mode: string): void {
  updateApiStatus(
    ['screen.width', 'screen.height', 'screen.colorDepth', 'window.devicePixelRatio'],
    { spoofed: mode !== 'off' }
  );
}

export function markHardwareSpoofed(mode: string): void {
  updateApiStatus(
    ['navigator.hardwareConcurrency', 'navigator.deviceMemory', 'navigator.maxTouchPoints'],
    { spoofed: mode !== 'off' }
  );
}
