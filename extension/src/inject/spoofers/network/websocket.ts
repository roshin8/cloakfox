/**
 * WebSocket Spoofer
 *
 * WebSockets can leak IP addresses and be used for fingerprinting.
 * Chameleon can block all, block 3rd-party, or allow all.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

export function initWebSocketSpoofer(mode: ProtectionMode, _prng: PRNG): void {
  if (mode === 'off') return;

  const OriginalWebSocket = window.WebSocket;

  if (mode === 'block') {
    // Block all WebSocket connections
    (window as any).WebSocket = function(url: string, protocols?: string | string[]) {
      logAccess('WebSocket', { spoofed: true, blocked: true, value: 'blocked' });
      throw new DOMException(
        'WebSocket connection blocked by Cloakfox Shield',
        'SecurityError'
      );
    };
    (window as any).WebSocket.prototype = OriginalWebSocket.prototype;
    (window as any).WebSocket.CONNECTING = 0;
    (window as any).WebSocket.OPEN = 1;
    (window as any).WebSocket.CLOSING = 2;
    (window as any).WebSocket.CLOSED = 3;
  } else {
    // Noise mode: block 3rd-party WebSocket connections only
    (window as any).WebSocket = function(url: string | URL, protocols?: string | string[]) {
      logAccess('WebSocket', { spoofed: true, value: '3rd party blocked' });
      const wsUrl = new URL(url.toString());
      const pageHost = window.location.hostname;

      // Allow same-origin WebSocket connections
      if (wsUrl.hostname === pageHost || wsUrl.hostname.endsWith('.' + pageHost)) {
        return new OriginalWebSocket(url, protocols);
      }

      // Block cross-origin WebSocket
      throw new DOMException(
        'Cross-origin WebSocket blocked by Cloakfox Shield',
        'SecurityError'
      );
    };
    (window as any).WebSocket.prototype = OriginalWebSocket.prototype;
    (window as any).WebSocket.CONNECTING = 0;
    (window as any).WebSocket.OPEN = 1;
    (window as any).WebSocket.CLOSING = 2;
    (window as any).WebSocket.CLOSED = 3;
  }
}
