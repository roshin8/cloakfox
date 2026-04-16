import React, { useState } from 'react';
import type { ProtectionMode } from '@/types';

interface Props {
  category: string;
  description: string;
  settings: Record<string, ProtectionMode | string>;
  onChange: (settings: Record<string, ProtectionMode | string>) => void;
  disabled?: boolean;
}

const MODE_LABELS: Record<string, string> = {
  off: 'Off',
  noise: 'Noise',
  block: 'Block',
  public_only: 'Public Only',
};

const MODE_COLORS: Record<string, string> = {
  off: 'bg-gray-600',
  noise: 'bg-green-600',
  block: 'bg-red-600',
  public_only: 'bg-yellow-600',
};

export default function CategoryToggle({
  category,
  description,
  settings,
  onChange,
  disabled,
}: Props) {
  const [expanded, setExpanded] = useState(false);

  // Calculate overall category status
  const values = Object.values(settings);
  const allOff = values.every((v) => v === 'off');
  const allSame = values.every((v) => v === values[0]);
  const overallStatus = allOff ? 'off' : allSame ? values[0] : 'mixed';

  // Cycle through modes for a single setting
  const cycleMode = (key: string, currentValue: string) => {
    const modes: string[] =
      currentValue === 'public_only'
        ? ['off', 'public_only', 'block']
        : ['off', 'noise', 'block'];

    const currentIndex = modes.indexOf(currentValue);
    const nextIndex = (currentIndex + 1) % modes.length;

    onChange({ ...settings, [key]: modes[nextIndex] });
  };

  // Set all settings in category
  const setAll = (mode: ProtectionMode) => {
    const newSettings: Record<string, ProtectionMode | string> = {};
    for (const key of Object.keys(settings)) {
      // Preserve special modes like webrtc's public_only
      if (settings[key] === 'public_only' && mode === 'noise') {
        newSettings[key] = 'public_only';
      } else {
        newSettings[key] = mode;
      }
    }
    onChange(newSettings);
  };

  return (
    <div
      className={`bg-gray-800 rounded-lg overflow-hidden ${
        disabled ? 'opacity-50' : ''
      }`}
    >
      {/* Category Header */}
      <button
        onClick={() => !disabled && setExpanded(!expanded)}
        disabled={disabled}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-700/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div
            className={`w-2 h-2 rounded-full ${
              overallStatus === 'off'
                ? 'bg-gray-500'
                : overallStatus === 'mixed'
                ? 'bg-yellow-500'
                : 'bg-green-500'
            }`}
          />
          <div className="text-left">
            <div className="font-medium">{category}</div>
            <div className="text-xs text-gray-400">{description}</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Quick toggle buttons */}
          <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setAll('off')}
              className={`px-2 py-1 text-xs rounded ${
                allOff ? 'bg-gray-600 text-white' : 'bg-gray-700 text-gray-400'
              }`}
            >
              Off
            </button>
            <button
              onClick={() => setAll('noise')}
              className={`px-2 py-1 text-xs rounded ${
                overallStatus === 'noise'
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-700 text-gray-400'
              }`}
            >
              On
            </button>
          </div>

          {/* Expand arrow */}
          <svg
            className={`w-4 h-4 transition-transform ${
              expanded ? 'rotate-180' : ''
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </button>

      {/* Expanded Settings */}
      {expanded && (
        <div className="px-4 pb-3 space-y-2 border-t border-gray-700 pt-2">
          {Object.entries(settings).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between">
              <span className="text-sm text-gray-300 capitalize">
                {key.replace(/([A-Z])/g, ' $1').trim()}
              </span>
              <button
                onClick={() => cycleMode(key, value as string)}
                className={`px-3 py-1 text-xs rounded-full ${
                  MODE_COLORS[value as string] || 'bg-gray-600'
                } text-white`}
              >
                {MODE_LABELS[value as string] || value}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
