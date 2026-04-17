import React, { useState, useMemo } from 'react';
import type { ContainerSettings } from '@/types';
import {
  ALL_PROFILES,
  PROFILES_BY_OS,
  type UserAgentProfile,
} from '@/lib/profiles/user-agents';
import {
  SCREENS_BY_CATEGORY,
  type ScreenProfile,
} from '@/lib/profiles/screen-sizes';

interface ProfileTabProps {
  settings: ContainerSettings;
  onSaveSettings: (updates: Partial<ContainerSettings>) => void;
  assignedProfile?: {
    userAgent?: {
      id?: string;
      name?: string;
      userAgent?: string;
      platform?: string;
      vendor?: string;
      platformName?: string;
      platformVersion?: string;
      mobile?: boolean;
    };
    screen?: {
      width: number;
      height: number;
      availWidth?: number;
      availHeight?: number;
      colorDepth?: number;
      pixelDepth?: number;
      devicePixelRatio?: number;
    };
    hardwareConcurrency?: number;
    deviceMemory?: number;
    languages?: string[];
    timezoneOffset?: number;
  };
}

// Common timezones with offsets
const TIMEZONES = [
  { name: 'Pacific Time (PT)', offset: -480, label: 'UTC-8' },
  { name: 'Mountain Time (MT)', offset: -420, label: 'UTC-7' },
  { name: 'Central Time (CT)', offset: -360, label: 'UTC-6' },
  { name: 'Eastern Time (ET)', offset: -300, label: 'UTC-5' },
  { name: 'UTC/GMT', offset: 0, label: 'UTC+0' },
  { name: 'Central European (CET)', offset: 60, label: 'UTC+1' },
  { name: 'Eastern European (EET)', offset: 120, label: 'UTC+2' },
  { name: 'India (IST)', offset: 330, label: 'UTC+5:30' },
  { name: 'China (CST)', offset: 480, label: 'UTC+8' },
  { name: 'Japan (JST)', offset: 540, label: 'UTC+9' },
  { name: 'Australia (AEST)', offset: 600, label: 'UTC+10' },
];

// Common language combinations
const LANGUAGE_PRESETS = [
  { id: 'en-US', label: 'English (US)', languages: ['en-US', 'en'] },
  { id: 'en-GB', label: 'English (UK)', languages: ['en-GB', 'en'] },
  { id: 'de-DE', label: 'German', languages: ['de-DE', 'de', 'en'] },
  { id: 'fr-FR', label: 'French', languages: ['fr-FR', 'fr', 'en'] },
  { id: 'es-ES', label: 'Spanish', languages: ['es-ES', 'es', 'en'] },
  { id: 'pt-BR', label: 'Portuguese (BR)', languages: ['pt-BR', 'pt', 'en'] },
  { id: 'ja-JP', label: 'Japanese', languages: ['ja-JP', 'ja', 'en'] },
  { id: 'zh-CN', label: 'Chinese (Simplified)', languages: ['zh-CN', 'zh', 'en'] },
  { id: 'ko-KR', label: 'Korean', languages: ['ko-KR', 'ko', 'en'] },
  { id: 'ru-RU', label: 'Russian', languages: ['ru-RU', 'ru', 'en'] },
];

