import React, { useState } from 'react';
import type { SpooferSettings, ProtectionMode } from '@/types';

/**
 * Signal information with description and risk level
 */
interface SignalInfo {
  key: string;
  name: string;
  description: string;
  risk: 'high' | 'medium' | 'low';
  api: string;
}

/**
 * Category with its signals
 */
interface CategorySignals {
  name: string;
  icon: string;
  signals: SignalInfo[];
}

/**
 * All fingerprinting signals organized by category
 */
const SIGNAL_CATEGORIES: CategorySignals[] = [
  {
    name: 'graphics',
    icon: '🎨',
    signals: [
      { key: 'canvas', name: 'Canvas 2D', description: 'Prevents canvas fingerprinting via toDataURL/getImageData', risk: 'high', api: 'HTMLCanvasElement' },
      { key: 'webgl', name: 'WebGL', description: 'Spoofs WebGL renderer, vendor, and parameters', risk: 'high', api: 'WebGLRenderingContext' },
      { key: 'webgl2', name: 'WebGL2', description: 'Spoofs WebGL2-specific parameters', risk: 'high', api: 'WebGL2RenderingContext' },
      { key: 'webglShaders', name: 'WebGL Shaders', description: 'Adds noise to shader precision', risk: 'medium', api: 'getShaderPrecisionFormat' },
      { key: 'webgpu', name: 'WebGPU', description: 'Spoofs WebGPU adapter info', risk: 'medium', api: 'GPU' },
      { key: 'svg', name: 'SVG', description: 'Adds noise to SVG rendering measurements', risk: 'medium', api: 'SVGElement' },
      { key: 'domRect', name: 'DOMRect', description: 'Adds noise to element bounding rectangles', risk: 'medium', api: 'getBoundingClientRect' },
      { key: 'textMetrics', name: 'Text Metrics', description: 'Adds noise to text measurement', risk: 'medium', api: 'measureText' },
      { key: 'offscreenCanvas', name: 'OffscreenCanvas', description: 'Protects OffscreenCanvas fingerprinting', risk: 'medium', api: 'OffscreenCanvas' },
    ],
  },
  {
    name: 'audio',
    icon: '🔊',
    signals: [
      { key: 'audioContext', name: 'AudioContext', description: 'Adds noise to audio processing fingerprint', risk: 'high', api: 'AudioContext' },
      { key: 'offlineAudio', name: 'Offline Audio', description: 'Protects OfflineAudioContext rendering', risk: 'high', api: 'OfflineAudioContext' },
      { key: 'latency', name: 'Audio Latency', description: 'Spoofs baseLatency and outputLatency', risk: 'low', api: 'AudioContext.baseLatency' },
      { key: 'codecs', name: 'Codecs', description: 'Normalizes codec support detection', risk: 'low', api: 'canPlayType' },
    ],
  },
  {
    name: 'hardware',
    icon: '💻',
    signals: [
      { key: 'screen', name: 'Screen', description: 'Spoofs screen dimensions and color depth', risk: 'high', api: 'screen' },
      { key: 'screenFrame', name: 'Screen Frame', description: 'Spoofs screenX/Y and outerWidth/Height', risk: 'medium', api: 'window.screenX' },
      { key: 'orientation', name: 'Orientation', description: 'Spoofs screen orientation API', risk: 'low', api: 'screen.orientation' },
      { key: 'deviceMemory', name: 'Device Memory', description: 'Reports common memory values', risk: 'medium', api: 'navigator.deviceMemory' },
      { key: 'hardwareConcurrency', name: 'CPU Cores', description: 'Reports common CPU core counts', risk: 'medium', api: 'navigator.hardwareConcurrency' },
      { key: 'mediaDevices', name: 'Media Devices', description: 'Anonymizes camera/microphone IDs', risk: 'medium', api: 'enumerateDevices' },
      { key: 'battery', name: 'Battery', description: 'Blocks or spoofs battery status', risk: 'low', api: 'getBattery' },
      { key: 'touch', name: 'Touch Points', description: 'Spoofs maxTouchPoints value', risk: 'low', api: 'navigator.maxTouchPoints' },
      { key: 'sensors', name: 'Sensors', description: 'Blocks accelerometer, gyroscope, etc.', risk: 'low', api: 'Sensor APIs' },
    ],
  },
  {
    name: 'navigator',
    icon: '🧭',
    signals: [
      { key: 'userAgent', name: 'User Agent', description: 'Spoofs browser identification strings', risk: 'high', api: 'navigator.userAgent' },
      { key: 'languages', name: 'Languages', description: 'Spoofs language preferences', risk: 'medium', api: 'navigator.languages' },
      { key: 'plugins', name: 'Plugins', description: 'Normalizes plugin/MIME type lists', risk: 'medium', api: 'navigator.plugins' },
      { key: 'clientHints', name: 'Client Hints', description: 'Spoofs User-Agent Client Hints API', risk: 'high', api: 'navigator.userAgentData' },
      { key: 'clipboard', name: 'Clipboard', description: 'Blocks clipboard fingerprinting', risk: 'low', api: 'navigator.clipboard' },
      { key: 'vibration', name: 'Vibration', description: 'Blocks vibration API detection', risk: 'low', api: 'navigator.vibrate' },
    ],
  },
  {
    name: 'timezone',
    icon: '🕐',
    signals: [
      { key: 'intl', name: 'Intl APIs', description: 'Spoofs timezone via Intl.DateTimeFormat', risk: 'high', api: 'Intl.DateTimeFormat' },
      { key: 'date', name: 'Date', description: 'Spoofs Date.getTimezoneOffset', risk: 'high', api: 'Date.getTimezoneOffset' },
    ],
  },
  {
    name: 'fonts',
    icon: '🔤',
    signals: [
      { key: 'enumeration', name: 'Font Detection', description: 'Prevents canvas-based font enumeration', risk: 'high', api: 'Canvas font detection' },
      { key: 'cssDetection', name: 'CSS Fonts', description: 'Prevents CSS-based font detection', risk: 'medium', api: 'CSS font-family' },
    ],
  },
  {
    name: 'network',
    icon: '🌐',
    signals: [
      { key: 'webrtc', name: 'WebRTC', description: 'Prevents local IP address leaks', risk: 'high', api: 'RTCPeerConnection' },
      { key: 'connection', name: 'Connection', description: 'Spoofs network connection info', risk: 'low', api: 'navigator.connection' },
    ],
  },
  {
    name: 'timing',
    icon: '⏱️',
    signals: [
      { key: 'performance', name: 'High-Res Time', description: 'Reduces performance.now() precision', risk: 'medium', api: 'performance.now' },
    ],
  },
  {
    name: 'storage',
    icon: '💾',
    signals: [
      { key: 'estimate', name: 'Storage Estimate', description: 'Spoofs storage quota values', risk: 'low', api: 'navigator.storage.estimate' },
      { key: 'indexedDB', name: 'IndexedDB', description: 'Protects IndexedDB fingerprinting', risk: 'low', api: 'indexedDB' },
      { key: 'webSQL', name: 'WebSQL', description: 'Blocks WebSQL detection', risk: 'low', api: 'openDatabase' },
    ],
  },
];

