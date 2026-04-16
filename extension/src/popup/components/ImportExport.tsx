/**
 * Import/Export Settings Component
 *
 * Allows users to backup and restore Cloakfox Shield settings
 */

import React, { useState, useRef } from 'react';
import browser from 'webextension-polyfill';

interface ImportExportProps {
  onImportComplete?: () => void;
}

export function ImportExport({ onImportComplete }: ImportExportProps) {
  const [status, setStatus] = useState<{
    type: 'success' | 'error' | 'info' | null;
    message: string;
  }>({ type: null, message: '' });
  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleExport = async () => {
    setIsExporting(true);
    setStatus({ type: null, message: '' });

    try {
      // Get all storage data
      const allData = await browser.storage.local.get(null);

      // Add metadata
      const exportData = {
        _meta: {
          version: '0.3.0',
          exportedAt: new Date().toISOString(),
          type: 'cloakfox-settings',
        },
        ...allData,
      };

      // Create blob and download
      const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const timestamp = new Date().toISOString().split('T')[0];
      const filename = `cloakfox-backup-${timestamp}.json`;

      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setStatus({
        type: 'success',
        message: `Settings exported to ${filename}`,
      });
    } catch (error) {
      console.error('Export failed:', error);
      setStatus({
        type: 'error',
        message: 'Failed to export settings',
      });
    } finally {
      setIsExporting(false);
    }
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsImporting(true);
    setStatus({ type: null, message: '' });

    try {
      const text = await file.text();
      const importData = JSON.parse(text);

      // Validate import data
      if (!importData._meta || importData._meta.type !== 'cloakfox-settings') {
        throw new Error('Invalid backup file format');
      }

      // Remove metadata before importing
      const { _meta, ...settingsData } = importData;

      // Confirm import
      const containerCount = Object.keys(settingsData.containers || {}).length;
      const confirmMessage = `Import settings from ${_meta.exportedAt}?\n\nThis will overwrite your current settings.\n\nContainers: ${containerCount}`;

      if (!confirm(confirmMessage)) {
        setStatus({ type: 'info', message: 'Import cancelled' });
        return;
      }

      // Clear existing and import new
      await browser.storage.local.clear();
      await browser.storage.local.set(settingsData);

      setStatus({
        type: 'success',
        message: `Settings imported successfully (${containerCount} containers)`,
      });

      // Notify parent component
      onImportComplete?.();

      // Reload to apply settings
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (error) {
      console.error('Import failed:', error);
      setStatus({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to import settings',
      });
    } finally {
      setIsImporting(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleReset = async () => {
    const confirmed = confirm(
      'Reset all settings to defaults?\n\nThis will:\n- Clear all container settings\n- Remove all domain exceptions\n- Reset protection levels\n\nThis cannot be undone!'
    );

    if (!confirmed) return;

    try {
      await browser.storage.local.clear();
      setStatus({
        type: 'success',
        message: 'Settings reset to defaults',
      });

      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } catch (error) {
      console.error('Reset failed:', error);
      setStatus({
        type: 'error',
        message: 'Failed to reset settings',
      });
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-gray-900 dark:text-white">
        Backup & Restore
      </h3>

      <p className="text-sm text-gray-600 dark:text-gray-400">
        Export your settings to a file or restore from a previous backup.
      </p>

      {/* Status message */}
      {status.type && (
        <div
          className={`p-3 rounded-lg text-sm ${
            status.type === 'success'
              ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
              : status.type === 'error'
              ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
              : 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
          }`}
        >
          {status.message}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={handleExport}
          disabled={isExporting}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg
                     hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
                     text-sm font-medium transition-colors"
        >
          {isExporting ? (
            <>
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Exporting...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
              Export Settings
            </>
          )}
        </button>

        <button
          onClick={handleImportClick}
          disabled={isImporting}
          className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg
                     hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed
                     text-sm font-medium transition-colors"
        >
          {isImporting ? (
            <>
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Importing...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                />
              </svg>
              Import Settings
            </>
          )}
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>

      {/* Danger zone */}
      <div className="pt-4 mt-4 border-t border-gray-200 dark:border-gray-700">
        <h4 className="text-sm font-medium text-red-600 dark:text-red-400 mb-2">
          Danger Zone
        </h4>
        <button
          onClick={handleReset}
          className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg
                     hover:bg-red-700 text-sm font-medium transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
          Reset All Settings
        </button>
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          This will remove all your settings and cannot be undone.
        </p>
      </div>

      {/* Info */}
      <div className="p-3 bg-gray-100 dark:bg-gray-800 rounded-lg">
        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          What's included in the backup?
        </h4>
        <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1 list-disc list-inside">
          <li>Container settings and protection levels</li>
          <li>Domain exceptions and rules</li>
          <li>Profile assignments</li>
          <li>Global preferences</li>
          <li>IP isolation data</li>
        </ul>
      </div>
    </div>
  );
}

export default ImportExport;
