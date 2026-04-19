/**
 * Dark Mode Hook
 *
 * Manages dark mode preference with system detection and manual override
 */

import { useState, useEffect } from 'react';
import browser from 'webextension-polyfill';

export type ThemeMode = 'auto' | 'light' | 'dark';

interface UseDarkModeReturn {
  isDark: boolean;
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  toggle: () => void;
}

export function useDarkMode(): UseDarkModeReturn {
  const [mode, setModeState] = useState<ThemeMode>('auto');
  const [systemDark, setSystemDark] = useState(false);

  // Load saved preference
  useEffect(() => {
    const loadPreference = async () => {
      try {
        const stored = await browser.storage.local.get('globalSettings');
        const globalSettings = (stored.globalSettings || {}) as { darkMode?: ThemeMode };
        if (globalSettings.darkMode) {
          setModeState(globalSettings.darkMode);
        }
      } catch (error) {
        console.error('Failed to load dark mode preference:', error);
      }
    };

    loadPreference();
  }, []);

  // Listen for system preference changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    setSystemDark(mediaQuery.matches);

    const handler = (e: MediaQueryListEvent) => {
      setSystemDark(e.matches);
    };

    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  // Apply dark mode class to document
  useEffect(() => {
    const isDark = mode === 'dark' || (mode === 'auto' && systemDark);

    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [mode, systemDark]);

  const setMode = async (newMode: ThemeMode) => {
    setModeState(newMode);

    try {
      const stored = await browser.storage.local.get('globalSettings');
      const globalSettings = (stored.globalSettings || {}) as Record<string, unknown>;
      await browser.storage.local.set({
        globalSettings: { ...globalSettings, darkMode: newMode },
      });
    } catch (error) {
      console.error('Failed to save dark mode preference:', error);
    }
  };

  const toggle = () => {
    const isDark = mode === 'dark' || (mode === 'auto' && systemDark);
    setMode(isDark ? 'light' : 'dark');
  };

  const isDark = mode === 'dark' || (mode === 'auto' && systemDark);

  return { isDark, mode, setMode, toggle };
}

export default useDarkMode;
