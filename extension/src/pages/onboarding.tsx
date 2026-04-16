import React from 'react';
import { createRoot } from 'react-dom/client';
import browser from 'webextension-polyfill';

/* ------------------------------------------------------------------ */
/*  Shared style helpers                                               */
/* ------------------------------------------------------------------ */

const PURPLE = '#7c5cfc';
const BG = '#111118';
const CARD_BG = '#18181f';
const CARD_BORDER = '#2a2a3e';
const MUTED = '#9898b0';
const DIM = '#606078';

const isMac = navigator.platform?.toUpperCase().includes('MAC');

const card: React.CSSProperties = {
  background: CARD_BG,
  border: `1px solid ${CARD_BORDER}`,
  borderRadius: '12px',
  padding: '24px',
  marginBottom: '24px',
};

/* ------------------------------------------------------------------ */
/*  Tiny SVG icons (inline so no external deps)                        */
/* ------------------------------------------------------------------ */

const Icon = ({ d, color = PURPLE, size = 28 }: { d: string; color?: string; size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8}
    strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

// Path data for each feature icon
const ICONS = {
  fingerprint: 'M12 2a10 10 0 0 1 10 10c0 5.52-4.48 10-10 10M12 2C6.48 2 2 6.48 2 12M2 12h2M12 2v2M12 8a4 4 0 0 1 4 4M12 6a6 6 0 0 1 6 6M12 12h.01',
  container: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16zM3.27 6.96 12 12.01l8.73-5.05M12 22.08V12',
  stealth: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  network: 'M12 22c5.52 0 10-4.48 10-10S17.52 2 12 2 2 6.48 2 12s4.48 10 10 10zM2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z',
  rotate: 'M1 4v6h6M23 20v-6h-6M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4-4.64 4.36A9 9 0 0 1 3.51 15',
  profile: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  lock: 'M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2zM7 11V7a5 5 0 0 1 10 0v4',
  keyboard: 'M2 6h20v12H2zM6 10h.01M10 10h.01M14 10h.01M18 10h.01M8 14h8',
  zap: 'M13 2 3 14h9l-1 8 10-12h-9l1-8z',
};

/* ------------------------------------------------------------------ */
/*  Feature card component                                             */
/* ------------------------------------------------------------------ */

function FeatureCard({ icon, title, children }: { icon: string; title: string; children: React.ReactNode }) {
  return (
    <div style={{
      ...card,
      display: 'flex',
      gap: '16px',
      alignItems: 'flex-start',
    }}>
      <div style={{
        width: '44px', height: '44px', borderRadius: '10px',
        background: `${PURPLE}18`, display: 'flex',
        alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <Icon d={icon} size={22} />
      </div>
      <div style={{ flex: 1 }}>
        <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '6px', color: '#e8e8f0' }}>{title}</h3>
        <div style={{ fontSize: '13px', lineHeight: '1.65', color: MUTED }}>{children}</div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Protection level pill                                              */
/* ------------------------------------------------------------------ */

function LevelPill({ name, color, desc }: { name: string; color: string; desc: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'baseline', gap: '10px', marginBottom: '10px',
    }}>
      <span style={{
        display: 'inline-block', minWidth: '72px', textAlign: 'center',
        padding: '3px 10px', borderRadius: '6px', fontSize: '12px', fontWeight: 600,
        background: `${color}22`, color, border: `1px solid ${color}44`,
      }}>
        {name}
      </span>
      <span style={{ fontSize: '13px', color: MUTED }}>{desc}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Shortcut row                                                       */
/* ------------------------------------------------------------------ */

function Shortcut({ label, win, mac }: { label: string; win: string; mac: string }) {
  const keys = isMac ? mac : win;
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '8px 0', borderBottom: `1px solid ${CARD_BORDER}`,
    }}>
      <span style={{ fontSize: '13px', color: MUTED }}>{label}</span>
      <kbd style={{
        fontFamily: 'SFMono-Regular, Menlo, monospace', fontSize: '12px',
        background: '#1f1f2b', border: `1px solid ${CARD_BORDER}`,
        borderRadius: '6px', padding: '3px 10px', color: '#c8c8d8',
      }}>
        {keys}
      </kbd>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Quick-start step                                                   */
/* ------------------------------------------------------------------ */

function Step({ num, children }: { num: number; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-start', marginBottom: '14px' }}>
      <span style={{
        width: '26px', height: '26px', borderRadius: '50%', background: PURPLE,
        color: '#fff', fontWeight: 700, fontSize: '13px',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        {num}
      </span>
      <span style={{ fontSize: '13px', lineHeight: '1.6', color: MUTED, paddingTop: '2px' }}>{children}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */

function OnboardingPage() {
  const handleGetStarted = async () => {
    await browser.storage.local.set({ onboardingComplete: true });
    window.close();
  };

  return (
    <div style={{
      maxWidth: '700px', margin: '0 auto', padding: '48px 24px 64px',
    }}>
      {/* Hero */}
      <div style={{ textAlign: 'center', marginBottom: '48px' }}>
        <img src="../icons/icon-96.svg" alt="Cloakfox Shield" style={{ width: '80px', height: '80px', marginBottom: '20px' }} />
        <h1 style={{
          fontSize: '32px', fontWeight: 700, marginBottom: '12px',
          background: `linear-gradient(135deg, ${PURPLE}, #a78bfa)`,
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        }}>
          Welcome to Cloakfox Shield
        </h1>
        <p style={{ fontSize: '16px', color: MUTED, maxWidth: '520px', margin: '0 auto', lineHeight: '1.6' }}>
          Per-container fingerprint spoofing and privacy protection for Firefox Multi-Account Containers.
          Each container gets a unique, consistent browser identity that cannot be linked across sessions.
        </p>
      </div>

      {/* Section: What it does */}
      <h2 style={sectionHeading}>What Cloakfox Shield Does</h2>
      <div style={{ ...card, fontSize: '13px', lineHeight: '1.7', color: MUTED }}>
        <p>
          Websites use dozens of subtle signals -- canvas rendering, WebGL parameters, audio processing,
          installed fonts, screen dimensions, and more -- to build a unique "fingerprint" of your browser.
          This fingerprint persists even when you clear cookies.
        </p>
        <p style={{ marginTop: '12px' }}>
          Cloakfox Shield intercepts <strong style={{ color: '#e8e8f0' }}>50+ fingerprinting APIs</strong> and
          returns spoofed values that are unique to each Firefox container. The result: every container looks
          like a completely different browser to tracking scripts, while websites continue to work normally.
        </p>
      </div>

      {/* Section: Key Features */}
      <h2 style={sectionHeading}>Key Features</h2>

      <FeatureCard icon={ICONS.fingerprint} title="50+ Fingerprint Signals Spoofed">
        Canvas, WebGL, AudioContext, fonts, screen resolution, DOMRect, SVG, TextMetrics, device memory,
        hardware concurrency, battery status, media devices, timezone, performance timing, and more.
      </FeatureCard>

      <FeatureCard icon={ICONS.container} title="Per-Container Unique Identity">
        Each Firefox container receives a deterministic but unique fingerprint derived from the container ID.
        Your "Work" and "Shopping" containers will appear as two completely different browsers.
      </FeatureCard>

      <FeatureCard icon={ICONS.stealth} title="Stealth Mode">
        Spoofed values are designed to be internally consistent and realistic. Cloakfox Shield passes
        detection checks on CreepJS, fingerprint.com, BrowserLeaks, and other audit tools.
      </FeatureCard>

      <FeatureCard icon={ICONS.network} title="IP Conflict Detection">
        When a tracked domain sees the same IP address from two different containers, Cloakfox Shield
        shows a warning before the request completes, preventing cross-container linkage.
      </FeatureCard>

      <FeatureCard icon={ICONS.rotate} title="Auto-Rotation">
        Optionally rotate your fingerprint on a schedule (hourly, daily, or weekly) to make long-term
        tracking even harder without any manual intervention.
      </FeatureCard>

      <FeatureCard icon={ICONS.profile} title="Profile-Based Spoofing">
        Choose from real browser profiles (Chrome on Windows, Safari on macOS, etc.) so your spoofed
        identity is consistent and plausible. User-Agent, platform, and hardware signals all match.
      </FeatureCard>

      {/* Section: Quick Start */}
      <h2 style={sectionHeading}>Quick Start</h2>
      <div style={card}>
        <Step num={1}>
          Click the <strong style={{ color: '#e8e8f0' }}>Cloakfox Shield icon</strong> in your toolbar to open the popup.
        </Step>
        <Step num={2}>
          Protection is <strong style={{ color: '#e8e8f0' }}>ON by default</strong> in Balanced mode -- no setup required.
        </Step>
        <Step num={3}>
          Use the <strong style={{ color: '#e8e8f0' }}>Profile</strong> tab to customize your browser identity (OS, browser, locale).
        </Step>
        <Step num={4}>
          Use the <strong style={{ color: '#e8e8f0' }}>Signals</strong> tab for granular control over individual spoofing categories.
        </Step>
        <Step num={5}>
          Add domains to IP tracking in the <strong style={{ color: '#e8e8f0' }}>Rules</strong> tab to enable conflict detection.
        </Step>
      </div>

      {/* Section: Protection Levels */}
      <h2 style={sectionHeading}>Protection Levels</h2>
      <div style={card}>
        <LevelPill name="Off" color="#64748b" desc="No spoofing. Fingerprinting APIs return real values." />
        <LevelPill name="Low" color="#22c55e" desc="Light noise added. Minimal risk of site breakage." />
        <LevelPill name="Balanced" color={PURPLE} desc="Recommended. Strong protection while keeping sites functional." />
        <LevelPill name="Strict" color="#ef4444" desc="Maximum privacy. All signals fully randomized. Some sites may break." />
      </div>

      {/* Section: Keyboard Shortcuts */}
      <h2 style={sectionHeading}>Keyboard Shortcuts</h2>
      <div style={card}>
        <Shortcut label="Toggle protection" win="Alt + Shift + P" mac="Ctrl + Shift + P" />
        <Shortcut label="Rotate fingerprint" win="Alt + Shift + R" mac="Ctrl + Shift + R" />
        <Shortcut label="Toggle site exception" win="Alt + Shift + E" mac="Ctrl + Shift + E" />
        <Shortcut label="Open popup" win="Alt + Shift + C" mac="Ctrl + Shift + C" />
        <p style={{ fontSize: '11px', color: DIM, marginTop: '10px' }}>
          {isMac ? 'Showing macOS shortcuts. Ctrl refers to the Control key (not Cmd).' : 'Showing Windows/Linux shortcuts.'}
        </p>
      </div>

      {/* Section: Privacy */}
      <h2 style={sectionHeading}>Your Privacy</h2>
      <div style={{
        ...card,
        display: 'flex', gap: '16px', alignItems: 'flex-start',
      }}>
        <div style={{
          width: '44px', height: '44px', borderRadius: '10px',
          background: '#22c55e18', display: 'flex',
          alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <Icon d={ICONS.lock} size={22} color="#22c55e" />
        </div>
        <div style={{ flex: 1, fontSize: '13px', lineHeight: '1.65', color: MUTED }}>
          Cloakfox Shield is <strong style={{ color: '#e8e8f0' }}>100% local</strong>.
          No data is collected, no telemetry is sent, and no external servers are contacted.
          All fingerprint generation and spoofing happens entirely within your browser.
          The source code is open and auditable on{' '}
          <a href="https://github.com/roshin8/containershield" target="_blank" rel="noopener noreferrer"
            style={{ color: PURPLE, textDecoration: 'none' }}>
            GitHub
          </a>.
        </div>
      </div>

      {/* CTA */}
      <div style={{ textAlign: 'center', marginTop: '40px' }}>
        <button onClick={handleGetStarted} style={{
          padding: '14px 48px', fontSize: '16px', fontWeight: 600,
          background: PURPLE, color: '#fff', border: 'none',
          borderRadius: '10px', cursor: 'pointer',
          boxShadow: `0 4px 24px ${PURPLE}44`,
          transition: 'transform 0.15s, box-shadow 0.15s',
        }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = `0 8px 32px ${PURPLE}66`;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = `0 4px 24px ${PURPLE}44`;
          }}
        >
          Get Started
        </button>
        <p style={{ fontSize: '12px', color: DIM, marginTop: '12px' }}>
          This will close the onboarding tab and you can start browsing privately.
        </p>
      </div>

      {/* Footer */}
      <div style={{ textAlign: 'center', marginTop: '48px', fontSize: '12px', color: DIM }}>
        <p>
          Cloakfox Shield is open source.{' '}
          <a href="https://github.com/roshin8/containershield" target="_blank" rel="noopener noreferrer"
            style={{ color: PURPLE, textDecoration: 'none' }}>
            View on GitHub
          </a>
        </p>
      </div>
    </div>
  );
}

const sectionHeading: React.CSSProperties = {
  fontSize: '18px',
  fontWeight: 600,
  marginBottom: '16px',
  marginTop: '36px',
  color: '#e8e8f0',
  borderBottom: `1px solid ${CARD_BORDER}`,
  paddingBottom: '10px',
};

/* ------------------------------------------------------------------ */
/*  Mount                                                              */
/* ------------------------------------------------------------------ */

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(<OnboardingPage />);
}
