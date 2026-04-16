/**
 * Headers Tab - HTTP header spoofing controls
 */

import React from 'react';
import type { ContainerSettings, RefererPolicy, XForwardedForMode } from '@/types';

interface HeadersTabProps {
  settings: ContainerSettings;
  onSaveSettings: (updates: Partial<ContainerSettings>) => void;
}

export default function HeadersTab({ settings, onSaveSettings }: HeadersTabProps) {
  const h = settings.headers;
  const update = (key: string, value: any) => {
    onSaveSettings({ headers: { ...h, [key]: value } });
  };

  return (
    <div className="space-y-3">
      {/* Request Headers */}
      <div className="card space-y-0">
        <div className="section-label" style={{ padding: '0 0 4px' }}>Request Headers</div>
        <ToggleRow label="Spoof User-Agent Header" desc="Match HTTP header to spoofed profile"
          checked={h.spoofUserAgent} onChange={(on) => update('spoofUserAgent', on)} />
        <ToggleRow label="Spoof Accept-Language" desc="Match language header to profile"
          checked={h.spoofAcceptLanguage} onChange={(on) => update('spoofAcceptLanguage', on)} />
        <ToggleRow label="Send Do Not Track" desc="Include DNT: 1 header"
          checked={h.sendDNT} onChange={(on) => update('sendDNT', on)} />
        <ToggleRow label="Disable ETag Tracking" desc="Strip If-None-Match for cache tracking"
          checked={h.disableEtag} onChange={(on) => update('disableEtag', on)} />
      </div>

      {/* Proxy Headers */}
      <div className="card space-y-0">
        <div className="section-label" style={{ padding: '0 0 4px' }}>Proxy Headers</div>
        <ToggleRow label="Spoof X-Forwarded-For" desc="Add fake proxy IP header"
          checked={h.spoofXForwardedFor} onChange={(on) => update('spoofXForwardedFor', on)} />

        {h.spoofXForwardedFor && (
          <div style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '4px' }}>IP Mode</div>
            <div className="flex gap-1 mb-2">
              {(['random', 'custom', 'range'] as XForwardedForMode[]).map((mode) => (
                <button key={mode} onClick={() => update('xForwardedForMode', mode)}
                  className={`pill ${h.xForwardedForMode === mode ? 'active-accent' : 'off'}`}>
                  {mode.charAt(0).toUpperCase() + mode.slice(1)}
                </button>
              ))}
            </div>
            {h.xForwardedForMode !== 'random' && (
              <input className="input" style={{ fontSize: '11px' }}
                placeholder={h.xForwardedForMode === 'custom' ? '203.0.113.42' : '198.51.100.1-198.51.100.254'}
                value={h.xForwardedForValue || ''}
                onChange={(e) => update('xForwardedForValue', e.target.value)} />
            )}
          </div>
        )}

        <ToggleRow label="Spoof Via Header" desc="Add fake proxy hop header"
          checked={h.spoofVia} onChange={(on) => update('spoofVia', on)} />
      </div>

      {/* Referer */}
      <div className="card space-y-0">
        <div className="section-label" style={{ padding: '0 0 4px' }}>Referer Policy</div>
        <div className="row">
          <div>
            <div className="row-label">Referer Header</div>
            <div className="row-desc">Control what referrer is sent</div>
          </div>
          <select className="select" style={{ width: '130px' }}
            value={h.refererPolicy}
            onChange={(e) => update('refererPolicy', e.target.value as RefererPolicy)}>
            <option value="off">Don't modify</option>
            <option value="origin">Origin only</option>
            <option value="same-origin">Same-origin only</option>
          </select>
        </div>
      </div>

      <div className="card">
        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
          Header modifications are applied via the webRequest API before requests are sent. Changes take effect on next page load.
        </div>
      </div>
    </div>
  );
}

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