export default function ProfileTab({
  settings,
  onSaveSettings,
  assignedProfile,
}: ProfileTabProps) {
  const [uaSearch, setUaSearch] = useState('');
  const [uaExpanded, setUaExpanded] = useState(false);
  const [screenExpanded, setScreenExpanded] = useState(false);
  const [languageExpanded, setLanguageExpanded] = useState(false);
  const [timezoneExpanded, setTimezoneExpanded] = useState(false);

  // Check if a setting is in custom mode
  const isUserAgentCustom = !!settings.profile?.userAgent;
  const isScreenCustom = !!settings.profile?.screen;
  const isLanguageCustom = !!settings.profile?.language;
  const isTimezoneCustom = !!settings.profile?.timezone;

  // Filter user agents based on search
  const filteredProfiles = useMemo(() => {
    if (!uaSearch) return null;
    const search = uaSearch.toLowerCase();
    return ALL_PROFILES.filter(
      (p) =>
        p.name.toLowerCase().includes(search) ||
        p.userAgent.toLowerCase().includes(search) ||
        p.platformName.toLowerCase().includes(search)
    );
  }, [uaSearch]);

  const handleUserAgentSelect = (profile: UserAgentProfile) => {
    onSaveSettings({
      profile: {
        ...settings.profile,
        userAgent: profile.userAgent,
        platform: profile.platform,
      },
    });
    setUaExpanded(false);
    setUaSearch('');
  };

  const handleUserAgentReset = () => {
    const { userAgent, platform, ...rest } = settings.profile || {};
    onSaveSettings({
      profile: rest,
    });
    setUaExpanded(false);
  };

  const handleScreenSelect = (screen: ScreenProfile) => {
    onSaveSettings({
      profile: {
        ...settings.profile,
        screen: { width: screen.width, height: screen.height },
      },
    });
    setScreenExpanded(false);
  };

  const handleScreenReset = () => {
    const { screen, ...rest } = settings.profile || {};
    onSaveSettings({
      profile: rest,
    });
    setScreenExpanded(false);
  };

  const handleLanguageSelect = (preset: typeof LANGUAGE_PRESETS[0]) => {
    onSaveSettings({
      profile: {
        ...settings.profile,
        language: preset.languages.join(', '),
      },
    });
    setLanguageExpanded(false);
  };

  const handleLanguageReset = () => {
    const { language, ...rest } = settings.profile || {};
    onSaveSettings({
      profile: rest,
    });
    setLanguageExpanded(false);
  };

  const handleTimezoneSelect = (tz: typeof TIMEZONES[0]) => {
    onSaveSettings({
      profile: {
        ...settings.profile,
        timezone: tz.offset.toString(),
      },
    });
    setTimezoneExpanded(false);
  };

  const handleTimezoneReset = () => {
    const { timezone, ...rest } = settings.profile || {};
    onSaveSettings({
      profile: rest,
    });
    setTimezoneExpanded(false);
  };

  // Get display values
  const getDisplayUserAgent = () => {
    if (isUserAgentCustom) {
      // Find the profile name from the UA string
      const profile = ALL_PROFILES.find(p => p.userAgent === settings.profile?.userAgent);
      return profile?.name || 'Custom';
    }
    return assignedProfile?.userAgent?.name || 'Auto-assigned';
  };

  const getDisplayScreen = () => {
    if (isScreenCustom && settings.profile?.screen) {
      return `${settings.profile.screen.width}×${settings.profile.screen.height}`;
    }
    if (assignedProfile?.screen) {
      return `${assignedProfile.screen.width}×${assignedProfile.screen.height}`;
    }
    return 'Auto-assigned';
  };

  const getDisplayLanguage = () => {
    if (isLanguageCustom && settings.profile?.language) {
      const primary = settings.profile.language.split(',')[0].trim();
      const preset = LANGUAGE_PRESETS.find(p => p.languages[0] === primary);
      return preset?.label || settings.profile.language;
    }
    if (assignedProfile?.languages) {
      return assignedProfile.languages.slice(0, 2).join(', ');
    }
    return 'Auto-assigned';
  };

  const getDisplayTimezone = () => {
    if (isTimezoneCustom && settings.profile?.timezone) {
      const offset = parseInt(settings.profile.timezone);
      const tz = TIMEZONES.find(t => t.offset === offset);
      return tz ? `${tz.label} (${tz.name})` : `UTC${offset >= 0 ? '+' : ''}${offset / 60}`;
    }
    if (assignedProfile?.timezoneOffset !== undefined) {
      const offset = assignedProfile.timezoneOffset;
      const hours = Math.floor(Math.abs(offset) / 60);
      const sign = offset >= 0 ? '+' : '-';
      return `UTC${sign}${hours}`;
    }
    return 'Auto-assigned';
  };

  return (
    <div className="space-y-3">
      {/* Current Fingerprint Summary */}
      <div className="bg-gradient-to-r from-blue-900/50 to-purple-900/50 rounded-lg p-3 border border-blue-700/30">
        <div className="text-xs text-blue-300 font-medium mb-2">Active Fingerprint</div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-gray-400">Browser: </span>
            <span className="text-white">{assignedProfile?.userAgent?.name?.split(' ')[0] || 'Unknown'}</span>
          </div>
          <div>
            <span className="text-gray-400">Platform: </span>
            <span className="text-white">{assignedProfile?.userAgent?.platformName || 'Unknown'}</span>
          </div>
          <div>
            <span className="text-gray-400">Screen: </span>
            <span className="text-white">
              {assignedProfile?.screen ? `${assignedProfile.screen.width}×${assignedProfile.screen.height}` : 'Unknown'}
            </span>
          </div>
          <div>
            <span className="text-gray-400">Cores: </span>
            <span className="text-white">{assignedProfile?.hardwareConcurrency || 'Unknown'}</span>
          </div>
        </div>
      </div>

      {/* User Agent */}
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <button
          onClick={() => setUaExpanded(!uaExpanded)}
          className="w-full p-3 flex items-center justify-between hover:bg-gray-700/50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <span className="text-lg">🌐</span>
            <div className="text-left">
              <div className="font-medium text-sm">User Agent</div>
              <div className="text-xs text-gray-400">
                {getDisplayUserAgent()}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded ${isUserAgentCustom ? 'bg-blue-500/20 text-blue-300' : 'bg-gray-600 text-gray-400'}`}>
              {isUserAgentCustom ? 'Custom' : 'Auto'}
            </span>
            <svg className={`w-4 h-4 transition-transform ${uaExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </button>

        {uaExpanded && (
          <div className="border-t border-gray-700 p-3 space-y-2">
            {/* Search */}
            <input
              type="text"
              value={uaSearch}
              onChange={(e) => setUaSearch(e.target.value)}
              placeholder="Search browsers..."
              className="w-full px-3 py-2 bg-gray-700 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />

            {/* Reset to Auto */}
            {isUserAgentCustom && (
              <button
                onClick={handleUserAgentReset}
                className="w-full px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-md text-sm text-left text-yellow-400"
              >
                ↩ Reset to Auto-assigned
              </button>
            )}

            {/* Browser List */}
            <div className="max-h-48 overflow-y-auto space-y-1">
              {filteredProfiles ? (
                filteredProfiles.length > 0 ? (
                  filteredProfiles.slice(0, 15).map((profile) => (
                    <button
                      key={profile.id}
                      onClick={() => handleUserAgentSelect(profile)}
                      className="w-full px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm text-left flex justify-between items-center"
                    >
                      <span>{profile.name}</span>
                      <span className="text-xs text-gray-400">{profile.platformName}</span>
                    </button>
                  ))
                ) : (
                  <div className="px-3 py-2 text-sm text-gray-400">No results</div>
                )
              ) : (
                Object.entries(PROFILES_BY_OS).map(([os, profiles]) => (
                  <div key={os} className="space-y-1">
                    <div className="text-xs font-medium text-gray-500 px-1 pt-2">
                      {os.toUpperCase()}
                    </div>
                    {profiles.map((profile) => (
                      <button
                        key={profile.id}
                        onClick={() => handleUserAgentSelect(profile)}
                        className="w-full px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm text-left flex justify-between items-center"
                      >
                        <span>{profile.name}</span>
                        <span className="text-xs text-gray-400">{profile.platformName}</span>
                      </button>
                    ))}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* Screen Size */}
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <button
          onClick={() => setScreenExpanded(!screenExpanded)}
          className="w-full p-3 flex items-center justify-between hover:bg-gray-700/50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <span className="text-lg">🖥️</span>
            <div className="text-left">
              <div className="font-medium text-sm">Screen Size</div>
              <div className="text-xs text-gray-400">
                {getDisplayScreen()}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded ${isScreenCustom ? 'bg-blue-500/20 text-blue-300' : 'bg-gray-600 text-gray-400'}`}>
              {isScreenCustom ? 'Custom' : 'Auto'}
            </span>
            <svg className={`w-4 h-4 transition-transform ${screenExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </button>

        {screenExpanded && (
          <div className="border-t border-gray-700 p-3 space-y-2">
            {/* Reset to Auto */}
            {isScreenCustom && (
              <button
                onClick={handleScreenReset}
                className="w-full px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-md text-sm text-left text-yellow-400"
              >
                ↩ Reset to Auto-assigned
              </button>
            )}

            {/* Screen List */}
            <div className="max-h-48 overflow-y-auto space-y-1">
              {Object.entries(SCREENS_BY_CATEGORY).map(([category, screens]) => (
                <div key={category} className="space-y-1">
                  <div className="text-xs font-medium text-gray-500 px-1 pt-2">
                    {category.toUpperCase()}
                  </div>
                  {screens.map((screen) => (
                    <button
                      key={screen.id}
                      onClick={() => handleScreenSelect(screen)}
                      className="w-full px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm text-left flex justify-between items-center"
                    >
                      <span>{screen.name}</span>
                      <span className="text-xs text-gray-400">{screen.width}×{screen.height}</span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Language */}
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <button
          onClick={() => setLanguageExpanded(!languageExpanded)}
          className="w-full p-3 flex items-center justify-between hover:bg-gray-700/50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <span className="text-lg">🌍</span>
            <div className="text-left">
              <div className="font-medium text-sm">Language</div>
              <div className="text-xs text-gray-400">
                {getDisplayLanguage()}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded ${isLanguageCustom ? 'bg-blue-500/20 text-blue-300' : 'bg-gray-600 text-gray-400'}`}>
              {isLanguageCustom ? 'Custom' : 'Auto'}
            </span>
            <svg className={`w-4 h-4 transition-transform ${languageExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </button>

        {languageExpanded && (
          <div className="border-t border-gray-700 p-3 space-y-2">
            {/* Reset to Auto */}
            {isLanguageCustom && (
              <button
                onClick={handleLanguageReset}
                className="w-full px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-md text-sm text-left text-yellow-400"
              >
                ↩ Reset to Auto-assigned
              </button>
            )}

            {/* Language List */}
            <div className="grid grid-cols-2 gap-1">
              {LANGUAGE_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  onClick={() => handleLanguageSelect(preset)}
                  className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm text-left"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Timezone */}
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <button
          onClick={() => setTimezoneExpanded(!timezoneExpanded)}
          className="w-full p-3 flex items-center justify-between hover:bg-gray-700/50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <span className="text-lg">🕐</span>
            <div className="text-left">
              <div className="font-medium text-sm">Timezone</div>
              <div className="text-xs text-gray-400">
                {getDisplayTimezone()}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded ${isTimezoneCustom ? 'bg-blue-500/20 text-blue-300' : 'bg-gray-600 text-gray-400'}`}>
              {isTimezoneCustom ? 'Custom' : 'Auto'}
            </span>
            <svg className={`w-4 h-4 transition-transform ${timezoneExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </button>

        {timezoneExpanded && (
          <div className="border-t border-gray-700 p-3 space-y-2">
            {/* Reset to Auto */}
            {isTimezoneCustom && (
              <button
                onClick={handleTimezoneReset}
                className="w-full px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-md text-sm text-left text-yellow-400"
              >
                ↩ Reset to Auto-assigned
              </button>
            )}

            {/* Timezone List */}
            <div className="max-h-48 overflow-y-auto space-y-1">
              {TIMEZONES.map((tz) => (
                <button
                  key={tz.offset}
                  onClick={() => handleTimezoneSelect(tz)}
                  className="w-full px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm text-left flex justify-between items-center"
                >
                  <span>{tz.name}</span>
                  <span className="text-xs text-gray-400">{tz.label}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Hardware Info (Read-only) */}
      <div className="bg-gray-800 rounded-lg p-3">
        <div className="text-xs text-gray-500 font-medium mb-2">Hardware (Auto-assigned)</div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex justify-between p-2 bg-gray-700/50 rounded">
            <span className="text-gray-400">CPU Cores</span>
            <span className="text-white">{assignedProfile?.hardwareConcurrency || '—'}</span>
          </div>
          <div className="flex justify-between p-2 bg-gray-700/50 rounded">
            <span className="text-gray-400">Memory</span>
            <span className="text-white">{assignedProfile?.deviceMemory ? `${assignedProfile.deviceMemory} GB` : '—'}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
