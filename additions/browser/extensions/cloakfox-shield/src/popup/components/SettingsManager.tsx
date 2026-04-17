import React, { useState, useRef } from 'react';
import browser from 'webextension-polyfill';
import type { GlobalStorage } from '@/types';
import { popupLogger } from '@/lib/logger';

/**
 * Message types for settings operations
 */
const MSG_EXPORT_SETTINGS = 'EXPORT_SETTINGS';
const MSG_IMPORT_SETTINGS = 'IMPORT_SETTINGS';
const MSG_RESET_SETTINGS = 'RESET_SETTINGS';

interface SettingsManagerProps {
  onSettingsChange?: () => void;
}

/**
 * Component for exporting, importing, and resetting settings
 */
export default function SettingsManager({ onSettingsChange }: SettingsManagerProps) {
  const [status, setStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [showConfirm, setShowConfirm] = useState<'import' | 'reset' | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const clearStatus = () => {
    setTimeout(() => setStatus(null), 3000);
  };

  /**
   * Export all settings to a JSON file
   */
  const handleExport = async () => {
    try {
      // Get all storage data
      const data = await browser.storage.local.get(null);

      const exportData = {
        version: '1.0',
        exportedAt: new Date().toISOString(),
        data,
      };

      const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);

      const a = document.createElement('a');
      a.href = url;
      a.download = `cloakfox-settings-${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setStatus({ type: 'success', message: 'Settings exported successfully' });
      clearStatus();
      popupLogger.info('Settings exported');
    } catch (error) {
      setStatus({ type: 'error', message: 'Failed to export settings' });
      clearStatus();
      popupLogger.error('Export failed:', error);
    }
  };

  /**
   * Import settings from a JSON file
   */
  const handleImport = async (file: File) => {
    try {
      const text = await file.text();
      const importData = JSON.parse(text);

      // Validate import format
      if (!importData.version || !importData.data) {
        throw new Error('Invalid settings file format');
      }

      // Import the settings
      await browser.storage.local.set(importData.data);

      setStatus({ type: 'success', message: 'Settings imported successfully' });
      clearStatus();
      setShowConfirm(null);
      onSettingsChange?.();
      popupLogger.info('Settings imported');
    } catch (error) {
      setStatus({ type: 'error', message: 'Failed to import settings: Invalid file' });
      clearStatus();
      popupLogger.error('Import failed:', error);
    }
  };

  /**
   * Reset all settings to defaults
   */
  const handleReset = async () => {
    try {
      await browser.storage.local.clear();

      setStatus({ type: 'success', message: 'Settings reset to defaults' });
      clearStatus();
      setShowConfirm(null);
      onSettingsChange?.();
      popupLogger.info('Settings reset');
    } catch (error) {
      setStatus({ type: 'error', message: 'Failed to reset settings' });
      clearStatus();
      popupLogger.error('Reset failed:', error);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setShowConfirm('import');
    }
  };

  const confirmImport = () => {
    const file = fileInputRef.current?.files?.[0];
    if (file) {
      handleImport(file);
    }
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
        Settings Management
      </h3>

      {/* Status Message */}
      {status && (
        <div
          className={`p-2 rounded text-sm ${
            status.type === 'success'
              ? 'bg-green-900/30 text-green-400 border border-green-500/30'
              : 'bg-red-900/30 text-red-400 border border-red-500/30'
          }`}
        >
          {status.message}
        </div>
      )}

      {/* Action Buttons */}
      <div className="grid grid-cols-3 gap-2">
        <button
          onClick={handleExport}
          className="p-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors"
        >
          <div className="text-lg mb-1">📤</div>
          <div>Export</div>
        </button>

        <label className="p-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors cursor-pointer text-center">
          <div className="text-lg mb-1">📥</div>
          <div>Import</div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleFileSelect}
            className="hidden"
          />
        </label>

        <button
          onClick={() => setShowConfirm('reset')}
          className="p-2 bg-gray-800 hover:bg-red-900/50 rounded-lg text-sm transition-colors"
        >
          <div className="text-lg mb-1">🔄</div>
          <div>Reset</div>
        </button>
      </div>

      {/* Confirmation Dialogs */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900 p-4 rounded-lg max-w-sm mx-4 border border-gray-700">
            <h4 className="font-medium mb-2">
              {showConfirm === 'import' ? 'Import Settings?' : 'Reset All Settings?'}
            </h4>
            <p className="text-sm text-gray-400 mb-4">
              {showConfirm === 'import'
                ? 'This will replace all current settings with the imported ones.'
                : 'This will reset all settings to their default values. This cannot be undone.'}
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => {
                  setShowConfirm(null);
                  if (fileInputRef.current) fileInputRef.current.value = '';
                }}
                className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
              >
                Cancel
              </button>
              <button
                onClick={showConfirm === 'import' ? confirmImport : handleReset}
                className={`px-3 py-1 rounded text-sm ${
                  showConfirm === 'reset'
                    ? 'bg-red-600 hover:bg-red-500'
                    : 'bg-blue-600 hover:bg-blue-500'
                }`}
              >
                {showConfirm === 'import' ? 'Import' : 'Reset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
