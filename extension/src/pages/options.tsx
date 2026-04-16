/**
 * Options Page - Full-page settings for Cloakfox Shield
 */

import React, { useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import browser from 'webextension-polyfill';
import '../popup/styles.css';

// Types
interface GlobalSettings {
  badgeEnabled: boolean;
  notificationsEnabled: boolean;
  darkMode: 'auto' | 'light' | 'dark';
  defaultProtectionLevel: 0 | 1 | 2 | 3;
  ipIsolationEnabled: boolean;
  firstPartyIsolation: boolean;
  contextMenuEnabled: boolean;
  keyboardShortcutsEnabled: boolean;
}

const defaultSettings: GlobalSettings = {
  badgeEnabled: true,
  notificationsEnabled: true,
  darkMode: 'auto',
  defaultProtectionLevel: 2,
  ipIsolationEnabled: true,
  firstPartyIsolation: false,
  contextMenuEnabled: true,
  keyboardShortcutsEnabled: true,
};

function OptionsPage() {
  const [settings, setSettings] = useState<GlobalSettings>(defaultSettings);
  const [saved, setSaved] = useState(false);
  const [activeTab, setActiveTab] = useState<'general' | 'privacy' | 'shortcuts' | 'about'>('general');

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    const stored = await browser.storage.local.get('globalSettings');
    if (stored.globalSettings) {
      setSettings({ ...defaultSettings, ...stored.globalSettings });
    }
  };

  const saveSettings = async (newSettings: Partial<GlobalSettings>) => {
    const updated = { ...settings, ...newSettings };
    setSettings(updated);
    await browser.storage.local.set({ globalSettings: updated });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className={`min-h-screen ${settings.darkMode === 'dark' ? 'dark bg-gray-900' : 'bg-gray-50'}`}>
      <div className="max-w-4xl mx-auto py-8 px-4">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <img src="../icons/icon-48.svg" alt="Cloakfox Shield" className="w-12 h-12" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Cloakfox Shield</h1>
            <p className="text-gray-600 dark:text-gray-400">Settings & Configuration</p>
          </div>
          {saved && (
            <span className="ml-auto bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm">
              Saved!
            </span>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 border-b border-gray-200 dark:border-gray-700">
          {(['general', 'privacy', 'shortcuts', 'about'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 font-medium capitalize transition-colors ${
                activeTab === tab
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-600 hover:text-gray-900 dark:text-gray-400'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          {activeTab === 'general' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">General Settings</h2>

              {/* Badge */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white">Toolbar Badge</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Show blocked count on icon</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.badgeEnabled}
                    onChange={(e) => saveSettings({ badgeEnabled: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              {/* Notifications */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white">Notifications</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Show notifications for actions</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.notificationsEnabled}
                    onChange={(e) => saveSettings({ notificationsEnabled: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              {/* Dark Mode */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white">Theme</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Choose your preferred theme</p>
                </div>
                <select
                  value={settings.darkMode}
                  onChange={(e) => saveSettings({ darkMode: e.target.value as 'auto' | 'light' | 'dark' })}
                  className="px-3 py-2 border border-gray-300 rounded-lg bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                >
                  <option value="auto">Auto (System)</option>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </select>
              </div>

              {/* Default Protection Level */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white">Default Protection Level</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">For new containers</p>
                </div>
                <select
                  value={settings.defaultProtectionLevel}
                  onChange={(e) => saveSettings({ defaultProtectionLevel: parseInt(e.target.value) as 0 | 1 | 2 | 3 })}
                  className="px-3 py-2 border border-gray-300 rounded-lg bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                >
                  <option value={0}>Off</option>
                  <option value={1}>Minimal</option>
                  <option value={2}>Balanced</option>
                  <option value={3}>Strict</option>
                </select>
              </div>

              {/* Context Menu */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white">Context Menu</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Show right-click menu options</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.contextMenuEnabled}
                    onChange={(e) => saveSettings({ contextMenuEnabled: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
            </div>
          )}

          {activeTab === 'privacy' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Privacy Settings</h2>

              {/* IP Isolation */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white">IP Isolation Warnings</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Warn when same IP accessed from different containers</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.ipIsolationEnabled}
                    onChange={(e) => saveSettings({ ipIsolationEnabled: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              {/* First Party Isolation */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white">First Party Isolation</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Isolate cookies and storage per domain</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.firstPartyIsolation}
                    onChange={(e) => saveSettings({ firstPartyIsolation: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                <h3 className="font-medium text-gray-900 dark:text-white mb-4">Data Management</h3>
                <div className="flex gap-4">
                  <button
                    onClick={async () => {
                      const data = await browser.storage.local.get();
                      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = 'containershield-backup.json';
                      a.click();
                    }}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    Export All Data
                  </button>
                  <button
                    onClick={async () => {
                      if (confirm('This will delete all settings. Are you sure?')) {
                        await browser.storage.local.clear();
                        window.location.reload();
                      }
                    }}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
                  >
                    Reset Everything
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'shortcuts' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Keyboard Shortcuts</h2>

              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white">Enable Shortcuts</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Use keyboard shortcuts</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.keyboardShortcutsEnabled}
                    onChange={(e) => saveSettings({ keyboardShortcutsEnabled: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              <div className="space-y-4">
                {[
                  { action: 'Toggle Protection', shortcut: 'Alt+Shift+P' },
                  { action: 'Rotate Fingerprint', shortcut: 'Alt+Shift+R' },
                  { action: 'Toggle Site Exception', shortcut: 'Alt+Shift+E' },
                  { action: 'Open Popup', shortcut: 'Alt+Shift+C' },
                ].map(({ action, shortcut }) => (
                  <div key={action} className="flex items-center justify-between py-3 border-b border-gray-100 dark:border-gray-700">
                    <span className="text-gray-900 dark:text-white">{action}</span>
                    <kbd className="px-3 py-1 bg-gray-100 dark:bg-gray-700 rounded text-sm font-mono text-gray-700 dark:text-gray-300">
                      {shortcut}
                    </kbd>
                  </div>
                ))}
              </div>

              <p className="text-sm text-gray-500 dark:text-gray-400 mt-4">
                To customize shortcuts, go to <code>about:addons</code> → ⚙️ → Manage Extension Shortcuts
              </p>
            </div>
          )}

          {activeTab === 'about' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">About Cloakfox Shield</h2>

              <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <img src="../icons/icon-64.svg" alt="Cloakfox Shield" className="w-16 h-16" />
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white">Cloakfox Shield</h3>
                  <p className="text-gray-600 dark:text-gray-400">Version 0.2.0</p>
                  <p className="text-sm text-gray-500 dark:text-gray-500">Per-container fingerprint protection</p>
                </div>
              </div>

              <div className="space-y-3">
                <a
                  href="https://github.com/roshin8/containershield"
                  target="_blank"
                  className="flex items-center justify-between p-3 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  <span className="text-gray-900 dark:text-white">GitHub Repository</span>
                  <span className="text-gray-400">→</span>
                </a>
                <a
                  href="https://github.com/roshin8/containershield/issues"
                  target="_blank"
                  className="flex items-center justify-between p-3 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  <span className="text-gray-900 dark:text-white">Report an Issue</span>
                  <span className="text-gray-400">→</span>
                </a>
                <a
                  href="https://github.com/roshin8/containershield/blob/main/LICENSE"
                  target="_blank"
                  className="flex items-center justify-between p-3 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  <span className="text-gray-900 dark:text-white">License (GPL-3.0)</span>
                  <span className="text-gray-400">→</span>
                </a>
              </div>

              <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                <h3 className="font-medium text-gray-900 dark:text-white mb-2">Acknowledgments</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Inspired by <a href="https://github.com/nickersoft/chameleon-ext" className="text-blue-600">Chameleon</a>,{' '}
                  <a href="https://jshelter.org" className="text-blue-600">JShelter</a>, and{' '}
                  <a href="https://brave.com" className="text-blue-600">Brave Browser</a>.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Mount the app
const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<OptionsPage />);
}
