/**
 * Signals Tab - Per-API fingerprint signal controls with value selectors.
 * Each signal has Off/Spoof/Block mode and optional value dropdown.
 */

import React, { useEffect, useState, useMemo } from 'react';
import browser from 'webextension-polyfill';
import type { ContainerSettings, FingerprintAccess } from '@/types';
import {
  CANVAS_NOISE_OPTIONS, AUDIO_NOISE_OPTIONS, TIMING_PRECISION_OPTIONS,
  BATTERY_OPTIONS, DOMRECT_NOISE_OPTIONS, FONT_LIST_OPTIONS,
  MEDIA_DEVICE_OPTIONS, TOUCH_OPTIONS, WEBGL_NOISE_OPTIONS,
  SVG_NOISE_OPTIONS, MATH_NOISE_OPTIONS, PLUGINS_OPTIONS, HISTORY_OPTIONS,
} from '@/popup/data/signal-options';
import { getSignalType, hasCore } from '@/popup/data/signal-types';

interface SignalsTabProps {
  settings: ContainerSettings;
  onSaveSettings: (updates: Partial<ContainerSettings>) => void;
  highlightedSignal?: { category: string; signal: string };
}

/**
 * Build a map of API name -> value from the fingerprint access log.
 * For APIs that appear multiple times, the most recent value wins.
 */
/** Quick hash for display — 8-char hex, like CreepJS */
function quickHash(str: string): string {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = ((h << 5) - h + str.charCodeAt(i)) | 0;
  return (h >>> 0).toString(16).padStart(8, '0');
}

/** Format a value for display — show hash for long/binary data, truncate for text */
function formatValue(val: string): string {
  if (!val) return '';
  // Data URLs → hash
  if (val.startsWith('data:')) return quickHash(val);
  // Long values → hash
  if (val.length > 30) return quickHash(val);
  return val;
}

function buildValueMap(apis: FingerprintAccess[]): Record<string, string> {
  const map: Record<string, string> = {};
  for (const a of apis) {
    if (a.value && a.spoofed) {
      map[a.api] = formatValue(a.value);
    }
  }
  return map;
}

