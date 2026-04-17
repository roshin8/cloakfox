import React, { useState } from 'react';
import type { ContainerSettings } from '@/types';

/**
 * Domain exception preset definition
 */
interface DomainPreset {
  id: string;
  name: string;
  description: string;
  domains: string[];
  icon: string;
}

/**
 * Pre-defined domain exception presets for common sites that may break
 */
const DOMAIN_PRESETS: DomainPreset[] = [
  {
    id: 'banking',
    name: 'Banking Sites',
    description: 'Common banking and financial sites',
    icon: '🏦',
    domains: [
      '*.chase.com',
      '*.bankofamerica.com',
      '*.wellsfargo.com',
      '*.citi.com',
      '*.capitalone.com',
      '*.usbank.com',
      '*.pnc.com',
      '*.discover.com',
      '*.americanexpress.com',
      '*.paypal.com',
      '*.venmo.com',
    ],
  },
  {
    id: 'streaming',
    name: 'Streaming Services',
    description: 'Video and music streaming platforms',
    icon: '🎬',
    domains: [
      '*.netflix.com',
      '*.hulu.com',
      '*.disneyplus.com',
      '*.hbomax.com',
      '*.primevideo.com',
      '*.spotify.com',
      '*.youtube.com',
      '*.twitch.tv',
      '*.crunchyroll.com',
    ],
  },
  {
    id: 'gaming',
    name: 'Gaming Platforms',
    description: 'Game stores and platforms',
    icon: '🎮',
    domains: [
      '*.steampowered.com',
      '*.store.steampowered.com',
      '*.epicgames.com',
      '*.gog.com',
      '*.ea.com',
      '*.origin.com',
      '*.blizzard.com',
      '*.battle.net',
      '*.riotgames.com',
    ],
  },
  {
    id: 'videoconferencing',
    name: 'Video Conferencing',
    description: 'Meeting and collaboration tools',
    icon: '📹',
    domains: [
      '*.zoom.us',
      '*.teams.microsoft.com',
      '*.meet.google.com',
      '*.webex.com',
      '*.gotomeeting.com',
      '*.slack.com',
      '*.discord.com',
    ],
  },
  {
    id: 'shopping',
    name: 'Shopping Sites',
    description: 'E-commerce platforms',
    icon: '🛒',
    domains: [
      '*.amazon.com',
      '*.ebay.com',
      '*.walmart.com',
      '*.target.com',
      '*.bestbuy.com',
      '*.etsy.com',
      '*.shopify.com',
    ],
  },
  {
    id: 'google',
    name: 'Google Services',
    description: 'Google apps and services',
    icon: '🔍',
    domains: [
      '*.google.com',
      '*.googleapis.com',
      '*.gstatic.com',
      '*.gmail.com',
      '*.youtube.com',
      '*.googlevideo.com',
    ],
  },
  {
    id: 'microsoft',
    name: 'Microsoft Services',
    description: 'Microsoft 365 and Azure',
    icon: '🪟',
    domains: [
      '*.microsoft.com',
      '*.microsoftonline.com',
      '*.office.com',
      '*.office365.com',
      '*.live.com',
      '*.outlook.com',
      '*.azure.com',
    ],
  },
  {
    id: 'social',
    name: 'Social Media',
    description: 'Social networking sites',
    icon: '📱',
    domains: [
      '*.facebook.com',
      '*.instagram.com',
      '*.twitter.com',
      '*.x.com',
      '*.linkedin.com',
      '*.reddit.com',
      '*.tiktok.com',
    ],
  },
];

interface DomainExceptionsProps {
  domainRules: Record<string, Partial<ContainerSettings>>;
  onChange: (domainRules: Record<string, Partial<ContainerSettings>>) => void;
  disabled?: boolean;
}

/**
 * Component for managing domain exceptions
 */
