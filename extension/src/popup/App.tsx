import React, { useEffect, useState } from 'react';

type Tab = 'dashboard' | 'fingerprint' | 'signals' | 'headers' | 'whitelist' | 'settings';

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [engineStatus, setEngineStatus] = useState<'checking' | 'active' | 'missing'>('checking');

  useEffect(() => {
    // Check if C++ engine is available by looking for window.setCanvasSeed
    // This runs in the popup context, so we query the active tab
    browser.tabs.query({ active: true, currentWindow: true }).then(async (tabs) => {
      const tab = tabs[0];
      if (!tab?.id) return;

      try {
        const results = await browser.scripting.executeScript({
          target: { tabId: tab.id },
          world: 'MAIN',
          func: () => typeof (window as Record<string, unknown>).setCanvasSeed === 'function',
        });
        setEngineStatus(results[0]?.result ? 'active' : 'missing');
      } catch {
        setEngineStatus('missing');
      }
    });
  }, []);

  const tabs: { id: Tab; label: string }[] = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'fingerprint', label: 'Fingerprint' },
    { id: 'signals', label: 'Signals' },
    { id: 'headers', label: 'Headers' },
    { id: 'whitelist', label: 'Whitelist' },
    { id: 'settings', label: 'Settings' },
  ];

  return (
    <div style={{ width: 380, minHeight: 500, fontFamily: 'system-ui, sans-serif' }}>
      <header style={{ padding: '12px 16px', borderBottom: '1px solid #e5e7eb' }}>
        <h1 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Cloakfox Shield</h1>
        <div style={{ fontSize: 12, marginTop: 4, color: engineStatus === 'active' ? '#16a34a' : '#dc2626' }}>
          Engine: {engineStatus === 'checking' ? '...' : engineStatus === 'active' ? 'C++ Active' : 'Not Detected'}
        </div>
      </header>

      <nav style={{ display: 'flex', borderBottom: '1px solid #e5e7eb', overflowX: 'auto' }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1,
              padding: '8px 4px',
              fontSize: 11,
              border: 'none',
              background: activeTab === tab.id ? '#f3f4f6' : 'transparent',
              borderBottom: activeTab === tab.id ? '2px solid #2563eb' : '2px solid transparent',
              cursor: 'pointer',
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main style={{ padding: 16 }}>
        {activeTab === 'dashboard' && <DashboardTab />}
        {activeTab !== 'dashboard' && (
          <p style={{ color: '#6b7280', fontSize: 13 }}>
            {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} tab — coming soon.
          </p>
        )}
      </main>
    </div>
  );
}

function DashboardTab() {
  return (
    <div>
      <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Protection Status</h2>
      <div style={{ display: 'grid', gap: 8 }}>
        {['Canvas', 'Audio', 'Navigator', 'Screen', 'Fonts', 'WebGL', 'WebRTC', 'Timezone'].map(
          (category) => (
            <div
              key={category}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '6px 10px',
                background: '#f9fafb',
                borderRadius: 6,
                fontSize: 13,
              }}
            >
              <span>{category}</span>
              <span style={{ color: '#16a34a', fontWeight: 500, fontSize: 11 }}>C++ Protected</span>
            </div>
          )
        )}
      </div>
    </div>
  );
}