export default function SignalsTab({ settings, onSaveSettings, highlightedSignal }: SignalsTabProps) {
  const [accessedAPIs, setAccessedAPIs] = useState<FingerprintAccess[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Try active tab first
        const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
        if (tab?.id) {
          const resp = await browser.runtime.sendMessage({ type: 'GET_RECOMMENDATIONS', tabId: tab.id }) as Record<string, unknown> | null;
          if (!cancelled && resp && Array.isArray(resp.accessedAPIs) && (resp.accessedAPIs as any[]).length > 0) {
            setAccessedAPIs(resp.accessedAPIs as FingerprintAccess[]);
            return;
          }
        }
        // Fallback: try all tabs in current window to find one with data
        const allTabs = await browser.tabs.query({ currentWindow: true });
        for (const t of allTabs) {
          if (!t.id || t.id === tab?.id) continue;
          const resp = await browser.runtime.sendMessage({ type: 'GET_RECOMMENDATIONS', tabId: t.id }) as Record<string, unknown> | null;
          if (!cancelled && resp && Array.isArray(resp.accessedAPIs) && (resp.accessedAPIs as any[]).length > 0) {
            setAccessedAPIs(resp.accessedAPIs as FingerprintAccess[]);
            return;
          }
        }
      } catch {}
    })();
    return () => { cancelled = true; };
  }, []);

  const vals = useMemo(() => buildValueMap(accessedAPIs), [accessedAPIs]);

  const get = (cat: string, key: string): string => (settings.spoofers as any)[cat]?.[key] || 'off';

  const set = (cat: string, key: string, mode: string) => {
    const spoofers = { ...settings.spoofers } as any;
    spoofers[cat] = { ...spoofers[cat], [key]: mode };
    onSaveSettings({ spoofers });
  };

  const hl = (cat: string, key: string) =>
    highlightedSignal?.category === cat && highlightedSignal?.signal === key;

  const S = (p: { name: string; cat: string; k: string; opts?: { id: string; name: string }[]; val?: string }) => (
    <SignalRow name={p.name} mode={get(p.cat, p.k)} onModeChange={(m) => set(p.cat, p.k, m)}
      highlighted={hl(p.cat, p.k)} valueOptions={p.opts} currentValue={p.val}
      signalType={getSignalType(p.cat, p.k)} isCore={hasCore(p.cat, p.k)} />
  );

  return (
    <div className="space-y-2">
      <G label="Graphics">
        <S name="Canvas" cat="graphics" k="canvas" opts={CANVAS_NOISE_OPTIONS} val={vals['HTMLCanvasElement.toDataURL']} />
        <S name="WebGL" cat="graphics" k="webgl" opts={WEBGL_NOISE_OPTIONS} val={vals['WebGLRenderingContext.getParameter']} />
        <S name="WebGL2" cat="graphics" k="webgl2" opts={WEBGL_NOISE_OPTIONS} val={vals['WebGL2RenderingContext.getParameter']} />
        <S name="DOMRect" cat="graphics" k="domRect" opts={DOMRECT_NOISE_OPTIONS} val={vals['Element.getBoundingClientRect']} />
        <S name="Text Metrics" cat="graphics" k="textMetrics" opts={DOMRECT_NOISE_OPTIONS} val={vals['CanvasRenderingContext2D.measureText']} />
        <S name="SVG" cat="graphics" k="svg" opts={SVG_NOISE_OPTIONS} val={vals['SVGGraphicsElement.getBBox']} />
        <S name="OffscreenCanvas" cat="graphics" k="offscreenCanvas" opts={CANVAS_NOISE_OPTIONS} val={vals['OffscreenCanvas.convertToBlob']} />
        <S name="WebGL Shaders" cat="graphics" k="webglShaders" />
        <S name="WebGPU" cat="graphics" k="webgpu" val={vals['navigator.gpu.requestAdapter']} />
        <S name="GPU" cat="hardware" k="gpu" />
      </G>
      <G label="Audio">
        <S name="AudioContext" cat="audio" k="audioContext" opts={AUDIO_NOISE_OPTIONS} val={vals['AnalyserNode.getFloatFrequencyData']} />
        <S name="Offline Audio" cat="audio" k="offlineAudio" opts={AUDIO_NOISE_OPTIONS} val={vals['OfflineAudioContext.startRendering']} />
        <S name="Audio Latency" cat="audio" k="latency" val={vals['AudioContext.baseLatency']} />
        <S name="Codecs" cat="audio" k="codecs" val={vals['HTMLMediaElement.canPlayType']} />
      </G>
      <G label="Hardware">
        <S name="Screen" cat="hardware" k="screen" val={vals['screen.width']} />
        <S name="Screen Frame" cat="hardware" k="screenFrame" val={vals['window.outerWidth']} />
        <S name="Screen Extended" cat="hardware" k="screenExtended" />
        <S name="Orientation" cat="hardware" k="orientation" val={vals['screen.orientation.type']} />
        <S name="Visual Viewport" cat="hardware" k="visualViewport" />
        <S name="Device Memory" cat="hardware" k="deviceMemory" val={vals['navigator.deviceMemory']} />
        <S name="CPU Cores" cat="hardware" k="hardwareConcurrency" val={vals['navigator.hardwareConcurrency']} />
        <S name="Architecture" cat="hardware" k="architecture" />
        <S name="Media Devices" cat="hardware" k="mediaDevices" opts={MEDIA_DEVICE_OPTIONS} val={vals['navigator.mediaDevices.enumerateDevices']} />
        <S name="Battery" cat="hardware" k="battery" opts={BATTERY_OPTIONS} val={vals['navigator.getBattery']} />
        <S name="Touch" cat="hardware" k="touch" opts={TOUCH_OPTIONS} val={vals['navigator.maxTouchPoints']} />
        <S name="Sensors" cat="hardware" k="sensors" val={vals['DeviceMotionEvent']} />
      </G>
      <G label="Navigator">
        <S name="User Agent" cat="navigator" k="userAgent" val={vals['navigator.userAgent']} />
        <S name="Languages" cat="navigator" k="languages" val={vals['navigator.languages']} />
        <S name="Plugins" cat="navigator" k="plugins" opts={PLUGINS_OPTIONS} />
        <S name="Client Hints" cat="navigator" k="clientHints" val={vals['navigator.userAgentData']} />
        <S name="Clipboard" cat="navigator" k="clipboard" val={vals['navigator.clipboard']} />
        <S name="Vibration" cat="navigator" k="vibration" val={vals['navigator.vibrate']} />
        <S name="Vendor Flavors" cat="navigator" k="vendorFlavors" />
        <S name="Font Preferences" cat="navigator" k="fontPreferences" />
        <S name="Window.name" cat="navigator" k="windowName" val={vals['window.name']} />
        <S name="Tab History" cat="navigator" k="tabHistory" opts={HISTORY_OPTIONS} val={vals['history.length']} />
        <S name="Media Capabilities" cat="navigator" k="mediaCapabilities" val={vals['navigator.mediaCapabilities.decodingInfo']} />
      </G>
      <G label="Network">
        <SignalRow name="WebRTC" mode={get('network', 'webrtc')}
          onModeChange={(m) => set('network', 'webrtc', m)}
          customModes={[{id:'off',name:'Off'},{id:'public_only',name:'Public Only'},{id:'block',name:'Block'}]} />
        <S name="Connection" cat="network" k="connection" val={vals['navigator.connection']} />
        <S name="Geolocation" cat="network" k="geolocation" val={vals['navigator.geolocation.getCurrentPosition']} />
        <SignalRow name="WebSocket" mode={get('network', 'websocket')}
          onModeChange={(m) => set('network', 'websocket', m)}
          customModes={[{id:'off',name:'Off'},{id:'noise',name:'3rd Party Only'},{id:'block',name:'Block All'}]} />
      </G>
      <G label="Timing & Timezone">
        <S name="Performance" cat="timing" k="performance" opts={TIMING_PRECISION_OPTIONS} val={vals['performance.now']} />
        <S name="Memory" cat="timing" k="memory" />
        <S name="Event Loop Jitter" cat="timing" k="eventLoop" val={vals['setTimeout']} />
        <S name="Timezone" cat="timezone" k="intl" val={vals['Intl.DateTimeFormat'] || vals['Date.getTimezoneOffset']} />
        <S name="Date" cat="timezone" k="date" val={vals['Date.getTimezoneOffset']} />
        <S name="Intl APIs" cat="intl" k="apis" val={vals['Intl.NumberFormat']} />
      </G>
      <G label="Fonts & Rendering">
        <S name="Font Enum" cat="fonts" k="enumeration" opts={FONT_LIST_OPTIONS} val={vals['document.fonts.check']} />
        <S name="CSS Fonts" cat="fonts" k="cssDetection" val={vals['getComputedStyle(fontFamily)']} />
        <S name="Emoji" cat="rendering" k="emoji" />
        <S name="MathML" cat="rendering" k="mathml" val={vals['MathML.getBoundingClientRect']} />
      </G>
      <G label="CSS">
        <S name="Media Queries" cat="css" k="mediaQueries" val={vals['matchMedia']} />
      </G>
      <G label="Storage">
        <S name="Storage Estimate" cat="storage" k="estimate" val={vals['navigator.storage.estimate']} />
        <S name="IndexedDB" cat="storage" k="indexedDB" val={vals['indexedDB.open']} />
        <S name="WebSQL" cat="storage" k="webSQL" val={vals['openDatabase']} />
        <S name="Private Mode" cat="storage" k="privateModeProtection" val={vals['navigator.storage.persisted']} />
      </G>
      <G label="Permissions">
        <S name="Permissions API" cat="permissions" k="query" val={vals['navigator.permissions.query']} />
        <S name="Notification" cat="permissions" k="notification" val={vals['Notification.permission']} />
      </G>
      <G label="Devices">
        <S name="Gamepad" cat="devices" k="gamepad" val={vals['navigator.getGamepads']} />
        <S name="MIDI" cat="devices" k="midi" val={vals['navigator.requestMIDIAccess']} />
        <S name="Bluetooth" cat="devices" k="bluetooth" val={vals['navigator.bluetooth.requestDevice']} />
        <S name="USB" cat="devices" k="usb" val={vals['navigator.usb.getDevices']} />
        <S name="Serial" cat="devices" k="serial" val={vals['navigator.serial.getPorts']} />
        <S name="HID" cat="devices" k="hid" val={vals['navigator.hid.getDevices']} />
      </G>
      <G label="Other">
        <S name="Math" cat="math" k="functions" opts={MATH_NOISE_OPTIONS} />
        <S name="Keyboard" cat="keyboard" k="layout" val={vals['navigator.keyboard.getLayoutMap']} />
        <S name="Key Cadence" cat="keyboard" k="cadence" val={vals['KeyboardEvent.timing']} />
        <S name="Speech" cat="speech" k="synthesis" val={vals['speechSynthesis.getVoices']} />
        <S name="Features" cat="features" k="detection" val={vals['navigator.webdriver']} />
        <S name="Crypto" cat="crypto" k="webCrypto" val={vals['crypto.getRandomValues']} />
        <S name="Errors" cat="errors" k="stackTrace" val={vals['Error.captureStackTrace']} />
        <S name="Apple Pay" cat="payment" k="applePay" val={vals['ApplePaySession.canMakePayments']} />
        <S name="Workers" cat="workers" k="fingerprint" val={vals['Worker.constructor']} />
        <S name="Service Workers" cat="workers" k="serviceWorker" val={vals['ServiceWorker.register']} />
        <div style={{ padding: '2px 8px', fontSize: '10px', color: 'var(--text-muted)', lineHeight: 1.4 }}>
          Spoof/Block: blocks SW registration — sites fall back to SharedWorker/DedicatedWorker which are fully spoofed. Firefox does not allow injecting into ServiceWorker scripts. Off: no interception (real values may leak).
        </div>
      </G>
    </div>
  );
}

