import { useEffect, useState, useCallback } from 'react';
import browser from 'webextension-polyfill';
import type { ContainerSettings, AssignedProfileData } from '@/types';
import ProtectionLevel from '../ProtectionLevel';
import FingerprintMonitor from '../FingerprintMonitor';
import { PROTECTION_PRESETS, PROTECTION_DESCRIPTIONS } from '@/lib/protection-presets';
import { countByType } from '@/popup/data/signal-types';

interface CollisionResult {
  container1: { id: string; name: string };
  container2: { id: string; name: string };
  score: number;
  matches: string[];
}

interface DashboardTabProps {
  settings: ContainerSettings;
  onSaveSettings: (updates: Partial<ContainerSettings>) => void;
  onEnableSpoofer: (settingPath: string) => void;
  onNavigateToSignal?: (category: string, signal: string) => void;
  currentContainerId?: string;
  assignedProfile?: AssignedProfileData;
}

function CollisionCard({ currentContainerId }: { currentContainerId?: string }) {
  const [collisions, setCollisions] = useState<CollisionResult[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [rerandomizing, setRerandomizing] = useState<string | null>(null);
  const [selectedContainer, setSelectedContainer] = useState<string | null>(null);

  const fetchCollisions = useCallback(() => {
    setLoading(true);
    browser.runtime.sendMessage({ type: 'CHECK_COLLISIONS' })
      .then((results) => {
        setCollisions(results as CollisionResult[] || []);
      })
      .catch(() => {
        setCollisions([]);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchCollisions();
  }, [fetchCollisions]);

  const handleRerandomize = useCallback(async (containerId: string) => {
    setRerandomizing(containerId);
    try {
      // Setting an empty profile config triggers re-generation with fresh randomness
      await browser.runtime.sendMessage({
        type: 'SET_SETTINGS',
        containerId,
        settings: {
          profile: {
            userAgent: '',
            platform: '',
            screen: null,
            language: '',
            timezone: '',
            hardwareConcurrency: 0,
            deviceMemory: 0,
          },
        },
      });
      // Re-check collisions after re-randomizing
      setTimeout(fetchCollisions, 300);
    } catch {
      // ignore
    } finally {
      setRerandomizing(null);
    }
  }, [fetchCollisions]);

  const getIndicator = (score: number) => {
    if (score < 30) {
      return { symbol: '\u2713', color: 'var(--green)' };
    }
    if (score <= 60) {
      return { symbol: '\u26A0', color: 'var(--yellow)' };
    }
    return { symbol: '\u26A0', color: 'var(--red)' };
  };

  return (
    <div className="card">
      <div className="section-label">Container Similarity</div>
      {loading ? (
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', padding: '8px 0' }}>
          Checking containers...
        </div>
      ) : !collisions || collisions.length === 0 ? (
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', padding: '8px 0' }}>
          Not enough containers to compare.
        </div>
      ) : (
        <div>
          {(() => {
            // Build list of all containers
            const containers = new Map<string, string>();
            for (const c of collisions) {
              containers.set(c.container1.id, c.container1.name);
              containers.set(c.container2.id, c.container2.name);
            }

            // Current view: selected container or current container
            const viewId = selectedContainer || currentContainerId || containers.keys().next().value || '';

            // Get pairs for the viewed container
            const pairs = collisions
              .filter(c => c.container1.id === viewId || c.container2.id === viewId)
              .map(c => ({
                otherName: c.container1.id === viewId ? c.container2.name : c.container1.name,
                otherId: c.container1.id === viewId ? c.container2.id : c.container1.id,
                score: c.score,
                matches: c.matches,
              }))
              .sort((a, b) => b.score - a.score);

            return (
              <>
                {/* Container selector dropdown */}
                <select className="select" style={{ marginBottom: '8px', fontSize: '11px' }}
                  value={viewId}
                  onChange={(e) => setSelectedContainer(e.target.value)}>
                  {Array.from(containers.entries()).map(([id, name]) => (
                    <option key={id} value={id}>
                      {name}{id === currentContainerId ? ' (current)' : ''}
                    </option>
                  ))}
                </select>

                {/* Comparisons for selected container */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                  {pairs.length === 0 ? (
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', padding: '4px 0' }}>No other containers to compare.</div>
                  ) : pairs.map(({ otherName, otherId, score, matches }) => {
                    const { symbol, color: c } = getIndicator(score);
                    return (
                      <div key={otherId} style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '5px 8px', background: 'var(--bg-elevated)', borderRadius: '5px', fontSize: '11px',
                      }}>
                        <span style={{ color: 'var(--text-secondary)' }}>vs {otherName}</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span style={{ color: c, fontFamily: 'monospace', fontWeight: 600, fontSize: '10px' }}>{score}%</span>
                          <span style={{ color: c, fontSize: '12px' }}>{symbol}</span>
                          {score > 30 && matches.length > 0 && (
                            <span style={{ fontSize: '8px', color: 'var(--text-muted)', maxWidth: '80px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {matches.join(', ')}
                            </span>
                          )}
                          {score > 60 && (
                            <button onClick={() => handleRerandomize(otherId)}
                              disabled={rerandomizing === otherId}
                              style={{ background: 'none', border: '1px solid var(--border)', borderRadius: '3px', color: 'var(--text-muted)', fontSize: '8px', padding: '1px 4px', cursor: 'pointer' }}>
                              {rerandomizing === otherId ? '...' : 'Fix'}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}

export default function DashboardTab({
  settings, onSaveSettings, onEnableSpoofer, onNavigateToSignal, currentContainerId, assignedProfile,
}: DashboardTabProps) {
  const signalCounts = countByType(settings.spoofers as unknown as Record<string, Record<string, string>>);

  const [stats, setStats] = useState<any>(null);
  useEffect(() => {
    browser.runtime.sendMessage({ type: 'GET_STATS' })
      .then(r => setStats(r)).catch(() => {});
  }, []);

  return (
    <div className="space-y-3">
      {/* Master Toggle */}
      <div className="card flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center"
            style={{ background: settings.enabled ? 'var(--green-muted)' : 'var(--bg-elevated)' }}>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}
              style={{ color: settings.enabled ? 'var(--green)' : 'var(--text-muted)' }}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            </svg>
          </div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 600 }}>
              {settings.enabled ? 'Protection Active' : 'Protection Off'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
              {settings.enabled ? `${signalCounts.core} Core · ${signalCounts.js} JS protected` : 'Click toggle to enable'}
            </div>
          </div>
        </div>
        <div className={`toggle ${settings.enabled ? 'on' : ''}`}
          onClick={() => onSaveSettings({ enabled: !settings.enabled })} />
      </div>

      {/* Protection Level */}
      <div className="card">
        <div className="section-label">Protection Level</div>
        <ProtectionLevel
          level={settings.protectionLevel}
          onChange={(level) => onSaveSettings({
            protectionLevel: level,
            spoofers: PROTECTION_PRESETS[level],
          })}
          disabled={!settings.enabled}
        />
        <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '6px' }}>
          {PROTECTION_DESCRIPTIONS[settings.protectionLevel]}
        </div>
      </div>

      {/* Active Profile Details */}
      <div className="card" style={{ padding: '10px 12px' }}>
        <div style={{ fontSize: '11px', fontWeight: 600, marginBottom: '8px', color: 'var(--text-primary)' }}>
          Active Spoofed Profile
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', fontSize: '11px' }}>
          {[
            { label: 'UA', value: assignedProfile?.userAgent?.name || 'Random' },
            { label: 'Platform', value: assignedProfile?.userAgent?.platformName || 'Auto' },
            { label: 'Screen', value: assignedProfile?.screen ? `${assignedProfile.screen.width}x${assignedProfile.screen.height}` : 'Auto' },
            { label: 'DPR', value: assignedProfile?.screen?.devicePixelRatio?.toString() || 'Auto' },
            { label: 'Language', value: assignedProfile?.languages?.[0] || 'Auto' },
            { label: 'Timezone', value: assignedProfile?.timezoneOffset !== undefined ? `UTC${assignedProfile.timezoneOffset <= 0 ? '+' : '-'}${Math.abs(assignedProfile.timezoneOffset / 60)}` : 'Auto' },
            { label: 'Cores', value: assignedProfile?.hardwareConcurrency?.toString() || 'Auto' },
            { label: 'RAM', value: assignedProfile?.deviceMemory ? `${assignedProfile.deviceMemory}GB` : 'Hidden' },
            { label: 'Browser', value: assignedProfile?.userAgent?.brands ? 'Chromium' : assignedProfile?.userAgent?.oscpu ? 'Firefox' : 'Auto' },
            { label: 'GPU', value: 'Spoofed' },
          ].map(({ label, value }) => (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>{label}</span>
              <span className="truncate" style={{ maxWidth: '120px', fontWeight: 500 }}>{value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Fingerprint Monitor */}
      <div className="card">
        <FingerprintMonitor
          onEnableSpoofer={onEnableSpoofer}
          onNavigateToSignal={onNavigateToSignal}
        />
      </div>

      {/* Container Similarity */}
      <CollisionCard currentContainerId={currentContainerId} />

      {/* Statistics */}
      {stats?.global && (
        <div className="card">
          <div className="section-label">Protection Statistics</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
            <div style={{ textAlign: 'center', padding: '8px', background: 'var(--bg-elevated)', borderRadius: '6px' }}>
              <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--green)' }}>{stats.global.totalSpoofed || 0}</div>
              <div style={{ fontSize: '9px', color: 'var(--text-muted)' }}>Spoofed</div>
            </div>
            <div style={{ textAlign: 'center', padding: '8px', background: 'var(--bg-elevated)', borderRadius: '6px' }}>
              <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--red)' }}>{stats.global.totalBlocked || 0}</div>
              <div style={{ fontSize: '9px', color: 'var(--text-muted)' }}>Blocked</div>
            </div>
            <div style={{ textAlign: 'center', padding: '8px', background: 'var(--bg-elevated)', borderRadius: '6px' }}>
              <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-secondary)' }}>{stats.global.totalAccesses || 0}</div>
              <div style={{ fontSize: '9px', color: 'var(--text-muted)' }}>Total</div>
            </div>
          </div>
          {stats.global.topDomains?.length > 0 && (
            <div style={{ marginTop: '8px' }}>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '4px' }}>Top Domains</div>
              {stats.global.topDomains.slice(0, 3).map((d: any) => (
                <div key={d.domain} style={{ fontSize: '11px', display: 'flex', justifyContent: 'space-between', padding: '2px 0', color: 'var(--text-secondary)' }}>
                  <span style={{ fontFamily: 'monospace' }}>{d.domain}</span>
                  <span>{d.accesses} accesses</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
