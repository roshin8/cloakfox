/**
 * Profile Tab - Browser identity configuration.
 * User agent, screen size, language, timezone, hardware selection.
 */

import React, { useState, useMemo, useEffect } from 'react';
import browser from 'webextension-polyfill';
import type { ContainerSettings } from '@/types';
import { ALL_PROFILES, PROFILES_BY_OS, PROFILES_BY_BROWSER, getRandomProfile } from '@/lib/profiles/user-agents';
import { SCREENS_BY_CATEGORY, getScreenForUserAgent } from '@/lib/profiles/screen-sizes';
import {
  LANGUAGE_OPTIONS, TIMEZONE_OPTIONS, CPU_CORES, DEVICE_MEMORY,
  GPU_OPTIONS, OS_FILTERS, BROWSER_FILTERS,
} from '@/popup/data/signal-options';

interface FingerprintTabProps {
  settings: ContainerSettings;
  onSaveSettings: (updates: Partial<ContainerSettings>) => void;
  assignedProfile?: {
    userAgent?: { id?: string; name?: string; userAgent?: string; platform?: string; platformName?: string };
    screen?: { width: number; height: number; colorDepth?: number; devicePixelRatio?: number };
    hardwareConcurrency?: number;
    deviceMemory?: number;
    languages?: string[];
    timezoneOffset?: number;
  };
}

