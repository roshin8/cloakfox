import React, { useEffect, useState, useCallback } from 'react';
import browser from 'webextension-polyfill';
import type { ContainerIdentity, ContainerSettings } from '@/types';
import { createDefaultSettings } from '@/types/settings';
import {
  MSG_GET_ALL_CONTAINERS,
  MSG_GET_CONTAINER_INFO,
  MSG_GET_SETTINGS,
  MSG_SET_SETTINGS,
  MSG_GET_ASSIGNED_PROFILE,
} from '@/constants';
import { EXTENSION_VERSION } from '@/lib/constants';
import { popupLogger } from '@/lib/logger';
import TabNavigation, { type TabId } from './components/TabNavigation';
import DashboardTab from './components/tabs/DashboardTab';
import FingerprintTab from './components/tabs/FingerprintTab';
import SignalsTab from './components/tabs/SignalsTab';
import HeadersTab from './components/tabs/HeadersTab';
import WhitelistTab from './components/tabs/WhitelistTab';
import SettingsTab from './components/tabs/SettingsTab';
import ErrorBoundary from './components/ErrorBoundary';

interface ContainerInfo {
  containerId: string;
  containerName: string;
  containerColor: string;
  containerIcon: string;
}

interface AssignedProfile {
  userAgent?: {
    id?: string; name?: string; userAgent?: string; platform?: string;
    vendor?: string; platformName?: string; platformVersion?: string; mobile?: boolean;
  };
  screen?: {
    width: number; height: number; availWidth?: number; availHeight?: number;
    colorDepth?: number; pixelDepth?: number; devicePixelRatio?: number;
  };
  hardwareConcurrency?: number;
  deviceMemory?: number;
  languages?: string[];
  timezoneOffset?: number;
}