function G({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <div className="section-label">{label}</div>
      <div>{children}</div>
    </div>
  );
}

function SignalRow({ name, mode, onModeChange, highlighted, valueOptions, customModes, currentValue, signalType, isCore }: {
  name: string; mode: string; onModeChange: (m: string) => void;
  highlighted?: boolean; valueOptions?: { id: string; name: string }[];
  customModes?: { id: string; name: string }[];
  currentValue?: string;
  signalType?: 'core' | 'js';
  isCore?: boolean;
}) {
  const isOn = mode !== 'off';
  const modes = customModes || [
    { id: 'off', name: 'Off' },
    { id: 'noise', name: 'Spoof' },
    { id: 'block', name: 'Block' },
  ];
  const modeClass = (m: string) => {
    if (m !== mode) return 'off';
    if (m === 'off') return 'off-active';
    if (m === 'block') return 'block';
    return 'noise';
  };

  const typeLabel = signalType === 'core' ? 'Core' : 'JS';
  const typeColor = signalType === 'core' ? 'var(--green)' : 'var(--blue)';
  const typeBg = signalType === 'core' ? 'var(--green-muted)' : 'var(--blue-muted)';

  return (
    <div style={{
      borderBottom: '1px solid var(--border)', padding: '6px 0',
      background: highlighted ? 'var(--accent-muted)' : 'transparent',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ minWidth: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text)' }}>{name}</span>
          {isOn && (
            <span style={{
              fontSize: '8px', fontWeight: 600, padding: '1px 5px', borderRadius: '3px',
              color: typeColor, background: typeBg, letterSpacing: '0.02em',
            }}>{typeLabel}</span>
          )}
          {currentValue && isOn && (
            <div style={{ fontSize: '9px', color: 'var(--accent)', marginTop: '1px' }} className="truncate">{currentValue}</div>
          )}
        </div>
        <div style={{ display: 'flex', gap: '2px' }}>
          {modes.map((m) => (
            <button key={m.id} onClick={() => onModeChange(m.id)}
              className={`pill ${modeClass(m.id)}`} style={{ fontSize: '10px', padding: '2px 7px' }}>
              {m.name}
            </button>
          ))}
        </div>
      </div>
      {isOn && mode !== 'block' && valueOptions && (
        <div style={{ marginTop: '4px', display: 'flex', gap: '4px' }}>
          <select className="select" style={{ fontSize: '10px', padding: '3px 6px', flex: 1 }}>
            {valueOptions.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
          <input className="input" type="number" min="0" placeholder="#"
            style={{ width: '50px', fontSize: '10px', padding: '3px 6px', textAlign: 'center' }} />
        </div>
      )}
    </div>
  );
}
