/**
 * Event Loop Timing Jitter
 *
 * Amazon and advanced fingerprinters use queue timing variation to identify
 * devices. They measure how long setTimeout/setInterval/requestAnimationFrame
 * callbacks take to fire, which reflects CPU performance and system load.
 *
 * Add small, random jitter to timer callbacks to make timing patterns
 * less deterministic while preserving functionality.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

export function initEventLoopJitter(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Max jitter in ms — small enough to not break functionality
  const maxJitter = mode === 'block' ? 5 : 2;
  let logged = false;

  const origSetTimeout = window.setTimeout;
  const origSetInterval = window.setInterval;
  const origRAF = window.requestAnimationFrame;

  // Add jitter to setTimeout
  window.setTimeout = function(handler: TimerHandler, timeout?: number, ...args: any[]): number {
    if (!logged) { logAccess('setTimeout', { spoofed: true }); logged = true; }
    const jitter = Math.floor(prng.nextFloat() * maxJitter);
    return origSetTimeout(handler, (timeout || 0) + jitter, ...args);
  } as typeof setTimeout;

  // Add jitter to setInterval
  window.setInterval = function(handler: TimerHandler, timeout?: number, ...args: any[]): number {
    const jitter = Math.floor(prng.nextFloat() * maxJitter);
    return origSetInterval(handler, (timeout || 0) + jitter, ...args);
  } as typeof setInterval;

  // Add jitter to requestAnimationFrame
  if (origRAF) {
    window.requestAnimationFrame = function(callback: FrameRequestCallback): number {
      return origRAF((timestamp) => {
        // Add sub-ms noise to the timestamp
        const noise = prng.nextFloat() * 0.1;
        callback(timestamp + noise);
      });
    };
  }
}
