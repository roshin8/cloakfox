/**
 * Options Tab - Chameleon-style injection/standard/cookie controls
 */

import React, { useState } from 'react';
import type { ContainerSettings, ProtectionMode } from '@/types';

interface OptionsTabProps {
  settings: ContainerSettings;
  onSaveSettings: (updates: Partial<ContainerSettings>) => void;
}

type SubTab = 'injection' | 'standard' | 'cookie';

export default function OptionsTab({ settings, onSaveSettings }: OptionsTabProps) {
  const [subTab, setSubTab] = useState<SubTab>('injection');

  const updateSpoofer = (category: string, key: string, value: ProtectionMode | string) => {
    const current = { ...settings.spoofers } as any;
    current[category] = { ...current[category], [key]: value };
    onSaveSettings({ spoofers: current });
  };

  const getMode = (category: string, key: string): string => {
    return (settings.spoofers as any)[category]?.[key] || 'off';
  };

  return (
    <div className="space-y-3">
      {/* Sub-tab pills */}
      <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--bg-elevated)' }}>
        {(['injection', 'standard', 'cookie'] as SubTab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setSubTab(tab)}
            className={`subtab flex-1 text-center ${subTab === tab ? 'active' : ''}`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Injection Sub-tab */}
      {subTab === 'injection' && (
        <div className="card space-y-0">
          <ToggleRow
            label="Spoof Canvas Fingerprint"
            desc="Add noise to canvas rendering"
            checked={getMode('graphics', 'canvas') !== 'off'}
            onChange={(on) => updateSpoofer('graphics', 'canvas', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Spoof Audio Context"
            desc="Add noise to audio processing"
            checked={getMode('audio', 'audioContext') !== 'off'}
            onChange={(on) => updateSpoofer('audio', 'audioContext', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Spoof Client Rects"
            desc="Add noise to getBoundingClientRect"
            checked={getMode('graphics', 'domRect') !== 'off'}
            onChange={(on) => updateSpoofer('graphics', 'domRect', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Spoof Font Fingerprint"
            desc="Randomize detected fonts"
            checked={getMode('fonts', 'enumeration') !== 'off'}
            onChange={(on) => updateSpoofer('fonts', 'enumeration', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Block Media Devices"
            desc="Hide cameras and microphones"
            checked={getMode('hardware', 'mediaDevices') === 'block'}
            onChange={(on) => updateSpoofer('hardware', 'mediaDevices', on ? 'block' : 'noise')}
          />
          <ToggleRow
            label="Protect Keyboard Fingerprint"
            desc="Normalize keyboard layout"
            checked={getMode('keyboard', 'layout') !== 'off'}
            onChange={(on) => updateSpoofer('keyboard', 'layout', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Protect Window.name"
            desc="Block cross-site tracking via window.name"
            checked={getMode('navigator', 'windowName') !== 'off'}
            onChange={(on) => updateSpoofer('navigator', 'windowName', on ? 'block' : 'off')}
          />
          <ToggleRow
            label="Limit Tab History"
            desc="Spoof window.history.length"
            checked={getMode('navigator', 'tabHistory') !== 'off'}
            onChange={(on) => updateSpoofer('navigator', 'tabHistory', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Protect Keyboard Cadence"
            desc="Normalize keystroke timing patterns"
            checked={getMode('keyboard', 'cadence') !== 'off'}
            onChange={(on) => updateSpoofer('keyboard', 'cadence', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Block CSS Exfil"
            desc="Prevent CSS-based data theft"
            checked={getMode('css', 'mediaQueries') !== 'off'}
            onChange={(on) => updateSpoofer('css', 'mediaQueries', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Spoof WebGL"
            desc="Noise WebGL vendor and renderer"
            checked={getMode('graphics', 'webgl') !== 'off'}
            onChange={(on) => updateSpoofer('graphics', 'webgl', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Spoof Math Functions"
            desc="Add noise to Math.tan, sin, cos"
            checked={getMode('math', 'functions') !== 'off'}
            onChange={(on) => updateSpoofer('math', 'functions', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Reduce Timer Precision"
            desc="Limit performance.now() accuracy"
            checked={getMode('timing', 'performance') !== 'off'}
            onChange={(on) => updateSpoofer('timing', 'performance', on ? 'noise' : 'off')}
          />

          {/* Screen spoofing dropdown */}
          <div className="row">
            <div>
              <div className="row-label">Spoof Screen Size</div>
              <div className="row-desc">Override screen dimensions</div>
            </div>
            <select className="select" style={{ width: '110px' }}
              value={getMode('hardware', 'screen')}
              onChange={(e) => updateSpoofer('hardware', 'screen', e.target.value)}>
              <option value="off">Don't spoof</option>
              <option value="noise">Profile</option>
              <option value="block">Fixed (1920x1080)</option>
            </select>
          </div>

          {/* Timezone spoofing dropdown */}
          <div className="row">
            <div>
              <div className="row-label">Spoof Timezone</div>
              <div className="row-desc">Override timezone detection</div>
            </div>
            <select className="select" style={{ width: '110px' }}
              value={getMode('timezone', 'intl')}
              onChange={(e) => updateSpoofer('timezone', 'intl', e.target.value)}>
              <option value="off">Don't spoof</option>
              <option value="noise">Profile</option>
              <option value="block">UTC</option>
            </select>
          </div>
        </div>
      )}

      {/* Standard Sub-tab */}
      {subTab === 'standard' && (
        <div className="card space-y-0">
          {/* WebRTC */}
          <div className="row">
            <div>
              <div className="row-label">WebRTC Policy</div>
              <div className="row-desc">Control IP leak via WebRTC</div>
            </div>
            <select className="select" style={{ width: '130px' }}
              value={getMode('network', 'webrtc')}
              onChange={(e) => updateSpoofer('network', 'webrtc', e.target.value)}>
              <option value="off">Allow all</option>
              <option value="public_only">Public only</option>
              <option value="block">Disable</option>
            </select>
          </div>

          <ToggleRow
            label="Spoof Navigator"
            desc="Override User-Agent, platform, vendor"
            checked={getMode('navigator', 'userAgent') !== 'off'}
            onChange={(on) => updateSpoofer('navigator', 'userAgent', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Hide Vendor Flavors"
            desc="Remove window.chrome, safari globals"
            checked={getMode('navigator', 'vendorFlavors') !== 'off'}
            onChange={(on) => updateSpoofer('navigator', 'vendorFlavors', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Spoof Feature Detection"
            desc="Hide webdriver flag, normalize features"
            checked={getMode('features', 'detection') !== 'off'}
            onChange={(on) => updateSpoofer('features', 'detection', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Block Geolocation"
            desc="Deny location access"
            checked={getMode('network', 'geolocation') !== 'off'}
            onChange={(on) => updateSpoofer('network', 'geolocation', on ? 'block' : 'off')}
          />
          <ToggleRow
            label="Block Battery API"
            desc="Hide battery status"
            checked={getMode('hardware', 'battery') !== 'off'}
            onChange={(on) => updateSpoofer('hardware', 'battery', on ? 'block' : 'off')}
          />
          <ToggleRow
            label="Block Sensor APIs"
            desc="Hide accelerometer, gyroscope"
            checked={getMode('hardware', 'sensors') !== 'off'}
            onChange={(on) => updateSpoofer('hardware', 'sensors', on ? 'block' : 'off')}
          />
          <ToggleRow
            label="Block Device APIs"
            desc="MIDI, Bluetooth, USB, Serial, HID"
            checked={getMode('devices', 'gamepad') !== 'off'}
            onChange={(on) => {
              const mode = on ? 'block' : 'off';
              const current = { ...settings.spoofers } as any;
              current.devices = { gamepad: mode, midi: mode, bluetooth: mode, usb: mode, serial: mode, hid: mode };
              onSaveSettings({ spoofers: current });
            }}
          />
          <ToggleRow
            label="Spoof Speech Voices"
            desc="Randomize available TTS voices"
            checked={getMode('speech', 'synthesis') !== 'off'}
            onChange={(on) => updateSpoofer('speech', 'synthesis', on ? 'noise' : 'off')}
          />

          {/* WebSocket policy */}
          <div className="row">
            <div>
              <div className="row-label">WebSockets</div>
              <div className="row-desc">Control WebSocket connections</div>
            </div>
            <select className="select" style={{ width: '130px' }}
              value={getMode('network', 'websocket')}
              onChange={(e) => updateSpoofer('network', 'websocket', e.target.value)}>
              <option value="off">Allow all</option>
              <option value="noise">Block 3rd party</option>
              <option value="block">Block all</option>
            </select>
          </div>
        </div>
      )}

      {/* Cookie Sub-tab */}
      {subTab === 'cookie' && (
        <div className="card space-y-0">
          <ToggleRow
            label="Spoof Storage Estimate"
            desc="Randomize reported disk quota"
            checked={getMode('storage', 'estimate') !== 'off'}
            onChange={(on) => updateSpoofer('storage', 'estimate', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Spoof IndexedDB"
            desc="Hide database enumeration"
            checked={getMode('storage', 'indexedDB') !== 'off'}
            onChange={(on) => updateSpoofer('storage', 'indexedDB', on ? 'noise' : 'off')}
          />
          <ToggleRow
            label="Block WebSQL"
            desc="Disable legacy database API"
            checked={getMode('storage', 'webSQL') !== 'off'}
            onChange={(on) => updateSpoofer('storage', 'webSQL', on ? 'block' : 'off')}
          />
          <ToggleRow
            label="Spoof Permissions"
            desc="Normalize permission states"
            checked={getMode('permissions', 'query') !== 'off'}
            onChange={(on) => updateSpoofer('permissions', 'query', on ? 'noise' : 'off')}
          />

          <div className="py-3" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="section-label">Cookie Policy</div>
            <div className="row-desc" style={{ marginBottom: '6px' }}>
              Managed via Firefox container settings
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', padding: '8px', borderRadius: '6px', background: 'var(--bg-elevated)' }}>
              Cookie isolation is handled per-container by Firefox Multi-Account Containers. Each container has its own cookie jar automatically.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* Reusable toggle row */
function ToggleRow({ label, desc, checked, onChange }: {
  label: string; desc?: string; checked: boolean; onChange: (on: boolean) => void;
}) {
  return (
    <div className="row">
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="row-label">{label}</div>
        {desc && <div className="row-desc">{desc}</div>}
      </div>
      <div className={`toggle ${checked ? 'on' : ''}`} onClick={() => onChange(!checked)} />
    </div>
  );
}
