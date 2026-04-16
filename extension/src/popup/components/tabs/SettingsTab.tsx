import React, { useState } from 'react';
import browser from 'webextension-polyfill';
import type { ContainerIdentity, ContainerSettings } from '@/types';
import { MSG_SET_SETTINGS } from '@/constants';
import { EXTENSION_VERSION } from '@/lib/constants';

interface SettingsTabProps {
  settings: ContainerSettings;
  containers: ContainerIdentity[];
  currentContainerId: string;
  onSaveSettings: (updates: Partial<ContainerSettings>) => void;
}

export default function SettingsTab({
  settings, containers, currentContainerId, onSaveSettings,
}: SettingsTabProps) {
  const [showApplyModal, setShowApplyModal] = useState(false);
  const [selectedContainers, setSelectedContainers] = useState<Set<string>>(new Set());
  const [applyOptions, setApplyOptions] = useState({
    protectionLevel: true, spoofers: true, profile: true, headers: false,
  });
  const [applyStatus, setApplyStatus] = useState<'idle' | 'applying' | 'success' | 'error'>('idle');

  const toggleContainer = (id: string) => {
    const s = new Set(selectedContainers);
    s.has(id) ? s.delete(id) : s.add(id);
    setSelectedContainers(s);
  };

  const applyToContainers = async () => {
    if (selectedContainers.size === 0) return;
    setApplyStatus('applying');
    try {
      const updates: Partial<ContainerSettings> = {};
      if (applyOptions.protectionLevel) { updates.enabled = settings.enabled; updates.protectionLevel = settings.protectionLevel; }
      if (applyOptions.spoofers) updates.spoofers = settings.spoofers;
      if (applyOptions.profile) updates.profile = settings.profile;
      if (applyOptions.headers) updates.headers = settings.headers;

      for (const containerId of selectedContainers) {
        await browser.runtime.sendMessage({ type: MSG_SET_SETTINGS, containerId, settings: updates });
      }
      setApplyStatus('success');
      setTimeout(() => { setApplyStatus('idle'); setShowApplyModal(false); setSelectedContainers(new Set()); }, 1500);
    } catch {
      setApplyStatus('error');
      setTimeout(() => setApplyStatus('idle'), 2000);
    }
  };

  const exportSettings = () => {
    try {
      const data = { version: EXTENSION_VERSION, exportedAt: new Date().toISOString(), settings };
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `cloakfox-shield-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {}
  };

  const importSettings = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      if (data.settings) onSaveSettings(data.settings);
    } catch {}
    event.target.value = '';
  };

  const resetToDefaults = () => {
    if (confirm('Reset all settings for this container to defaults?')) {
      onSaveSettings({ enabled: true, protectionLevel: 2, profile: { mode: 'random' } });
    }
  };

  return (
    <div className="space-y-3">
      {/* Apply to Containers */}
      <div className="card">
        <div className="section-label">Sync to Containers</div>
        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
          Copy this container's settings to others
        </div>
        <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => setShowApplyModal(true)}>
          Apply Settings...
        </button>
      </div>

      {/* Apply Modal */}
      {showApplyModal && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4" style={{ background: 'rgba(0,0,0,0.5)' }}>
          <div className="rounded-lg w-full max-w-sm max-h-[80vh] overflow-hidden flex flex-col"
            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
            <div className="p-3" style={{ borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontWeight: 600, fontSize: '13px' }}>Apply Settings To...</div>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="section-label" style={{ margin: 0 }}>Containers</span>
                  <div className="flex gap-2">
                    <button onClick={() => setSelectedContainers(new Set(containers.map(c => c.cookieStoreId).filter(id => id !== currentContainerId)))}
                      style={{ fontSize: '10px', color: 'var(--accent)', cursor: 'pointer', background: 'none', border: 'none' }}>
                      All
                    </button>
                    <button onClick={() => setSelectedContainers(new Set())}
                      style={{ fontSize: '10px', color: 'var(--text-muted)', cursor: 'pointer', background: 'none', border: 'none' }}>
                      None
                    </button>
                  </div>
                </div>
                <div className="space-y-0.5" style={{ maxHeight: '120px', overflowY: 'auto' }}>
                  {containers.filter(c => c.cookieStoreId !== currentContainerId).map((c) => (
                    <label key={c.cookieStoreId} className="flex items-center gap-2 p-1.5 rounded cursor-pointer"
                      style={{ fontSize: '12px' }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}>
                      <input type="checkbox" checked={selectedContainers.has(c.cookieStoreId)}
                        onChange={() => toggleContainer(c.cookieStoreId)} />
                      <div className="w-2.5 h-2.5 rounded-full" style={{ background: c.colorCode }} />
                      <span>{c.name}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <div className="section-label">Include</div>
                <div className="space-y-0.5">
                  {[
                    { key: 'protectionLevel', label: 'Protection Level' },
                    { key: 'spoofers', label: 'Signal Settings' },
                    { key: 'profile', label: 'Profile Settings' },
                    { key: 'headers', label: 'Header Settings' },
                  ].map(({ key, label }) => (
                    <label key={key} className="flex items-center gap-2 p-1.5 rounded cursor-pointer"
                      style={{ fontSize: '12px' }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}>
                      <input type="checkbox" checked={applyOptions[key as keyof typeof applyOptions]}
                        onChange={(e) => setApplyOptions({ ...applyOptions, [key]: e.target.checked })} />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex gap-2 p-3" style={{ borderTop: '1px solid var(--border)' }}>
              <button className="btn btn-secondary flex-1"
                onClick={() => { setShowApplyModal(false); setSelectedContainers(new Set()); }}>
                Cancel
              </button>
              <button className="btn btn-primary flex-1"
                disabled={selectedContainers.size === 0 || applyStatus === 'applying'}
                onClick={applyToContainers}
                style={{ opacity: selectedContainers.size === 0 ? 0.5 : 1 }}>
                {applyStatus === 'applying' ? 'Applying...' : applyStatus === 'success' ? 'Done!' : `Apply (${selectedContainers.size})`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Backup & Restore */}
      <div className="card">
        <div className="section-label">Backup & Restore</div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-secondary" style={{ flex: 1 }} onClick={exportSettings}>Export</button>
          <label style={{ flex: 1 }}>
            <span className="btn btn-secondary" style={{ display: 'block', textAlign: 'center', cursor: 'pointer' }}>Import</span>
            <input type="file" accept=".json" onChange={importSettings} style={{ display: 'none' }} />
          </label>
        </div>
      </div>

      {/* Reset */}
      <div className="card" style={{ borderColor: 'var(--red-border)' }}>
        <div className="section-label" style={{ color: 'var(--red)' }}>Danger Zone</div>
        <button className="btn btn-danger" style={{ width: '100%' }} onClick={resetToDefaults}>
          Reset to Defaults
        </button>
      </div>

      {/* Keyboard Shortcuts */}
      <div className="card">
        <div className="section-label">Keyboard Shortcuts</div>
        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
          {[
            { action: 'Toggle Protection', key: 'P' },
            { action: 'Rotate Fingerprint', key: 'R' },
            { action: 'Toggle Site Exception', key: 'E' },
            { action: 'Open Popup', key: 'C' },
          ].map(({ action, key }) => {
            const isMac = navigator.platform?.includes('Mac');
            const modifier = isMac ? 'Ctrl+Shift' : 'Alt+Shift';
            return (
              <div key={key} className="row">
                <span className="row-label">{action}</span>
                <code style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '3px', background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
                  {modifier}+{key}
                </code>
              </div>
            );
          })}
        </div>
      </div>

      <div className="text-center py-1" style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
        Cloakfox Shield v{EXTENSION_VERSION}
      </div>
    </div>
  );
}
