/**
 * WebRTC Spoofer - Prevents WebRTC IP leaks
 *
 * Note: Full WebRTC blocking is better done via browser.privacy API in background script.
 * This provides additional page-level protection.
 */

import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

type WebRTCMode = 'off' | 'public_only' | 'block';

/**
 * Initialize WebRTC spoofing
 */
export function initWebRTCSpoofer(mode: WebRTCMode, _prng: PRNG): void {
  if (mode === 'off') return;

  // Store original constructors
  const OriginalRTCPeerConnection = window.RTCPeerConnection;

  if (mode === 'block') {
    // Completely disable WebRTC
    // @ts-ignore
    window.RTCPeerConnection = function () {
      logAccess('RTCPeerConnection', { spoofed: true, blocked: true, value: 'blocked' });
      throw new Error('WebRTC is disabled');
    };

    // Also disable related APIs
    if ('RTCSessionDescription' in window) {
      // @ts-ignore
      window.RTCSessionDescription = function () {
        throw new Error('WebRTC is disabled');
      };
    }

    if ('RTCIceCandidate' in window) {
      // @ts-ignore
      window.RTCIceCandidate = function () {
        throw new Error('WebRTC is disabled');
      };
    }

    // Block getUserMedia as well
    if (navigator.mediaDevices?.getUserMedia) {
      navigator.mediaDevices.getUserMedia = async function () {
        throw new Error('getUserMedia is disabled');
      };
    }

    return;
  }

  // public_only mode - allow WebRTC but filter local IPs
  // @ts-ignore
  window.RTCPeerConnection = function (
    configuration?: RTCConfiguration
  ): RTCPeerConnection {
    // Filter out STUN/TURN servers that might leak IPs
    const filteredConfig: RTCConfiguration = {
      ...configuration,
      iceServers: configuration?.iceServers?.filter((server) => {
        // Allow TURN servers (they hide IP)
        const urls = Array.isArray(server.urls) ? server.urls : [server.urls];
        return urls.some((url) => url.startsWith('turn:'));
      }),
    };

    logAccess('RTCPeerConnection', { spoofed: true, value: 'public only' });
    const pc = new OriginalRTCPeerConnection(filteredConfig);

    // Intercept ICE candidates to filter local IPs
    const originalAddEventListener = pc.addEventListener.bind(pc);

    pc.addEventListener = function (
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | AddEventListenerOptions
    ): void {
      if (type === 'icecandidate') {
        const wrappedListener = function (event: RTCPeerConnectionIceEvent) {
          if (event.candidate) {
            const candidate = event.candidate.candidate;

            // Filter out local IP candidates
            if (isLocalIPCandidate(candidate)) {
              return;
            }
          }

          if (typeof listener === 'function') {
            listener.call(pc, event);
          } else {
            listener.handleEvent(event);
          }
        };

        return originalAddEventListener(type, wrappedListener, options);
      }

      return originalAddEventListener(type, listener, options);
    };

    // Also intercept onicecandidate property
    let _onicecandidate: ((event: RTCPeerConnectionIceEvent) => void) | null =
      null;

    Object.defineProperty(pc, 'onicecandidate', {
      get: () => _onicecandidate,
      set: (handler: ((event: RTCPeerConnectionIceEvent) => void) | null) => {
        if (handler) {
          _onicecandidate = function (event: RTCPeerConnectionIceEvent) {
            if (event.candidate) {
              const candidate = event.candidate.candidate;

              if (isLocalIPCandidate(candidate)) {
                return;
              }
            }

            handler(event);
          };
        } else {
          _onicecandidate = null;
        }
      },
    });

    return pc;
  };

  // Copy static properties
  Object.setPrototypeOf(window.RTCPeerConnection, OriginalRTCPeerConnection);

}

/**
 * Check if an ICE candidate contains a local IP
 */
function isLocalIPCandidate(candidate: string): boolean {
  // Match local IP patterns
  const localIPPatterns = [
    /10\.\d{1,3}\.\d{1,3}\.\d{1,3}/,
    /172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}/,
    /192\.168\.\d{1,3}\.\d{1,3}/,
    /127\.\d{1,3}\.\d{1,3}\.\d{1,3}/,
    /::1/,
    /fe80::/i,
    /fd[0-9a-f]{2}:/i,
  ];

  return localIPPatterns.some((pattern) => pattern.test(candidate));
}
