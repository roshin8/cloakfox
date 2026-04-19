import React from 'react';
import type { ProfileConfig } from '@/types';

/**
 * Browser profile preset definition
 */
interface ProfilePreset {
  id: string;
  name: string;
  description: string;
  icon: string;
  profile: Partial<ProfileConfig>;
}

/**
 * Available browser profile presets
 */
const PROFILE_PRESETS: ProfilePreset[] = [
  {
    id: 'real',
    name: 'Real Browser',
    description: 'Use your actual browser fingerprint',
    icon: '🔓',
    profile: {
      mode: 'real',
    },
  },
  {
    id: 'windows-chrome',
    name: 'Windows Chrome',
    description: 'Chrome 120 on Windows 10',
    icon: '🪟',
    profile: {
      mode: 'preset',
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      platform: 'Win32',
      language: 'en-US',
    },
  },
  {
    id: 'windows-firefox',
    name: 'Windows Firefox',
    description: 'Firefox 121 on Windows 10',
    icon: '🦊',
    profile: {
      mode: 'preset',
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
      platform: 'Win32',
      language: 'en-US',
    },
  },
  {
    id: 'mac-safari',
    name: 'macOS Safari',
    description: 'Safari 17 on macOS Sonoma',
    icon: '🧭',
    profile: {
      mode: 'preset',
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
      platform: 'MacIntel',
      language: 'en-US',
    },
  },
  {
    id: 'mac-chrome',
    name: 'macOS Chrome',
    description: 'Chrome 120 on macOS',
    icon: '🍎',
    profile: {
      mode: 'preset',
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      platform: 'MacIntel',
      language: 'en-US',
    },
  },
  {
    id: 'linux-firefox',
    name: 'Linux Firefox',
    description: 'Firefox 121 on Ubuntu',
    icon: '🐧',
    profile: {
      mode: 'preset',
      userAgent: 'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
      platform: 'Linux x86_64',
      language: 'en-US',
    },
  },
  {
    id: 'android-chrome',
    name: 'Android Chrome',
    description: 'Chrome on Android phone',
    icon: '📱',
    profile: {
      mode: 'preset',
      userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
      platform: 'Linux armv8l',
      language: 'en-US',
    },
  },
  {
    id: 'iphone-safari',
    name: 'iPhone Safari',
    description: 'Safari on iPhone 15',
    icon: '📲',
    profile: {
      mode: 'preset',
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
      platform: 'iPhone',
      language: 'en-US',
    },
  },
  {
    id: 'random',
    name: 'Random Profile',
    description: 'Rotate between common profiles',
    icon: '🎲',
    profile: {
      mode: 'random',
    },
  },
];

interface ProfilePresetsProps {
  currentProfile: ProfileConfig;
  onChange: (profile: Partial<ProfileConfig>) => void;
  disabled?: boolean;
}

/**
 * Component for quick browser profile selection
 */
export default function ProfilePresets({ currentProfile, onChange, disabled }: ProfilePresetsProps) {
  const getActivePresetId = (): string | null => {
    if (currentProfile.mode === 'real') return 'real';
    if (currentProfile.mode === 'random') return 'random';
    if (currentProfile.mode === 'custom') return null;

    // Find matching preset by user agent
    const preset = PROFILE_PRESETS.find(
      (p) => p.profile.userAgent === currentProfile.userAgent
    );
    return preset?.id || null;
  };

  const activePresetId = getActivePresetId();

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
        Browser Profile
      </h3>

      <div className="grid grid-cols-3 gap-2">
        {PROFILE_PRESETS.map((preset) => (
          <button
            key={preset.id}
            onClick={() => onChange(preset.profile)}
            disabled={disabled}
            className={`p-2 rounded-lg text-center transition-all ${
              activePresetId === preset.id
                ? 'bg-blue-600 ring-2 ring-blue-400'
                : 'bg-gray-800 hover:bg-gray-700'
            } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
            title={preset.description}
          >
            <div className="text-xl mb-1">{preset.icon}</div>
            <div className="text-xs font-medium truncate">{preset.name}</div>
          </button>
        ))}
      </div>

      {/* Current Profile Display */}
      <div className="p-3 bg-gray-800 rounded-lg">
        <div className="text-xs text-gray-400 mb-1">Current Profile</div>
        {currentProfile.mode === 'real' ? (
          <div className="text-sm text-yellow-400">Using real browser identity</div>
        ) : currentProfile.mode === 'random' ? (
          <div className="text-sm text-purple-400">Rotating profiles automatically</div>
        ) : (
          <div className="space-y-1">
            <div className="text-xs text-gray-300 font-mono break-all">
              {currentProfile.userAgent || 'Default user agent'}
            </div>
            <div className="flex gap-2 text-xs text-gray-500">
              <span>Platform: {currentProfile.platform || 'Default'}</span>
              <span>Lang: {currentProfile.language || 'Default'}</span>
            </div>
          </div>
        )}
      </div>

      {/* Custom Profile Option */}
      {currentProfile.mode !== 'custom' && (
        <button
          onClick={() => onChange({ mode: 'custom' })}
          disabled={disabled}
          className={`w-full p-2 text-sm text-gray-400 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors ${
            disabled ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          Customize profile...
        </button>
      )}
    </div>
  );
}
