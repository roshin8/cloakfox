import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import browser from 'webextension-polyfill';

interface ConflictParams {
  ip: string;
  domain: string;
  url: string;
  currentContainer: string;
  currentContainerId: string;
  originalContainer: string;
  originalContainerId: string;
  lastAccessed: string;
}

function IPWarningPage() {
  const [params, setParams] = useState<ConflictParams | null>(null);

  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    setParams({
      ip: sp.get('ip') || '',
      domain: sp.get('domain') || '',
      url: sp.get('url') || '',
      currentContainer: sp.get('currentContainer') || '',
      currentContainerId: sp.get('currentContainerId') || '',
      originalContainer: sp.get('originalContainer') || '',
      originalContainerId: sp.get('originalContainerId') || '',
      lastAccessed: sp.get('lastAccessed') || '',
    });
  }, []);

  const formatTimeAgo = (ts: string): string => {
    const diff = Date.now() - parseInt(ts, 10);
    const mins = Math.floor(diff / 60000);
    const hrs = Math.floor(mins / 60);
    const days = Math.floor(hrs / 24);
    if (days > 0) return `${days}d ago`;
    if (hrs > 0) return `${hrs}h ago`;
    if (mins > 0) return `${mins}m ago`;
    return 'just now';
  };

  const handleBlock = () => {
    // Go back or close tab
    if (window.history.length > 1) {
      window.history.back();
    } else {
      window.close();
    }
  };

  const handleAllowOnce = async () => {
    if (!params) return;
    // Tell background to allow this IP temporarily and record it
    await browser.runtime.sendMessage({
      type: 'IP_ALLOW_ONCE',
      ip: params.ip,
      url: params.url,
      containerId: params.currentContainerId,
      containerName: params.currentContainer,
    });
    // Navigate to original URL
    window.location.href = params.url;
  };

  const handleOpenInOriginal = async () => {
    if (!params) return;
    // Open in the original container
    try {
      await browser.tabs.create({
        url: params.url,
        cookieStoreId: params.originalContainerId,
      });
    } catch {
      // Fallback - just open normally
      window.open(params.url);
    }
    // Go back in current tab
    if (window.history.length > 1) window.history.back();
    else window.close();
  };

  if (!params) return null;

  return (
    <div style={{
      maxWidth: '480px', width: '100%',
      background: '#18181f', borderRadius: '12px',
      border: '1px solid #2a2a3e', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        background: '#d97706', padding: '16px 24px',
        display: 'flex', alignItems: 'center', gap: '12px',
      }}>
        <svg width="28" height="28" fill="none" stroke="white" viewBox="0 0 24 24" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: 'white' }}>IP Conflict Detected</div>
          <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.8)' }}>Request blocked until you decide</div>
        </div>
      </div>

      {/* Content */}
      <div style={{ padding: '20px 24px' }}>
        <p style={{ fontSize: '13px', color: '#9898b0', marginBottom: '16px' }}>
          <strong style={{ fontFamily: 'monospace', color: '#e8e8f0' }}>{params.domain}</strong> resolves to IP <strong style={{ fontFamily: 'monospace' }}>{params.ip}</strong> which was already used in another container.
        </p>

        <div style={{
          background: '#1f1f2b', borderRadius: '8px', padding: '12px 16px',
          marginBottom: '16px', fontSize: '13px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: '#606078' }}>You are in:</span>
            <span style={{ fontWeight: 600, color: '#7c5cfc' }}>{params.currentContainer}</span>
          </div>
          <div style={{ borderTop: '1px solid #2a2a3e', margin: '8px 0' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: '#606078' }}>Previously used by:</span>
            <span style={{ fontWeight: 600, color: '#f59e0b' }}>{params.originalContainer}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#606078' }}>Last access:</span>
            <span style={{ color: '#9898b0' }}>{formatTimeAgo(params.lastAccessed)}</span>
          </div>
        </div>

        <div style={{
          background: 'rgba(217,119,6,0.1)', border: '1px solid rgba(217,119,6,0.3)',
          borderRadius: '8px', padding: '12px 16px', fontSize: '12px',
          color: '#9898b0', lineHeight: '1.5',
        }}>
          <strong>Why this matters:</strong> The server at {params.domain} can see your IP address. If you visit from multiple containers, the server can link those visits together, defeating container isolation.
        </div>
      </div>

      {/* Actions */}
      <div style={{
        padding: '16px 24px', borderTop: '1px solid #2a2a3e',
        display: 'flex', gap: '8px',
      }}>
        <button onClick={handleBlock} style={{
          flex: 1, padding: '10px', borderRadius: '8px', fontWeight: 500, fontSize: '13px',
          background: '#1f1f2b', color: '#e8e8f0', border: '1px solid #2a2a3e',
          cursor: 'pointer',
        }}>
          Block
        </button>
        <button onClick={handleAllowOnce} style={{
          flex: 1, padding: '10px', borderRadius: '8px', fontWeight: 500, fontSize: '13px',
          background: '#d97706', color: 'white', border: 'none', cursor: 'pointer',
        }}>
          Allow Once
        </button>
        <button onClick={handleOpenInOriginal} style={{
          flex: 1, padding: '10px', borderRadius: '8px', fontWeight: 500, fontSize: '13px',
          background: '#7c5cfc', color: 'white', border: 'none', cursor: 'pointer',
        }}>
          Open in {params.originalContainer}
        </button>
      </div>
    </div>
  );
}

const container = document.getElementById('root');
if (container) {
  createRoot(container).render(<IPWarningPage />);
}
