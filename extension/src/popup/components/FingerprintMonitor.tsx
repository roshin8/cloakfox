import React, { useEffect, useState } from 'react';
import browser from 'webextension-polyfill';
import { MSG_GET_RECOMMENDATIONS, POPUP_REFRESH_INTERVAL_MS } from '@/constants';

interface FingerprintAccess {
  api: string; category: string; timestamp: number; blocked: boolean; spoofed: boolean;
}

interface Recommendation {
  api: string; category: string; settingPath: string; currentValue: string;
}

interface FingerprintData {
  recommendations: Recommendation[];
  accessedCategories: string[];
  accessedAPIs: FingerprintAccess[];
  totalAccesses: number;
  url: string;
}

interface Props {
  onEnableSpoofer?: (settingPath: string) => void;
  onNavigateToSignal?: (category: string, signal: string) => void;
}

const CATEGORY_TO_SIGNAL: Record<string, { category: string; signal: string }> = {
  'Canvas': { category: 'graphics', signal: 'canvas' },
  'WebGL': { category: 'graphics', signal: 'webgl' },
  'DOMRect': { category: 'graphics', signal: 'domRect' },
  'Audio': { category: 'audio', signal: 'audioContext' },
  'Screen': { category: 'hardware', signal: 'screen' },
  'Hardware': { category: 'hardware', signal: 'deviceMemory' },
  'Navigator': { category: 'navigator', signal: 'userAgent' },
  'Timezone': { category: 'timezone', signal: 'intl' },
  'Fonts': { category: 'fonts', signal: 'enumeration' },
  'WebRTC': { category: 'network', signal: 'webrtc' },
  'Timing': { category: 'timing', signal: 'performance' },
  'Math': { category: 'math', signal: 'functions' },
  'Features': { category: 'features', signal: 'detection' },
};

export default function FingerprintMonitor({ onEnableSpoofer, onNavigateToSignal }: Props) {
  const [data, setData] = useState<FingerprintData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [viewMode, setViewMode] = useState<'apis' | 'categories'>('categories');

  useEffect(() => {
    async function loadData() {
      try {
        const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
        if (!tab?.id) return;
        const result = await browser.runtime.sendMessage({
          type: MSG_GET_RECOMMENDATIONS, tabId: tab.id,
        }) as FingerprintData;
        setData(result);
      } catch {} finally { setLoading(false); }
    }
    loadData();
    const interval = setInterval(loadData, POPUP_REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div style={{ fontSize: '12px', color: 'var(--text-muted)', padding: '8px 0' }}>Loading...</div>;
  }

  if (!data || data.totalAccesses === 0) {
    return (
      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
        <div style={{ fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '2px' }}>Fingerprint Monitor</div>
        <div>No fingerprinting detected. Reload the page to scan.</div>
      </div>
    );
  }

  const apisByCategory = (data.accessedAPIs || []).reduce((acc, api) => {
    if (!acc[api.category]) acc[api.category] = [];
    if (!acc[api.category].some(a => a.api === api.api)) acc[api.category].push(api);
    return acc;
  }, {} as Record<string, FingerprintAccess[]>);

  const uniqueAPIs = Object.values(apisByCategory).flat();
  const protectedCount = uniqueAPIs.filter(a => a.spoofed || a.blocked).length;
  const exposedCount = uniqueAPIs.filter(a => !a.spoofed && !a.blocked).length;

  const statusColor = (api: FingerprintAccess) =>
    api.blocked ? 'var(--red)' : api.spoofed ? 'var(--green)' : 'var(--yellow)';
  const statusBg = (api: FingerprintAccess) =>
    api.blocked ? 'var(--red-muted)' : api.spoofed ? 'var(--green-muted)' : 'var(--yellow-muted)';
  const statusLabel = (api: FingerprintAccess) =>
    api.blocked ? 'Blocked' : api.spoofed ? 'Spoofed' : 'Exposed';

  return (
    <div>
      {/* Header - clickable to expand */}
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between"
        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--text)' }}>
        <div>
          <div style={{ fontSize: '12px', fontWeight: 500 }}>Fingerprint Monitor</div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '1px' }}>
            {uniqueAPIs.length} APIs
            <span style={{ color: 'var(--green)', marginLeft: '6px' }}>{protectedCount} protected</span>
            {exposedCount > 0 && <span style={{ color: 'var(--yellow)', marginLeft: '6px' }}>{exposedCount} exposed</span>}
          </div>
        </div>
        <svg className={`w-3.5 h-3.5 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}
          style={{ color: 'var(--text-muted)' }}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div style={{ marginTop: '8px' }}>
          {/* View toggle */}
          <div className="flex gap-1 p-0.5 rounded-md mb-2" style={{ background: 'var(--bg-elevated)' }}>
            {(['categories', 'apis'] as const).map((mode) => (
              <button key={mode} onClick={() => setViewMode(mode)}
                className={`subtab flex-1 text-center ${viewMode === mode ? 'active' : ''}`}
                style={{ fontSize: '10px', padding: '2px 0' }}>
                {mode === 'categories' ? 'Categories' : 'All APIs'}
              </button>
            ))}
          </div>

          <div style={{ maxHeight: '220px', overflowY: 'auto' }}>
            {viewMode === 'categories' ? (
              <div className="space-y-1">
                {Object.entries(apisByCategory).map(([category, apis]) => {
                  const allProtected = apis.every(a => a.spoofed || a.blocked);
                  const sig = CATEGORY_TO_SIGNAL[category];
                  return (
                    <button key={category} className="w-full flex items-center justify-between p-1.5 rounded-md"
                      style={{ background: 'var(--bg-elevated)', border: 'none', cursor: 'pointer', color: 'var(--text)' }}
                      onClick={() => sig && onNavigateToSignal?.(sig.category, sig.signal)}>
                      <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full" style={{ background: allProtected ? 'var(--green)' : 'var(--yellow)' }} />
                        <span style={{ fontSize: '11px', fontWeight: 500 }}>{category}</span>
                        <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>({apis.length})</span>
                      </div>
                      <span className="pill" style={{
                        fontSize: '9px', padding: '1px 6px',
                        color: allProtected ? 'var(--green)' : 'var(--yellow)',
                        background: allProtected ? 'var(--green-muted)' : 'var(--yellow-muted)',
                      }}>
                        {allProtected ? 'Protected' : 'Exposed'}
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="space-y-0.5">
                {uniqueAPIs.map((api, idx) => (
                  <div key={idx} className="flex items-center justify-between p-1.5 rounded"
                    style={{ background: 'var(--bg-elevated)' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '10px', fontFamily: 'monospace', color: 'var(--text)' }} className="truncate">{api.api}</div>
                      <div style={{ fontSize: '9px', color: 'var(--text-muted)' }}>{api.category}</div>
                    </div>
                    <span style={{
                      fontSize: '9px', padding: '1px 6px', borderRadius: '3px', marginLeft: '4px',
                      color: statusColor(api), background: statusBg(api),
                    }}>
                      {statusLabel(api)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Legend */}
          <div className="flex items-center justify-center gap-4 pt-2 mt-2"
            style={{ borderTop: '1px solid var(--border)', fontSize: '9px', color: 'var(--text-muted)' }}>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--green)' }} /> Spoofed
            </span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--red)' }} /> Blocked
            </span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--yellow)' }} /> Exposed
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
