/**
 * Per-Domain Rules UI Component
 *
 * Allows users to configure custom protection settings for specific domains
 */

import React, { useState, useEffect } from 'react';
import browser from 'webextension-polyfill';
import type { ProtectionMode } from '@/types';

interface DomainRule {
  domain: string;
  enabled: boolean;
  protectionLevel?: 0 | 1 | 2 | 3;
  overrides?: {
    [category: string]: {
      [signal: string]: ProtectionMode;
    };
  };
  createdAt: number;
}

interface PerDomainRulesProps {
  containerId: string;
}

export function PerDomainRules({ containerId }: PerDomainRulesProps) {
  const [rules, setRules] = useState<DomainRule[]>([]);
  const [newDomain, setNewDomain] = useState('');
  const [editingRule, setEditingRule] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRules();
  }, [containerId]);

  const loadRules = async () => {
    try {
      const result = await browser.storage.local.get(`domainRules_${containerId}`);
      const storedRules = (result[`domainRules_${containerId}`] as DomainRule[] | undefined) || [];
      setRules(storedRules);
    } catch (error) {
      console.error('Failed to load domain rules:', error);
    } finally {
      setLoading(false);
    }
  };

  const saveRules = async (newRules: DomainRule[]) => {
    try {
      await browser.storage.local.set({
        [`domainRules_${containerId}`]: newRules,
      });
      setRules(newRules);
    } catch (error) {
      console.error('Failed to save domain rules:', error);
    }
  };

  const addRule = () => {
    if (!newDomain.trim()) return;

    // Validate domain format
    const domain = newDomain.trim().toLowerCase();
    if (rules.some(r => r.domain === domain)) {
      alert('Rule for this domain already exists');
      return;
    }

    const newRule: DomainRule = {
      domain,
      enabled: true,
      protectionLevel: 0, // Off for this domain
      createdAt: Date.now(),
    };

    saveRules([...rules, newRule]);
    setNewDomain('');
  };

  const removeRule = (domain: string) => {
    saveRules(rules.filter(r => r.domain !== domain));
  };

  const updateRule = (domain: string, updates: Partial<DomainRule>) => {
    saveRules(rules.map(r =>
      r.domain === domain ? { ...r, ...updates } : r
    ));
  };

  const toggleRule = (domain: string) => {
    const rule = rules.find(r => r.domain === domain);
    if (rule) {
      updateRule(domain, { enabled: !rule.enabled });
    }
  };

  if (loading) {
    return (
      <div className="p-4 text-center text-gray-500 dark:text-gray-400">
        Loading rules...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900 dark:text-white">
          Per-Domain Rules
        </h3>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {rules.length} rule{rules.length !== 1 ? 's' : ''}
        </span>
      </div>

      <p className="text-sm text-gray-600 dark:text-gray-400">
        Configure custom protection settings for specific websites.
      </p>

      {/* Add new rule */}
      <div className="flex gap-2">
        <input
          type="text"
          value={newDomain}
          onChange={(e) => setNewDomain(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addRule()}
          placeholder="example.com"
          className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                     focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
        />
        <button
          onClick={addRule}
          disabled={!newDomain.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700
                     disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
        >
          Add Rule
        </button>
      </div>

      {/* Rules list */}
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {rules.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <p className="text-sm">No domain rules configured</p>
            <p className="text-xs mt-1">Add a domain above to create custom rules</p>
          </div>
        ) : (
          rules.map((rule) => (
            <div
              key={rule.domain}
              className={`p-3 border rounded-lg transition-colors ${
                rule.enabled
                  ? 'border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20'
                  : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => toggleRule(rule.domain)}
                    className={`w-10 h-6 rounded-full transition-colors relative ${
                      rule.enabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                    }`}
                  >
                    <span
                      className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${
                        rule.enabled ? 'translate-x-4' : ''
                      }`}
                    />
                  </button>
                  <div>
                    <span className="font-medium text-gray-900 dark:text-white">
                      {rule.domain}
                    </span>
                    <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                      {rule.enabled ? 'Protection OFF' : 'Using container settings'}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setEditingRule(editingRule === rule.domain ? null : rule.domain)}
                    className="p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                    title="Edit rule"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  </button>
                  <button
                    onClick={() => removeRule(rule.domain)}
                    className="p-1 text-red-500 hover:text-red-700"
                    title="Remove rule"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Expanded settings */}
              {editingRule === rule.domain && (
                <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Protection Level
                      </label>
                      <select
                        value={rule.protectionLevel ?? 0}
                        onChange={(e) => updateRule(rule.domain, {
                          protectionLevel: parseInt(e.target.value) as 0 | 1 | 2 | 3
                        })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                      >
                        <option value={0}>Off (No protection)</option>
                        <option value={1}>Minimal</option>
                        <option value={2}>Balanced</option>
                        <option value={3}>Strict</option>
                      </select>
                    </div>

                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      Created: {new Date(rule.createdAt).toLocaleDateString()}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Quick actions */}
      {rules.length > 0 && (
        <div className="flex justify-between pt-2 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={() => saveRules(rules.map(r => ({ ...r, enabled: true })))}
            className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400"
          >
            Enable all
          </button>
          <button
            onClick={() => saveRules(rules.map(r => ({ ...r, enabled: false })))}
            className="text-sm text-gray-600 hover:text-gray-700 dark:text-gray-400"
          >
            Disable all
          </button>
          <button
            onClick={() => {
              if (confirm('Remove all domain rules?')) {
                saveRules([]);
              }
            }}
            className="text-sm text-red-600 hover:text-red-700"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
}

export default PerDomainRules;