export default function DomainExceptions({ domainRules, onChange, disabled }: DomainExceptionsProps) {
  const [customDomain, setCustomDomain] = useState('');
  const [expandedPreset, setExpandedPreset] = useState<string | null>(null);

  /**
   * Check if a preset is enabled (all domains have exceptions)
   */
  const isPresetEnabled = (preset: DomainPreset): boolean => {
    return preset.domains.every((domain) => domain in domainRules);
  };

  /**
   * Check if a preset is partially enabled
   */
  const isPresetPartial = (preset: DomainPreset): boolean => {
    const count = preset.domains.filter((domain) => domain in domainRules).length;
    return count > 0 && count < preset.domains.length;
  };

  /**
   * Toggle a preset on/off
   */
  const togglePreset = (preset: DomainPreset) => {
    const newRules = { ...domainRules };

    if (isPresetEnabled(preset)) {
      // Remove all domains from preset
      preset.domains.forEach((domain) => {
        delete newRules[domain];
      });
    } else {
      // Add all domains with protection disabled
      preset.domains.forEach((domain) => {
        newRules[domain] = { enabled: false };
      });
    }

    onChange(newRules);
  };

  /**
   * Toggle a single domain
   */
  const toggleDomain = (domain: string) => {
    const newRules = { ...domainRules };

    if (domain in newRules) {
      delete newRules[domain];
    } else {
      newRules[domain] = { enabled: false };
    }

    onChange(newRules);
  };

  /**
   * Add a custom domain exception
   */
  const addCustomDomain = () => {
    if (!customDomain.trim()) return;

    const domain = customDomain.trim().toLowerCase();
    const newRules = { ...domainRules };
    newRules[domain] = { enabled: false };

    onChange(newRules);
    setCustomDomain('');
  };

  /**
   * Get custom domains (not in any preset)
   */
  const getCustomDomains = (): string[] => {
    const presetDomains = new Set(DOMAIN_PRESETS.flatMap((p) => p.domains));
    return Object.keys(domainRules).filter((d) => !presetDomains.has(d));
  };

  const customDomains = getCustomDomains();

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
        Domain Exceptions
      </h3>

      <p className="text-xs text-gray-500">
        Disable protection on sites that may break with fingerprint spoofing.
      </p>

      {/* Preset Categories */}
      <div className="space-y-2">
        {DOMAIN_PRESETS.map((preset) => {
          const enabled = isPresetEnabled(preset);
          const partial = isPresetPartial(preset);

          return (
            <div key={preset.id} className="bg-gray-800 rounded-lg overflow-hidden">
              {/* Preset Header */}
              <div className="flex items-center justify-between p-2">
                <button
                  onClick={() => setExpandedPreset(expandedPreset === preset.id ? null : preset.id)}
                  className="flex items-center gap-2 flex-1 text-left"
                  disabled={disabled}
                >
                  <span>{preset.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm">{preset.name}</div>
                    <div className="text-xs text-gray-500 truncate">{preset.description}</div>
                  </div>
                  <svg
                    className={`w-4 h-4 text-gray-400 transition-transform ${
                      expandedPreset === preset.id ? 'rotate-180' : ''
                    }`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                <button
                  onClick={() => togglePreset(preset)}
                  disabled={disabled}
                  className={`ml-2 px-2 py-1 text-xs rounded transition-colors ${
                    enabled
                      ? 'bg-green-600 text-white'
                      : partial
                      ? 'bg-yellow-600 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {enabled ? 'On' : partial ? 'Partial' : 'Off'}
                </button>
              </div>

              {/* Expanded Domain List */}
              {expandedPreset === preset.id && (
                <div className="px-2 pb-2 border-t border-gray-700">
                  <div className="flex flex-wrap gap-1 pt-2">
                    {preset.domains.map((domain) => {
                      const isEnabled = domain in domainRules;
                      return (
                        <button
                          key={domain}
                          onClick={() => toggleDomain(domain)}
                          disabled={disabled}
                          className={`px-2 py-0.5 text-xs rounded transition-colors ${
                            isEnabled
                              ? 'bg-green-900/50 text-green-300 border border-green-500/30'
                              : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                          } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                        >
                          {domain}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Custom Domains */}
      <div className="space-y-2">
        <div className="flex gap-2">
          <input
            type="text"
            value={customDomain}
            onChange={(e) => setCustomDomain(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addCustomDomain()}
            placeholder="Add custom domain (e.g., *.example.com)"
            disabled={disabled}
            className="flex-1 px-2 py-1 bg-gray-800 border border-gray-700 rounded text-sm placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={addCustomDomain}
            disabled={disabled || !customDomain.trim()}
            className="px-3 py-1 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 rounded text-sm transition-colors"
          >
            Add
          </button>
        </div>

        {/* Custom Domain List */}
        {customDomains.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {customDomains.map((domain) => (
              <span
                key={domain}
                className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-700 rounded text-xs"
              >
                {domain}
                <button
                  onClick={() => toggleDomain(domain)}
                  disabled={disabled}
                  className="text-gray-400 hover:text-red-400"
                >
                  x
                </button>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