export default function App() {
  const [containers, setContainers] = useState<ContainerIdentity[]>([]);
  const [currentContainer, setCurrentContainer] = useState<ContainerInfo | null>(null);
  const [selectedContainer, setSelectedContainer] = useState<string | null>(null);
  const [settings, setSettings] = useState<ContainerSettings>(createDefaultSettings());
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>('dashboard');
  const [highlightedSignal, setHighlightedSignal] = useState<{ category: string; signal: string } | undefined>();
  const [assignedProfile, setAssignedProfile] = useState<AssignedProfile | undefined>();
  const [isDark, setIsDark] = useState(() => {
    try { return localStorage.getItem('cloakfox-theme') === 'dark'; } catch { return false; }
  });

  // Apply theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    try { localStorage.setItem('cloakfox-theme', isDark ? 'dark' : 'light'); } catch {}
  }, [isDark]);

  useEffect(() => {
    async function init() {
      try {
        const allContainers = await browser.runtime.sendMessage({ type: MSG_GET_ALL_CONTAINERS }) as ContainerIdentity[] | null;
        setContainers(allContainers || []);

        const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
        const containerInfo = await browser.runtime.sendMessage({ type: MSG_GET_CONTAINER_INFO, tabId: tab?.id }) as ContainerInfo;
        setCurrentContainer(containerInfo);
        setSelectedContainer(containerInfo.containerId);

        const containerSettings = await browser.runtime.sendMessage({ type: MSG_GET_SETTINGS, containerId: containerInfo.containerId }) as ContainerSettings;
        setSettings(containerSettings);
      } catch (error) {
        popupLogger.error('Failed to initialize:', error);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  useEffect(() => {
    if (!selectedContainer) return;
    (async () => {
      try {
        const s = await browser.runtime.sendMessage({ type: MSG_GET_SETTINGS, containerId: selectedContainer }) as ContainerSettings;
        setSettings(s);
      } catch {}
    })();
  }, [selectedContainer]);

  const loadAssignedProfile = useCallback(async () => {
    if (!selectedContainer) return;
    try {
      // Try to get the ACTUAL profile from the inject script (stored per-tab)
      const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
      if (tab?.id) {
        const stored = await browser.storage.local.get(`activeProfile:${tab.id}`);
        const active = stored[`activeProfile:${tab.id}`];
        if (active?.profile) {
          setAssignedProfile(active.profile);
          return;
        }
      }
      // Fallback to background's assigned profile
      const profile = await browser.runtime.sendMessage({ type: MSG_GET_ASSIGNED_PROFILE, containerId: selectedContainer }) as AssignedProfile | null;
      setAssignedProfile(profile || undefined);
    } catch { setAssignedProfile(undefined); }
  }, [selectedContainer]);

  useEffect(() => { loadAssignedProfile(); }, [loadAssignedProfile]);

  const saveSettings = useCallback(async (updates: Partial<ContainerSettings>) => {
    if (!selectedContainer) return;
    setSettings(prev => ({ ...prev, ...updates }));
    try {
      await browser.runtime.sendMessage({ type: MSG_SET_SETTINGS, containerId: selectedContainer, settings: updates });
      await loadAssignedProfile();
    } catch (error) {
      popupLogger.error('Failed to save:', error);
    }
  }, [selectedContainer, loadAssignedProfile]);

  const enableSpoofer = useCallback(async (settingPath: string) => {
    const [category, setting] = settingPath.split('.');
    if (!category || !setting) return;
    const spoofers = { ...settings.spoofers } as any;
    if (spoofers[category]) {
      spoofers[category] = { ...spoofers[category], [setting]: 'noise' };
    }
    await saveSettings({ spoofers });
  }, [settings, saveSettings]);

  const navigateToSignal = useCallback((category: string, signal: string) => {
    setHighlightedSignal({ category, signal });
    setActiveTab('signals');
    setTimeout(() => setHighlightedSignal(undefined), 3000);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full w-full" style={{ background: 'var(--bg-base)' }}>
        <div className="w-5 h-5 border-2 rounded-full animate-spin"
          style={{ borderColor: 'var(--border)', borderTopColor: 'var(--accent)' }} />
      </div>
    );
  }

  const containerInfo = containers.find(c => c.cookieStoreId === selectedContainer);
  const activeCount = Object.values(settings.spoofers).reduce((n, cat) =>
    n + Object.values(cat).filter(v => v !== 'off').length, 0);

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', width: '440px', height: '540px', background: 'var(--bg-base)', overflow: 'hidden' }}>
        <TabNavigation
          activeTab={activeTab}
          onTabChange={setActiveTab}
          isDark={isDark}
          onToggleTheme={() => setIsDark(d => !d)}
        />

        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', width: 'calc(100% - 54px)' }}>
          {/* Header */}
          <header className="flex items-center justify-between px-3 py-2"
            style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="flex items-center gap-2.5">
              {/* Status indicator */}
              <div className="w-7 h-7 rounded-md flex items-center justify-center"
                style={{ background: settings.enabled ? 'var(--green-muted)' : 'var(--bg-elevated)' }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}
                  style={{ color: settings.enabled ? 'var(--green)' : 'var(--text-muted)' }}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                </svg>
              </div>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>
                  Cloakfox Shield
                </div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                  {settings.enabled ? `${activeCount} protections` : 'Disabled'}
                </div>
              </div>
            </div>

            <select
              value={selectedContainer || ''}
              onChange={(e) => setSelectedContainer(e.target.value)}
              className="select"
              style={{
                width: 'auto',
                maxWidth: '130px',
                fontSize: '11px',
                padding: '4px 6px',
                borderLeft: `3px solid ${containerInfo?.colorCode || 'var(--text-muted)'}`,
              }}
            >
              {containers.map((c) => (
                <option key={c.cookieStoreId} value={c.cookieStoreId}>
                  {c.name}{c.cookieStoreId === currentContainer?.containerId ? ' *' : ''}
                </option>
              ))}
            </select>
          </header>

          {/* Content */}
          <main style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '12px', width: '100%' }}>
            {activeTab === 'dashboard' && (
              <DashboardTab settings={settings} onSaveSettings={saveSettings}
                onEnableSpoofer={enableSpoofer} onNavigateToSignal={navigateToSignal}
                currentContainerId={selectedContainer || undefined}
                assignedProfile={assignedProfile} />
            )}
            {activeTab === 'fingerprint' && (
              <FingerprintTab settings={settings} onSaveSettings={saveSettings}
                assignedProfile={assignedProfile} />
            )}
            {activeTab === 'signals' && (
              <SignalsTab settings={settings} onSaveSettings={saveSettings}
                highlightedSignal={highlightedSignal} />
            )}
            {activeTab === 'headers' && (
              <HeadersTab settings={settings} onSaveSettings={saveSettings} />
            )}
            {activeTab === 'whitelist' && (
              <WhitelistTab settings={settings} onSaveSettings={saveSettings} />
            )}
            {activeTab === 'settings' && (
              <SettingsTab settings={settings} containers={containers}
                currentContainerId={selectedContainer || ''} onSaveSettings={saveSettings} />
            )}
          </main>

          {/* Footer */}
          <footer className="flex items-center justify-between px-3 py-1.5"
            style={{ borderTop: '1px solid var(--border)', fontSize: '10px', color: 'var(--text-muted)' }}>
            <span>{containerInfo?.name || 'Default'}</span>
            <span>v{EXTENSION_VERSION}</span>
          </footer>
        </div>
      </div>
    </ErrorBoundary>
  );
}