export default function FingerprintTab({ settings, onSaveSettings, assignedProfile }: FingerprintTabProps) {
  const [uaSearch, setUaSearch] = useState('');
  const [osFilter, setOsFilter] = useState('all');
  const [browserFilter, setBrowserFilter] = useState('all');
  const [rotation, setRotation] = useState<any>(null);

  useEffect(() => {
    browser.runtime.sendMessage({ type: 'GET_ROTATION_SETTINGS' })
      .then(r => setRotation(r)).catch(() => {});
  }, []);

  const updateRotation = async (updates: any) => {
    try {
      await browser.runtime.sendMessage({ type: 'SET_ROTATION_SETTINGS', settings: updates });
      const r = await browser.runtime.sendMessage({ type: 'GET_ROTATION_SETTINGS' });
      setRotation(r);
    } catch {}
  };

  const rotateNow = async () => {
    try {
      await browser.runtime.sendMessage({ type: 'ROTATE_NOW' });
      // Reload profile after rotation
      onSaveSettings({});
    } catch {}
  };

  const filteredProfiles = useMemo(() => {
    let list = ALL_PROFILES;

    // Filter by OS
    if (osFilter !== 'all') {
      list = (PROFILES_BY_OS as any)[osFilter] || list;
    }

    // Filter by browser
    if (browserFilter !== 'all') {
      const browserList = (PROFILES_BY_BROWSER as any)[browserFilter];
      if (browserList) {
        list = list.filter((p: any) => browserList.includes(p));
      }
    }

    // Filter by search
    if (uaSearch) {
      const q = uaSearch.toLowerCase();
      list = list.filter((p: any) => p.name.toLowerCase().includes(q) || p.userAgent.toLowerCase().includes(q));
    }
    return list.slice(0, 60);
  }, [osFilter, browserFilter, uaSearch]);

  const updateProfile = (updates: Partial<ContainerSettings['profile']>) => {
    onSaveSettings({ profile: { ...settings.profile, ...updates } });
  };

  const randomizeAll = () => {
    const pick = <T,>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];
    const randInt = (min: number, max: number) => Math.floor(Math.random() * (max - min + 1)) + min;
    const simplePrng = { nextInt: randInt, nextFloat: () => Math.random() };

    const ua = getRandomProfile(simplePrng);
    const screen = getScreenForUserAgent(simplePrng, ua.mobile, ua.platformName);

    const languages = ['en-US', 'en-GB', 'de-DE', 'fr-FR', 'es-ES', 'ja-JP', 'zh-CN', 'ko-KR', 'pt-BR', 'ru-RU'];
    const timezones = ['-480', '-420', '-360', '-300', '0', '60', '120', '-540', '480'];
    const cores = [4, 6, 8, 12, 16];
    const memory = [4, 8, 16];

    onSaveSettings({
      profile: {
        mode: 'preset',
        userAgent: ua.userAgent,
        platform: ua.platform,
        language: pick(languages),
        timezone: pick(timezones),
        screen: { width: screen.width, height: screen.height },
        hardwareConcurrency: pick(cores),
        deviceMemory: pick(memory),
        gpu: undefined,
      },
    });
  };

  return (
    <div className="space-y-3">
      {/* Randomize + current summary */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: settings.profile?.userAgent ? '8px' : 0 }}>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 600 }}>Browser Identity</div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
              {settings.profile?.mode === 'preset' ? 'Custom profile' : 'Random on each session'}
            </div>
          </div>
          <button className="btn btn-primary" onClick={randomizeAll}>
            Randomize
          </button>
        </div>
        {settings.profile?.userAgent && (
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', padding: '6px 8px', background: 'var(--bg-elevated)', borderRadius: '4px', lineHeight: '1.6' }}>
            <div><b style={{color:'var(--text-secondary)'}}>UA:</b> {settings.profile.userAgent.substring(0, 70)}...</div>
            <div><b style={{color:'var(--text-secondary)'}}>Platform:</b> {settings.profile.platform} | <b style={{color:'var(--text-secondary)'}}>Screen:</b> {settings.profile.screen ? `${settings.profile.screen.width}x${settings.profile.screen.height}` : 'Auto'} | <b style={{color:'var(--text-secondary)'}}>Lang:</b> {settings.profile.language || 'Auto'}</div>
            <div><b style={{color:'var(--text-secondary)'}}>CPU:</b> {settings.profile.hardwareConcurrency || 'Auto'} | <b style={{color:'var(--text-secondary)'}}>RAM:</b> {settings.profile.deviceMemory ? settings.profile.deviceMemory + 'GB' : 'Auto'} | <b style={{color:'var(--text-secondary)'}}>TZ:</b> {settings.profile.timezone || 'Auto'}</div>
          </div>
        )}
      </div>

      {/* Profile Rotation */}
      <div className="card">
        <div className="section-label">Auto-Rotation</div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Rotate fingerprint automatically
          </div>
          <div className={`toggle ${rotation?.enabled ? 'on' : ''}`}
            onClick={() => updateRotation({ enabled: !rotation?.enabled })} />
        </div>
        {rotation?.enabled && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <select className="select" style={{ flex: 1 }}
              value={rotation?.schedule || 'daily'}
              onChange={(e) => updateRotation({ schedule: e.target.value })}>
              <option value="session">Every session</option>
              <option value="hourly">Every hour</option>
              <option value="daily">Every day</option>
              <option value="weekly">Every week</option>
            </select>
            <button className="btn btn-secondary" onClick={rotateNow}
              style={{ whiteSpace: 'nowrap' }}>Rotate Now</button>
          </div>
        )}
      </div>

      {/* User Agent */}
      <div className="card">
        <div className="section-label">User Agent ({filteredProfiles.length})</div>
        {/* OS filter */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px', marginBottom: '4px' }}>
          {OS_FILTERS.map((os) => (
            <button key={os} onClick={() => { setOsFilter(os); setBrowserFilter('all'); }}
              className={`pill ${osFilter === os ? 'active-accent' : 'off'}`}
              style={{ fontSize: '9px', padding: '2px 6px' }}>
              {os === 'all' ? 'All OS' : os.charAt(0).toUpperCase() + os.slice(1)}
            </button>
          ))}
        </div>
        {/* Browser filter */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px', marginBottom: '8px' }}>
          {BROWSER_FILTERS.map((br) => (
            <button key={br} onClick={() => { setBrowserFilter(br); setOsFilter('all'); }}
              className={`pill ${browserFilter === br ? 'active-accent' : 'off'}`}
              style={{ fontSize: '9px', padding: '2px 6px' }}>
              {br === 'all' ? 'All Browsers' : br.charAt(0).toUpperCase() + br.slice(1)}
            </button>
          ))}
        </div>
        <input className="input" placeholder="Search browsers..."
          value={uaSearch} onChange={(e) => setUaSearch(e.target.value)}
          style={{ marginBottom: '8px' }} />
        <div style={{ maxHeight: '160px', overflowY: 'auto' }}>
          {filteredProfiles.map((p: any) => {
            const active = settings.profile?.userAgent === p.userAgent && settings.profile?.platform === p.platform;
            return (
              <button key={p.id} onClick={() => updateProfile({
                mode: 'preset', userAgent: p.userAgent, platform: p.platform,
              })}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  width: '100%', textAlign: 'left', padding: '6px 8px', borderRadius: '4px',
                  background: active ? 'var(--accent-muted)' : 'transparent',
                  border: active ? '1px solid var(--accent-border)' : '1px solid transparent',
                  fontSize: '11px', cursor: 'pointer', color: 'var(--text)',
                  marginBottom: '2px',
                }}
                onMouseEnter={(e) => { if (!active) (e.target as HTMLElement).style.background = 'var(--bg-hover)'; }}
                onMouseLeave={(e) => { if (!active) (e.target as HTMLElement).style.background = 'transparent'; }}>
                <span className="truncate">{p.name}</span>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)', flexShrink: 0, marginLeft: '8px' }}>{p.platformName}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Screen Size */}
      <div className="card">
        <div className="section-label">Screen Size</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          {Object.entries(SCREENS_BY_CATEGORY).map(([cat, screens]) => (
            <div key={cat}>
              <div style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '3px' }}>{cat}</div>
              <select className="select" value={
                settings.profile?.screen ? `${settings.profile.screen.width}x${settings.profile.screen.height}`
                : assignedProfile?.screen ? `${assignedProfile.screen.width}x${assignedProfile.screen.height}`
                : ''
              } onChange={(e) => {
                if (!e.target.value) { updateProfile({ screen: undefined }); return; }
                const [w, h] = e.target.value.split('x').map(Number);
                if (w && h) updateProfile({ screen: { width: w, height: h } });
              }}>
                <option value="">{assignedProfile?.screen ? `${assignedProfile.screen.width}x${assignedProfile.screen.height} (current)` : 'Random'}</option>
                {(screens as any[]).map((s: any) => (
                  <option key={s.id} value={`${s.width}x${s.height}`}>{s.width}x{s.height}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
        {/* Custom size */}
        <div style={{ marginTop: '8px' }}>
          <div style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '3px' }}>Custom</div>
          <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
            <input className="input" type="number" placeholder="Width"
              style={{ flex: 1, fontSize: '11px' }}
              value={settings.profile?.screen?.width || ''}
              onChange={(e) => {
                const w = Number(e.target.value);
                const h = settings.profile?.screen?.height || 768;
                if (w > 0) updateProfile({ screen: { width: w, height: h } });
              }} />
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>x</span>
            <input className="input" type="number" placeholder="Height"
              style={{ flex: 1, fontSize: '11px' }}
              value={settings.profile?.screen?.height || ''}
              onChange={(e) => {
                const h = Number(e.target.value);
                const w = settings.profile?.screen?.width || 1920;
                if (h > 0) updateProfile({ screen: { width: w, height: h } });
              }} />
          </div>
        </div>
        {assignedProfile?.screen && (
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '8px', padding: '6px 8px', background: 'var(--bg-elevated)', borderRadius: '4px' }}>
            Current: {assignedProfile.screen.width}x{assignedProfile.screen.height}, {assignedProfile.screen.colorDepth || 24}bit, {assignedProfile.screen.devicePixelRatio || 1}x DPR
          </div>
        )}
      </div>

      {/* Language & Timezone */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        <div className="card">
          <div className="section-label">Language</div>
          <select className="select" value={settings.profile?.language || ''}
            onChange={(e) => updateProfile({ language: e.target.value || undefined })}>
            <option value="">{assignedProfile?.languages?.[0] ? `${assignedProfile.languages[0]} (current)` : 'Random'}</option>
            {LANGUAGE_OPTIONS.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </div>
        <div className="card">
          <div className="section-label">Timezone</div>
          <select className="select" value={settings.profile?.timezone || ''}
            onChange={(e) => updateProfile({ timezone: e.target.value || undefined })}>
            <option value="">{assignedProfile?.timezoneOffset !== undefined ? `UTC${assignedProfile.timezoneOffset >= 0 ? '+' : ''}${assignedProfile.timezoneOffset / 60} (current)` : 'Random'}</option>
            <option value="real">Real timezone</option>
            {TIMEZONE_OPTIONS.map((t) => <option key={t.id} value={String(t.offset)}>{t.name}</option>)}
          </select>
        </div>
      </div>

      {/* Hardware */}
      <div className="card">
        <div className="section-label">Hardware</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '3px' }}>CPU Cores</div>
            <select className="select" value={settings.profile?.hardwareConcurrency || ''}
              onChange={(e) => updateProfile({ hardwareConcurrency: Number(e.target.value) || undefined })}>
              <option value="">{assignedProfile?.hardwareConcurrency ? `${assignedProfile.hardwareConcurrency} (current)` : 'Random'}</option>
              {CPU_CORES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '3px' }}>Memory (GB)</div>
            <select className="select" value={settings.profile?.deviceMemory || ''}
              onChange={(e) => updateProfile({ deviceMemory: Number(e.target.value) || undefined })}>
              <option value="">{assignedProfile?.deviceMemory ? `${assignedProfile.deviceMemory}GB (current)` : 'Random'}</option>
              {DEVICE_MEMORY.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '3px' }}>GPU</div>
            <select className="select" value={settings.profile?.gpu?.renderer || ''}
              onChange={(e) => {
                const gpu = GPU_OPTIONS.find((g) => g.renderer === e.target.value);
                updateProfile(gpu ? { gpu: { vendor: gpu.vendor, renderer: gpu.renderer } } : { gpu: undefined });
              }}>
              <option value="">Random</option>
              {GPU_OPTIONS.map((g) => <option key={g.id} value={g.renderer}>{g.id}</option>)}
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}
