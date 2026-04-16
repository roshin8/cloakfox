/**
 * Error Stack Trace Spoofer
 *
 * Error stack traces can reveal browser version, OS, and
 * extension information through their format.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize Error stack trace spoofing
 */
export function initErrorSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  const OriginalError = window.Error;

  // Create a proxy for the Error constructor
  window.Error = function (message?: string): Error {
    const error = new OriginalError(message);

    if (mode === 'block') {
      // Remove stack trace entirely
      Object.defineProperty(error, 'stack', {
        value: `Error: ${message || ''}`,
        writable: true,
        configurable: true,
      });
    } else if (mode === 'noise') {
      // Normalize stack trace format
      const originalStack = error.stack;
      if (originalStack) {
        const normalizedStack = normalizeStackTrace(originalStack);
        Object.defineProperty(error, 'stack', {
          value: normalizedStack,
          writable: true,
          configurable: true,
        });
      }
    }

    return error;
  } as ErrorConstructor;

  // Copy prototype and static methods
  window.Error.prototype = OriginalError.prototype;
  Object.setPrototypeOf(window.Error, OriginalError);

  // Also spoof captureStackTrace if it exists (V8-specific)
  if ('captureStackTrace' in OriginalError) {
    (window.Error as any).captureStackTrace = function (
      targetObject: object,
      constructorOpt?: Function
    ): void {
      logAccess('Error.captureStackTrace', { spoofed: true, value: 'modified' });
      (OriginalError as any).captureStackTrace(targetObject, constructorOpt);

      if (mode === 'block') {
        (targetObject as any).stack = 'Error';
      } else if (mode === 'noise') {
        const stack = (targetObject as any).stack;
        if (stack) {
          (targetObject as any).stack = normalizeStackTrace(stack);
        }
      }
    };
  }

  // Spoof stackTraceLimit
  Object.defineProperty(window.Error, 'stackTraceLimit', {
    value: 10, // Common value
    writable: true,
    configurable: true,
  });

}

/**
 * Normalize a stack trace to remove identifying information
 */
function normalizeStackTrace(stack: string): string {
  const lines = stack.split('\n');

  return lines
    .map((line, index) => {
      if (index === 0) return line; // Keep error message

      // Remove file paths that might reveal extensions or system info
      // Normalize to generic format: "    at functionName (script.js:line:col)"
      const match = line.match(/^\s*at\s+(.+?)\s+\((.+?):(\d+):(\d+)\)$/);

      if (match) {
        const [, funcName, , lineNum, colNum] = match;
        return `    at ${funcName} (script.js:${lineNum}:${colNum})`;
      }

      // Handle anonymous functions
      const anonMatch = line.match(/^\s*at\s+(.+?):(\d+):(\d+)$/);
      if (anonMatch) {
        const [, , lineNum, colNum] = anonMatch;
        return `    at script.js:${lineNum}:${colNum}`;
      }

      return line;
    })
    .join('\n');
}
