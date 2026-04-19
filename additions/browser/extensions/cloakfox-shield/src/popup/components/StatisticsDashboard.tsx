import React, { useState, useEffect } from 'react';
import browser from 'webextension-polyfill';
import type { FingerprintSummary } from '@/types';
import { popupLogger } from '@/lib/logger';

/**
 * Statistics storage format
 */
interface StatisticsData {
  totalAccesses: number;
  totalBlocked: number;
  totalSpoofed: number;
  byCategory: Record<string, { count: number; blocked: number; spoofed: number }>;
  byDomain: Record<string, { count: number; blocked: number; spoofed: number }>;
  history: Array<{
    timestamp: number;
    accesses: number;
    blocked: number;
    spoofed: number;
  }>;
  lastUpdated: number;
}

/**
 * Default empty statistics
 */
const DEFAULT_STATISTICS: StatisticsData = {
  totalAccesses: 0,
  totalBlocked: 0,
  totalSpoofed: 0,
  byCategory: {},
  byDomain: {},
  history: [],
  lastUpdated: 0,
};

interface StatisticsDashboardProps {
  containerId: string | null;
}

/**
 * Component showing fingerprint protection statistics
 */
export default function StatisticsDashboard({ containerId }: StatisticsDashboardProps) {
  const [stats, setStats] = useState<StatisticsData>(DEFAULT_STATISTICS);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<'overview' | 'categories' | 'domains'>('overview');

  // Load statistics
  useEffect(() => {
    async function loadStats() {
      try {
        const key = containerId ? `statistics_${containerId}` : 'statistics_global';
        const result = await browser.storage.local.get(key);
        setStats((result[key] as StatisticsData | undefined) || DEFAULT_STATISTICS);
      } catch (error) {
        popupLogger.error('Failed to load statistics:', error);
      } finally {
        setLoading(false);
      }
    }

    loadStats();

    // Refresh every 5 seconds
    const interval = setInterval(loadStats, 5000);
    return () => clearInterval(interval);
  }, [containerId]);

  // Clear statistics
  const handleClear = async () => {
    try {
      const key = containerId ? `statistics_${containerId}` : 'statistics_global';
      await browser.storage.local.remove(key);
      setStats(DEFAULT_STATISTICS);
    } catch (error) {
      popupLogger.error('Failed to clear statistics:', error);
    }
  };

  // Format large numbers
  const formatNumber = (n: number): string => {
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
    return n.toString();
  };

  // Calculate protection rate
  const getProtectionRate = (): number => {
    if (stats.totalAccesses === 0) return 0;
    return Math.round(((stats.totalBlocked + stats.totalSpoofed) / stats.totalAccesses) * 100);
  };

  // Get top categories
  const getTopCategories = (limit: number = 5) => {
    return Object.entries(stats.byCategory)
      .sort(([, a], [, b]) => b.count - a.count)
      .slice(0, limit);
  };

  // Get top domains
  const getTopDomains = (limit: number = 5) => {
    return Object.entries(stats.byDomain)
      .sort(([, a], [, b]) => b.count - a.count)
      .slice(0, limit);
  };

  if (loading) {
    return (
      <div className="p-3 bg-gray-800 rounded-lg animate-pulse">
        <div className="h-24 bg-gray-700 rounded"></div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
          Statistics
        </h3>
        <button
          onClick={handleClear}
          className="text-xs text-gray-500 hover:text-gray-300"
        >
          Clear
        </button>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-4 gap-2">
        <div className="p-2 bg-gray-800 rounded-lg text-center">
          <div className="text-lg font-bold text-blue-400">
            {formatNumber(stats.totalAccesses)}
          </div>
          <div className="text-xs text-gray-500">Total</div>
        </div>
        <div className="p-2 bg-gray-800 rounded-lg text-center">
          <div className="text-lg font-bold text-red-400">
            {formatNumber(stats.totalBlocked)}
          </div>
          <div className="text-xs text-gray-500">Blocked</div>
        </div>
        <div className="p-2 bg-gray-800 rounded-lg text-center">
          <div className="text-lg font-bold text-yellow-400">
            {formatNumber(stats.totalSpoofed)}
          </div>
          <div className="text-xs text-gray-500">Spoofed</div>
        </div>
        <div className="p-2 bg-gray-800 rounded-lg text-center">
          <div className="text-lg font-bold text-green-400">
            {getProtectionRate()}%
          </div>
          <div className="text-xs text-gray-500">Protected</div>
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex gap-1 bg-gray-800 p-1 rounded-lg">
        {(['overview', 'categories', 'domains'] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`flex-1 py-1 text-xs rounded transition-colors capitalize ${
              view === v
                ? 'bg-gray-700 text-white'
                : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            {v}
          </button>
        ))}
      </div>

      {/* View Content */}
      <div className="bg-gray-800 rounded-lg p-3">
        {view === 'overview' && (
          <div className="space-y-3">
            {/* Protection Rate Bar */}
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-400">Protection Rate</span>
                <span className="text-green-400">{getProtectionRate()}%</span>
              </div>
              <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-green-500 to-green-400 transition-all"
                  style={{ width: `${getProtectionRate()}%` }}
                />
              </div>
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Categories tracked:</span>
                <span>{Object.keys(stats.byCategory).length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Domains tracked:</span>
                <span>{Object.keys(stats.byDomain).length}</span>
              </div>
            </div>

            {/* Last Updated */}
            {stats.lastUpdated > 0 && (
              <div className="text-xs text-gray-500 text-center">
                Last updated: {new Date(stats.lastUpdated).toLocaleTimeString()}
              </div>
            )}
          </div>
        )}

        {view === 'categories' && (
          <div className="space-y-2">
            {getTopCategories(8).length === 0 ? (
              <div className="text-center text-gray-500 text-sm py-4">
                No category data yet
              </div>
            ) : (
              getTopCategories(8).map(([category, data]) => (
                <div key={category} className="flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="truncate">{category}</span>
                      <span className="text-gray-500">{data.count}</span>
                    </div>
                    <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden flex">
                      <div
                        className="h-full bg-red-500"
                        style={{
                          width: `${(data.blocked / Math.max(data.count, 1)) * 100}%`,
                        }}
                      />
                      <div
                        className="h-full bg-yellow-500"
                        style={{
                          width: `${(data.spoofed / Math.max(data.count, 1)) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {view === 'domains' && (
          <div className="space-y-2">
            {getTopDomains(8).length === 0 ? (
              <div className="text-center text-gray-500 text-sm py-4">
                No domain data yet
              </div>
            ) : (
              getTopDomains(8).map(([domain, data]) => (
                <div key={domain} className="flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="truncate font-mono">{domain}</span>
                      <span className="text-gray-500">{data.count}</span>
                    </div>
                    <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden flex">
                      <div
                        className="h-full bg-red-500"
                        style={{
                          width: `${(data.blocked / Math.max(data.count, 1)) * 100}%`,
                        }}
                      />
                      <div
                        className="h-full bg-yellow-500"
                        style={{
                          width: `${(data.spoofed / Math.max(data.count, 1)) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex justify-center gap-4 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 bg-red-500 rounded-full"></div>
          <span className="text-gray-500">Blocked</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
          <span className="text-gray-500">Spoofed</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 bg-gray-600 rounded-full"></div>
          <span className="text-gray-500">Passed</span>
        </div>
      </div>
    </div>
  );
}