interface SignalListProps {
  settings: SpooferSettings;
  onChange: (category: string, signal: string, mode: ProtectionMode) => void;
  disabled?: boolean;
}

/**
 * Component showing individual signal toggles with descriptions
 */
export default function SignalList({ settings, onChange, disabled }: SignalListProps) {
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);

  const toggleCategory = (category: string) => {
    setExpandedCategory(expandedCategory === category ? null : category);
  };

  const getSignalValue = (category: string, signal: string): ProtectionMode => {
    const categorySettings = (settings as any)[category];
    return categorySettings?.[signal] || 'off';
  };

  const getRiskColor = (risk: 'high' | 'medium' | 'low') => {
    switch (risk) {
      case 'high': return 'text-red-400';
      case 'medium': return 'text-yellow-400';
      case 'low': return 'text-green-400';
    }
  };

  const getModeColor = (mode: ProtectionMode) => {
    switch (mode) {
      case 'noise': return 'bg-blue-600';
      case 'block': return 'bg-red-600';
      default: return 'bg-gray-600';
    }
  };

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
        Individual Signals
      </h3>

      {SIGNAL_CATEGORIES.map((category) => (
        <div key={category.name} className="bg-gray-800 rounded-lg overflow-hidden">
          {/* Category Header */}
          <button
            onClick={() => toggleCategory(category.name)}
            className="w-full px-3 py-2 flex items-center justify-between hover:bg-gray-700/50 transition-colors"
            disabled={disabled}
          >
            <div className="flex items-center gap-2">
              <span>{category.icon}</span>
              <span className="font-medium capitalize">{category.name}</span>
              <span className="text-xs text-gray-500">
                ({category.signals.length} signals)
              </span>
            </div>
            <svg
              className={`w-4 h-4 transition-transform ${expandedCategory === category.name ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Expanded Signal List */}
          {expandedCategory === category.name && (
            <div className="px-3 pb-3 space-y-2 border-t border-gray-700">
              {category.signals.map((signal) => {
                const value = getSignalValue(category.name, signal.key);
                return (
                  <div
                    key={signal.key}
                    className="pt-2 first:pt-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">{signal.name}</span>
                          <span className={`text-xs ${getRiskColor(signal.risk)}`}>
                            {signal.risk}
                          </span>
                        </div>
                        <p className="text-xs text-gray-400 mt-0.5">
                          {signal.description}
                        </p>
                        <code className="text-xs text-gray-500 mt-0.5 block">
                          {signal.api}
                        </code>
                      </div>

                      {/* Mode Selector */}
                      <div className="flex gap-1">
                        {(['off', 'noise', 'block'] as ProtectionMode[]).map((mode) => (
                          <button
                            key={mode}
                            onClick={() => onChange(category.name, signal.key, mode)}
                            disabled={disabled}
                            className={`px-2 py-1 text-xs rounded transition-colors ${
                              value === mode
                                ? getModeColor(mode) + ' text-white'
                                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                            } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                          >
                            {mode}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
