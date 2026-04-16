/**
 * Keyboard Layout Spoofer
 *
 * The Keyboard API can reveal the keyboard layout being used,
 * which is a fingerprinting vector.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

// US QWERTY keyboard layout mapping
const US_QWERTY_LAYOUT: Record<string, string> = {
  'KeyA': 'a', 'KeyB': 'b', 'KeyC': 'c', 'KeyD': 'd', 'KeyE': 'e',
  'KeyF': 'f', 'KeyG': 'g', 'KeyH': 'h', 'KeyI': 'i', 'KeyJ': 'j',
  'KeyK': 'k', 'KeyL': 'l', 'KeyM': 'm', 'KeyN': 'n', 'KeyO': 'o',
  'KeyP': 'p', 'KeyQ': 'q', 'KeyR': 'r', 'KeyS': 's', 'KeyT': 't',
  'KeyU': 'u', 'KeyV': 'v', 'KeyW': 'w', 'KeyX': 'x', 'KeyY': 'y',
  'KeyZ': 'z',
  'Digit0': '0', 'Digit1': '1', 'Digit2': '2', 'Digit3': '3', 'Digit4': '4',
  'Digit5': '5', 'Digit6': '6', 'Digit7': '7', 'Digit8': '8', 'Digit9': '9',
  'Minus': '-', 'Equal': '=', 'BracketLeft': '[', 'BracketRight': ']',
  'Backslash': '\\', 'Semicolon': ';', 'Quote': "'", 'Backquote': '`',
  'Comma': ',', 'Period': '.', 'Slash': '/',
  'Space': ' ', 'Enter': '\n', 'Tab': '\t',
};

/**
 * Initialize Keyboard layout spoofing
 */
export function initKeyboardSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Check if Keyboard API exists
  if (!('keyboard' in navigator)) return;

  const keyboard = (navigator as any).keyboard;

  if (!keyboard || !keyboard.getLayoutMap) return;

  const originalGetLayoutMap = keyboard.getLayoutMap.bind(keyboard);

  keyboard.getLayoutMap = async function (): Promise<Map<string, string>> {
    logAccess('navigator.keyboard.getLayoutMap', { spoofed: true, value: 'spoofed' });

    if (mode === 'block') {
      // Return empty map
      return new Map();
    }

    // Return US QWERTY layout
    return new Map(Object.entries(US_QWERTY_LAYOUT));
  };

}
