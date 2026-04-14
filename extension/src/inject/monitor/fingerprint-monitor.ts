/**
 * Fingerprint access monitor — tracks which fingerprinting APIs
 * are accessed by page scripts. Reports to popup for visibility.
 *
 * Does NOT interfere with spoofing — read-only observation.
 */

interface AccessRecord {
  category: string;
  api: string;
  count: number;
  firstAccess: number;
}

const accessLog = new Map<string, AccessRecord>();

function recordAccess(category: string, api: string): void {
  const key = `${category}:${api}`;
  const existing = accessLog.get(key);
  if (existing) {
    existing.count++;
  } else {
    accessLog.set(key, { category, api, count: 1, firstAccess: Date.now() });
  }

  // Notify content script (which relays to background)
  window.postMessage(
    { type: 'CLOAKFOX_FINGERPRINT_ACCESS', category, api },
    '*'
  );
}

/** Install passive observers on common fingerprinting APIs */
export function initFingerprintMonitor(): void {
  // Canvas
  const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
  HTMLCanvasElement.prototype.toDataURL = function (...args) {
    recordAccess('canvas', 'toDataURL');
    return origToDataURL.apply(this, args);
  };

  const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
  CanvasRenderingContext2D.prototype.getImageData = function (...args) {
    recordAccess('canvas', 'getImageData');
    return origGetImageData.apply(this, args);
  };

  // WebGL
  const origGetParameter = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function (...args) {
    recordAccess('webgl', 'getParameter');
    return origGetParameter.apply(this, args);
  };

  // Audio
  const origCreateOscillator = AudioContext.prototype.createOscillator;
  AudioContext.prototype.createOscillator = function (...args) {
    recordAccess('audio', 'createOscillator');
    return origCreateOscillator.apply(this, args);
  };
}

/** Get all recorded accesses (called by content script bridge) */
export function getAccessLog(): AccessRecord[] {
  return Array.from(accessLog.values());
}
