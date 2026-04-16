import React, { useState, useEffect } from 'react';
import browser from 'webextension-polyfill';
import type { RotationSchedule, RotationSettings } from '@/background/profile-rotation';
import { popupLogger } from '@/lib/logger';

/**
 * Message types for rotation operations
 */
const MSG_GET_ROTATION_SETTINGS = 'GET_ROTATION_SETTINGS';
const MSG_SET_ROTATION_SETTINGS = 'SET_ROTATION_SETTINGS';
const MSG_ROTATE_NOW = 'ROTATE_NOW';

interface ProfileRotationProps {
  containerId: string | null;
}

/**
 * Schedule options with descriptions
 */
const SCHEDULE_OPTIONS: { value: RotationSchedule; label: string; description: string }[] = [
  { value: 'off', label: 'Off', description: 'Manual rotation only' },
  { value: 'session', label: 'Session', description: 'Rotate on browser restart' },
  { value: 'hourly', label: 'Hourly', description: 'Rotate every hour' },
  { value: 'daily', label: 'Daily', description: 'Rotate every 24 hours' },
  { value: 'weekly', label: 'Weekly', description: 'Rotate every 7 days' },
];

/**
 * Component for managing profile rotation settings
 */
export default function ProfileRotationSettings({ containerId }: ProfileRotationProps) {
  const [settings, setSettings] = useState<RotationSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [rotating, setRotating] = useState(false);

  // Load rotation settings
  useEffect(() => {
    async function loadSettings() {
      try {
        const result = await browser.storage.local.get('rotationSettings');
        setSettings(result.rotationSettings || {
          enabled: false,
          schedule: 'daily',
          lastRotation: {},
          rotateOnStartup: false,
        });
      } catch (error) {
        popupLogger.error('Failed to load rotation settings:', error);
      } finally {
        setLoading(false);
      }
    }

    loadSettings();
  }, []);

  // Save settings
  const saveSettings = async (updates: Partial<RotationSettings>) => {
    if (!settings) return;

    const newSettings = { ...settings, ...updates };
    setSettings(newSettings);

    try {
      await browser.storage.local.set({ rotationSettings: newSettings });
    } catch (error) {
      popupLogger.error('Failed to save rotation settings:', error);
    }
  };

  // Rotate now
  const handleRotateNow = async () => {
    if (!containerId) return;

    setRotating(true);
    try {
      await browser.runtime.sendMessage({
        type: MSG_ROTATE_NOW,
        containerId,
      });

      // Update last rotation time
      if (settings) {
        saveSettings({
          lastRotation: {
            ...settings.lastRotation,
            [containerId]: Date.now(),
          },
        });
      }
    } catch (error) {
      popupLogger.error('Failed to rotate profile:', error);
    } finally {
      setRotating(false);
    }
  };

  // Format last rotation time
  const formatLastRotation = (): string => {
    if (!settings || !containerId) return 'Never';

    const timestamp = settings.lastRotation[containerId];
    if (!timestamp) return 'Never';

    const date = new Date(timestamp);
    const now = Date.now();
    const diff = now - timestamp;

    if (diff < 60 * 1000) return 'Just now';
    if (diff < 60 * 60 * 1000) return `${Math.floor(diff / (60 * 1000))}m ago`;
    if (diff < 24 * 60 * 60 * 1000) return `${Math.floor(diff / (60 * 60 * 1000))}h ago`;

    return date.toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="p-3 bg-gray-800 rounded-lg animate-pulse">
        <div className="h-4 bg-gray-700 rounded w-1/2"></div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
        Profile Rotation
      </h3>

      <div className="p-3 bg-gray-800 rounded-lg space-y-3">
        {/* Enable Toggle */}
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium text-sm">Auto-Rotate</div>
            <div className="text-xs text-gray-500">
              Periodically regenerate fingerprint seed
            </div>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={settings?.enabled || false}
              onChange={(e) => saveSettings({ enabled: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-gray-600 rounded-full peer peer-checked:bg-green-500 peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
          </label>
        </div>

        {/* Schedule Selection */}
        {settings?.enabled && (
          <div className="space-y-2">
            <div className="text-xs text-gray-400">Rotation Schedule</div>
            <div className="grid grid-cols-5 gap-1">
              {SCHEDULE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={() => saveSettings({ schedule: option.value })}
                  className={`px-2 py-1 text-xs rounded transition-colors ${
                    settings.schedule === option.value
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                  title={option.description}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Rotate on Startup */}
        {settings?.enabled && (
          <div className="flex items-center justify-between">
            <div className="text-sm">Rotate on startup</div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings?.rotateOnStartup || false}
                onChange={(e) => saveSettings({ rotateOnStartup: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-gray-600 rounded-full peer peer-checked:bg-green-500 peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
            </label>
          </div>
        )}

        {/* Status and Manual Rotate */}
        <div className="pt-2 border-t border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-500">Last rotation</div>
              <div className="text-sm">{formatLastRotation()}</div>
            </div>
            <button
              onClick={handleRotateNow}
              disabled={!containerId || rotating}
              className="px-3 py-1 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 disabled:text-gray-500 rounded text-sm transition-colors"
            >
              {rotating ? 'Rotating...' : 'Rotate Now'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
