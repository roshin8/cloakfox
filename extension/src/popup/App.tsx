import React, { useEffect, useState } from 'react';

type TabId = 'dashboard' | 'fingerprint' | 'signals' | 'headers' | 'whitelist' | 'settings';

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Home', icon: '⌂' },
  { id: 'fingerprint', label: 'Profile', icon: '👤' },
  { id: 'signals', label: 'Signals', icon: '📡' },
  { id: 'headers', label: 'Headers', icon: '⟨/⟩' },
  { id: 'whitelist', label: 'Rules', icon: '✓' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
];

interface ContainerInfo {
  name: string;
  color: string;
  cookieStoreId: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('dashboard');
  const [isDark, setIsDark] = useState(true);
  const [engineActive, setEngineActive] = useState(false);
  const [container, setContainer] = useState<ContainerInfo | null>(null);
  const [domain, setDomain] = useState('');
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem('cloakfox-theme');
    if (saved === 'light') { setIsDark(false); document.documentElement.setAttribute('data-theme', 'light'); }

    // Get current tab info
    browser.tabs.query({ active: true, currentWindow: true }).then(async (tabs) => {
      const tab = tabs[0];
      if (!tab?.id || !tab.url) return;

      try { setDomain(new URL(tab.url).hostname); } catch {}

      // Get container info
      if (tab.cookieStoreId && tab.cookieStoreId !== 'firefox-default') {
        try {
          const ctx = await browser.contextualIdentities.get(tab.cookieStoreId);
          setContainer({ name: ctx.name, color: ctx.color, cookieStoreId: tab.cookieStoreId });
        } catch {}
      }

      // Check C++ engine
      try {
        const results = await browser.scripting.executeScript({
          target: { tabId: tab.id },
          world: 'MAIN' as never,
          func: () => typeof (window as Record<string, unknown>).setCanvasSeed === 'function',
        });
        setEngineActive(results[0]?.result === true);
      } catch { setEngineActive(false); }
    });
  }, []);

  const toggleTheme = () => {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.setAttribute('data-theme', next ? 'dark' : 'light');
    localStorage.setItem('cloakfox-theme', next ? 'dark' : 'light');
  };

  return (
    <>
      {/* Sidebar navigation */}
      <nav className="tab-nav">
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
              title={tab.label}
            >
              <span style={{ fontSize: 15 }}>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
        <button className="tab-btn" onClick={toggleTheme} title={isDark ? 'Light mode' : 'Dark mode'}>
          <span style={{ fontSize: 15 }}>{isDark ? '☀' : '☾'}</span>
          <span>Theme</span>
        </button>
      </nav>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Header */}
        <header style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700 }}>Cloakfox Shield</div>
              <div style={{ fontSize: 11, marginTop: 2, display: 'flex', alignItems: 'center' }}>
                <span className={`status-dot ${engineActive ? 'green' : 'red'}`} />
                <span style={{ color: engineActive ? 'var(--green)' : 'var(--red)' }}>
                  {engineActive ? 'C++ Engine Active' : 'Engine: Page not spoofed'}
                </span>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {container && (
                <span className="pill active" style={{ fontSize: 10 }}>
                  {container.name}
                </span>
              )}
              <div
                className={`toggle ${enabled ? 'on' : ''}`}
                onClick={() => setEnabled(!enabled)}
                title={enabled ? 'Disable protection' : 'Enable protection'}
              />
            </div>
          </div>
          {domain && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              {domain}
            </div>
          )}
        </header>

        {/* Content */}
        <main style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
          {activeTab === 'dashboard' && <DashboardTab container={container} />}
          {activeTab === 'fingerprint' && <FingerprintTab />}
          {activeTab === 'signals' && <SignalsTab />}
          {activeTab === 'headers' && <HeadersTab />}
          {activeTab === 'whitelist' && <RulesTab />}
          {activeTab === 'settings' && <SettingsTab />}
        </main>

        {/* Footer */}
        <footer style={{
          padding: '6px 14px',
          borderTop: '1px solid var(--border)',
          fontSize: 10,
          color: 'var(--text-muted)',
          display: 'flex',
          justifyContent: 'space-between',
        }}>
          <span>{container ? container.name : 'Default'}</span>
          <span>v0.1.0</span>
        </footer>
      </div>
    </>
  );
}

