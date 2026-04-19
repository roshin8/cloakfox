import { useState, useEffect, useCallback } from 'react';
import browser from 'webextension-polyfill';
import type { ContainerSettings, SpooferSettings, ProfileConfig, ProtectionMode } from '@/types';
import { createDefaultSettings } from '@/types/settings';
import { MSG_GET_SETTINGS, MSG_SET_SETTINGS } from '@/constants';
import { popupLogger } from '@/lib/logger';

/**
 * Return type for useSettings hook
 */
interface UseSettingsReturn {
  /** Current settings */
  settings: ContainerSettings;
  /** Loading state */
  loading: boolean;
  /** Error message if any */
  error: string | null;
  /** Whether there are unsaved changes */
  isDirty: boolean;
  /** Update settings (debounced auto-save) */
  updateSettings: (updates: Partial<ContainerSettings>) => void;
  /** Update a specific spoofer setting */
  updateSpoofer: (category: string, signal: string, mode: ProtectionMode) => void;
  /** Update profile settings */
  updateProfile: (profile: Partial<ProfileConfig>) => void;
  /** Set protection level (updates multiple spoofers) */
  setProtectionLevel: (level: 0 | 1 | 2 | 3) => void;
  /** Toggle protection on/off */
  toggleEnabled: () => void;
  /** Reload settings from storage */
  reload: () => Promise<void>;
}

/**
 * Hook for managing container settings
 *
 * Provides settings management with automatic saving.
 *
 * @param containerId - The container to manage settings for
 *
 * @example
 * ```tsx
 * const { settings, updateSpoofer, setProtectionLevel } = useSettings('firefox-container-1');
 * ```
 */
export function useSettings(containerId: string | null): UseSettingsReturn {
  const [settings, setSettings] = useState<ContainerSettings>(createDefaultSettings());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);

  // Load settings when containerId changes
  const loadSettings = useCallback(async () => {
    if (!containerId) {
      setSettings(createDefaultSettings());
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const containerSettings = await browser.runtime.sendMessage({
        type: MSG_GET_SETTINGS,
        containerId,
      }) as ContainerSettings;

      setSettings(containerSettings);
      setIsDirty(false);
      popupLogger.debug('Settings loaded for container:', containerId);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load settings';
      setError(message);
      popupLogger.error('Failed to load settings:', err);
    } finally {
      setLoading(false);
    }
  }, [containerId]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  // Save settings to storage
  const saveSettings = useCallback(async (updates: Partial<ContainerSettings>) => {
    if (!containerId) return;

    try {
      await browser.runtime.sendMessage({
        type: MSG_SET_SETTINGS,
        containerId,
        settings: updates,
      });
      setIsDirty(false);
      popupLogger.debug('Settings saved for container:', containerId);
    } catch (err) {
      popupLogger.error('Failed to save settings:', err);
    }
  }, [containerId]);

  // Update settings with auto-save
  const updateSettings = useCallback((updates: Partial<ContainerSettings>) => {
    const newSettings = { ...settings, ...updates };
    setSettings(newSettings);
    setIsDirty(true);
    saveSettings(updates);
  }, [settings, saveSettings]);

  // Update a specific spoofer
  const updateSpoofer = useCallback((category: string, signal: string, mode: ProtectionMode) => {
    const currentCategory = (settings.spoofers as any)[category] || {};
    const updatedSpoofers = {
      ...settings.spoofers,
      [category]: {
        ...currentCategory,
        [signal]: mode,
      },
    };
    updateSettings({ spoofers: updatedSpoofers as SpooferSettings });
  }, [settings.spoofers, updateSettings]);

  // Update profile
  const updateProfile = useCallback((profile: Partial<ProfileConfig>) => {
    updateSettings({
      profile: { ...settings.profile, ...profile },
    });
  }, [settings.profile, updateSettings]);

  // Set protection level (preset configurations)
  const setProtectionLevel = useCallback((level: 0 | 1 | 2 | 3) => {
    // Each category uses Partial so presets can omit fields they don't
    // need to override — the active settings are merged on top below.
    type PartialSpoofers = {
      [K in keyof SpooferSettings]?: Partial<SpooferSettings[K]>;
    };
    const presets: Record<number, PartialSpoofers> = {
      0: {}, // Off - all remain as-is
      1: {   // Minimal - only high-risk
        graphics: { canvas: 'noise', webgl: 'noise', webgl2: 'noise', svg: 'off', domRect: 'off', textMetrics: 'off', offscreenCanvas: 'off', webglShaders: 'off', webgpu: 'off' },
        audio: { audioContext: 'noise', codecs: 'off', offlineAudio: 'off', latency: 'off' },
        network: { webrtc: 'public_only', connection: 'off' },
      },
      2: {   // Balanced
        graphics: { canvas: 'noise', webgl: 'noise', webgl2: 'noise', svg: 'noise', domRect: 'noise', textMetrics: 'noise', offscreenCanvas: 'noise', webglShaders: 'off', webgpu: 'off' },
        audio: { audioContext: 'noise', codecs: 'noise', offlineAudio: 'noise', latency: 'off' },
        hardware: { screen: 'noise', deviceMemory: 'noise', hardwareConcurrency: 'noise', mediaDevices: 'noise', battery: 'block', touch: 'noise', screenFrame: 'noise', orientation: 'off', sensors: 'off' },
        navigator: { userAgent: 'noise', languages: 'noise', plugins: 'noise', clientHints: 'noise', clipboard: 'off', vibration: 'off' },
        timezone: { intl: 'noise', date: 'noise' },
        fonts: { enumeration: 'noise', cssDetection: 'noise' },
        network: { webrtc: 'public_only', connection: 'noise' },
        timing: { performance: 'noise' },
      },
      3: {   // Strict - block where possible
        graphics: { canvas: 'noise', webgl: 'noise', webgl2: 'noise', svg: 'noise', domRect: 'noise', textMetrics: 'noise', offscreenCanvas: 'noise', webglShaders: 'noise', webgpu: 'block' },
        audio: { audioContext: 'noise', codecs: 'noise', offlineAudio: 'noise', latency: 'noise' },
        hardware: { screen: 'noise', deviceMemory: 'noise', hardwareConcurrency: 'noise', mediaDevices: 'noise', battery: 'block', touch: 'noise', screenFrame: 'noise', orientation: 'noise', sensors: 'block' },
        navigator: { userAgent: 'noise', languages: 'noise', plugins: 'noise', clientHints: 'noise', clipboard: 'block', vibration: 'block' },
        timezone: { intl: 'noise', date: 'noise' },
        fonts: { enumeration: 'noise', cssDetection: 'noise' },
        network: { webrtc: 'block', connection: 'noise' },
        timing: { performance: 'noise' },
        storage: { estimate: 'noise', indexedDB: 'noise', webSQL: 'block' },
        permissions: { query: 'noise', notification: 'noise' },
      },
    };

    const levelPreset = presets[level];
    if (level === 0) {
      updateSettings({ protectionLevel: level, enabled: false });
    } else {
      updateSettings({
        protectionLevel: level,
        enabled: true,
        spoofers: { ...settings.spoofers, ...levelPreset } as SpooferSettings,
      });
    }
  }, [settings.spoofers, updateSettings]);

  // Toggle enabled
  const toggleEnabled = useCallback(() => {
    updateSettings({ enabled: !settings.enabled });
  }, [settings.enabled, updateSettings]);

  return {
    settings,
    loading,
    error,
    isDirty,
    updateSettings,
    updateSpoofer,
    updateProfile,
    setProtectionLevel,
    toggleEnabled,
    reload: loadSettings,
  };
}

export default useSettings;