/* ─── DASHBOARD TAB ─────────────────────────────────────────────── */

function DashboardTab({ container }: { container: ContainerInfo | null }) {
  const protections = [
    { name: 'Canvas', status: 'noise' as const },
    { name: 'Audio', status: 'noise' as const },
    { name: 'Navigator', status: 'spoof' as const },
    { name: 'Screen', status: 'spoof' as const },
    { name: 'Fonts', status: 'filter' as const },
    { name: 'WebGL', status: 'noise' as const },
    { name: 'WebRTC', status: 'spoof' as const },
    { name: 'Timezone', status: 'spoof' as const },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Protection status */}
      <div className="card">
        <div className="section-label">Protection Status</div>
        {protections.map((p) => (
          <div key={p.name} className="row">
            <span style={{ fontSize: 12 }}>{p.name}</span>
            <span className={`pill ${p.status === 'noise' ? 'green' : 'active'}`}>
              {p.status === 'noise' ? 'Noise' : p.status === 'spoof' ? 'Spoofed' : 'Filtered'}
            </span>
          </div>
        ))}
      </div>

      {/* Stats */}
      <div className="grid-3">
        <div className="stat">
          <div className="stat-value" style={{ color: 'var(--green)' }}>8</div>
          <div className="stat-label">Protected</div>
        </div>
        <div className="stat">
          <div className="stat-value" style={{ color: 'var(--yellow)' }}>0</div>
          <div className="stat-label">Blocked</div>
        </div>
        <div className="stat">
          <div className="stat-value" style={{ color: 'var(--blue)' }}>0</div>
          <div className="stat-label">Accesses</div>
        </div>
      </div>

      {/* Container info */}
      <div className="card">
        <div className="section-label">Container Identity</div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
          {container ? (
            <>
              <div className="row">
                <span>Container</span>
                <span style={{ color: 'var(--accent)', fontWeight: 500 }}>{container.name}</span>
              </div>
              <div className="row">
                <span>Isolation</span>
                <span className="pill green">Per-domain</span>
              </div>
            </>
          ) : (
            <div style={{ padding: '8px 0', color: 'var(--text-muted)' }}>
              Default container — open a Container Tab for per-identity isolation
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── FINGERPRINT TAB ───────────────────────────────────────────── */

function FingerprintTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div className="card">
        <div className="section-label">Active Profile</div>
        <div className="grid-2">
          {[
            ['Platform', 'MacIntel'],
            ['Screen', '1920×1080'],
            ['Cores', '8'],
            ['Memory', '8 GB'],
            ['Timezone', 'America/New_York'],
            ['Language', 'en-US'],
            ['WebGL', 'Apple M1'],
            ['Color Depth', '24-bit'],
          ].map(([label, value]) => (
            <div key={label} style={{ padding: '6px 0' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{label}</div>
              <div style={{ fontSize: 12, fontWeight: 500 }}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="section-label">Profile Rotation</div>
        <div className="row">
          <div>
            <div style={{ fontSize: 12 }}>Auto-rotate</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>New identity per session</div>
          </div>
          <div className="toggle on" />
        </div>
        <div className="row">
          <span style={{ fontSize: 12 }}>Rotate Now</span>
          <button className="btn btn-secondary" style={{ fontSize: 11 }}>↻ Rotate</button>
        </div>
      </div>
    </div>
  );
}

/* ─── SIGNALS TAB ───────────────────────────────────────────────── */

function SignalsTab() {
  const groups = [
    { name: 'Graphics', signals: ['Canvas 2D', 'WebGL Params', 'WebGL Vendor'] },
    { name: 'Audio', signals: ['AudioContext', 'OfflineAudioContext'] },
    { name: 'Hardware', signals: ['Screen Size', 'Color Depth', 'CPU Cores', 'Device Memory'] },
    { name: 'Navigator', signals: ['User Agent', 'Platform', 'Language'] },
    { name: 'Network', signals: ['WebRTC IP', 'WebRTC IPv6'] },
    { name: 'Timing', signals: ['Timezone', 'Date offset'] },
    { name: 'Fonts', signals: ['Font Enumeration', 'Font Metrics'] },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {groups.map((group) => (
        <div key={group.name} className="card">
          <div className="section-label">{group.name}</div>
          {group.signals.map((signal) => (
            <div key={signal} className="row">
              <span style={{ fontSize: 12 }}>{signal}</span>
              <div style={{ display: 'flex', gap: 4 }}>
                <span className="pill off">Off</span>
                <span className="pill green">Noise</span>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

/* ─── HEADERS TAB ───────────────────────────────────────────────── */

function HeadersTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div className="card">
        <div className="section-label">Request Headers</div>
        <div className="row">
          <div>
            <div style={{ fontSize: 12 }}>User-Agent</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Matches spoofed navigator</div>
          </div>
          <div className="toggle on" />
        </div>
        <div className="row">
          <div>
            <div style={{ fontSize: 12 }}>Accept-Language</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Matches spoofed language</div>
          </div>
          <div className="toggle on" />
        </div>
        <div className="row">
          <div>
            <div style={{ fontSize: 12 }}>DNT (Do Not Track)</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Adds uniqueness — disable for stealth</div>
          </div>
          <div className="toggle" />
        </div>
      </div>

      <div className="card">
        <div className="section-label">Referer Policy</div>
        <div className="row">
          <div>
            <div style={{ fontSize: 12 }}>Strip referer to origin</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Send only domain, not full path</div>
          </div>
          <div className="toggle on" />
        </div>
      </div>
    </div>
  );
}

/* ─── RULES TAB ─────────────────────────────────────────────────── */

function RulesTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div className="card">
        <div className="section-label">Domain Exceptions</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '8px 0' }}>
          Sites where spoofing is disabled. Add domains that break with fingerprint protection.
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            type="text"
            placeholder="example.com"
            style={{
              flex: 1,
              fontSize: 12,
              padding: '6px 10px',
              borderRadius: 6,
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              color: 'var(--text)',
              outline: 'none',
            }}
          />
          <button className="btn btn-primary">Add</button>
        </div>
      </div>

      <div className="card">
        <div className="section-label">Blocklist</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '8px 0' }}>
          Tracking domains to block entirely. Requests to these domains will be cancelled.
        </div>
      </div>
    </div>
  );
}

/* ─── SETTINGS TAB ──────────────────────────────────────────────── */

function SettingsTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div className="card">
        <div className="section-label">General</div>
        <div className="row">
          <div>
            <div style={{ fontSize: 12 }}>Apply to all containers</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Use same settings for all containers</div>
          </div>
          <div className="toggle" />
        </div>
        <div className="row">
          <div>
            <div style={{ fontSize: 12 }}>Auto-rotate profiles</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>New identity each session</div>
          </div>
          <div className="toggle on" />
        </div>
      </div>

      <div className="card">
        <div className="section-label">Data</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" style={{ flex: 1 }}>Export Settings</button>
          <button className="btn btn-secondary" style={{ flex: 1 }}>Import Settings</button>
        </div>
      </div>

      <div className="card" style={{ borderColor: 'var(--red-border)' }}>
        <div className="section-label" style={{ color: 'var(--red)' }}>Danger Zone</div>
        <button className="btn" style={{ background: 'var(--red-muted)', color: 'var(--red)', borderColor: 'var(--red-border)', width: '100%' }}>
          Reset All Settings
        </button>
      </div>
    </div>
  );
}
