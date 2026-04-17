import React from 'react';
import { createRoot } from 'react-dom/client';
import browser from 'webextension-polyfill';

const ACCENT = '#e87e22';
const ACCENT_LIGHT = '#f5a623';
const BG = '#111118';
const CARD_BG = '#18181f';
const CARD_BORDER = '#2a2a3e';
const MUTED = '#9898b0';
const DIM = '#606078';
const GREEN = '#34d399';
const BLUE = '#60a5fa';

const isMac = navigator.platform?.toUpperCase().includes('MAC');

const card: React.CSSProperties = {
  background: CARD_BG,
  border: `1px solid ${CARD_BORDER}`,
  borderRadius: '12px',
  padding: '24px',
  marginBottom: '24px',
};

const sectionHeading: React.CSSProperties = {
  fontSize: '18px',
  fontWeight: 600,
  marginBottom: '16px',
  marginTop: '36px',
  color: '#e8e8f0',
  borderBottom: `1px solid ${CARD_BORDER}`,
  paddingBottom: '10px',
};

const Icon = ({ d, color = ACCENT, size = 28 }: { d: string; color?: string; size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8}
    strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

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
  cpu: 'M6 4h12v16H6zM14 4V2M10 4V2M14 20v2M10 20v2M2 10h2M2 14h2M20 10h2M20 14h2',
  layers: 'M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
};

function FeatureCard({ icon, title, children, badge }: { icon: string; title: string; children: React.ReactNode; badge?: { text: string; color: string } }) {
  return (
    <div style={{ ...card, display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
      <div style={{
        width: '44px', height: '44px', borderRadius: '10px',
        background: `${ACCENT}18`, display: 'flex',
        alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <Icon d={icon} size={22} />
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: '#e8e8f0' }}>{title}</h3>
          {badge && (
            <span style={{
              fontSize: '10px', fontWeight: 600, padding: '2px 8px', borderRadius: '4px',
              color: badge.color, background: `${badge.color}18`, border: `1px solid ${badge.color}33`,
            }}>{badge.text}</span>
          )}
        </div>
        <div style={{ fontSize: '13px', lineHeight: '1.65', color: MUTED }}>{children}</div>
      </div>
    </div>
  );
}

function LevelPill({ name, color, desc }: { name: string; color: string; desc: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px', marginBottom: '10px' }}>
      <span style={{
        display: 'inline-block', minWidth: '72px', textAlign: 'center',
        padding: '3px 10px', borderRadius: '6px', fontSize: '12px', fontWeight: 600,
        background: `${color}22`, color, border: `1px solid ${color}44`,
      }}>{name}</span>
      <span style={{ fontSize: '13px', color: MUTED }}>{desc}</span>
    </div>
  );
}

function Shortcut({ label, win, mac }: { label: string; win: string; mac: string }) {
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
      }}>{isMac ? mac : win}</kbd>
    </div>
  );
}

function Step({ num, children }: { num: number; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-start', marginBottom: '14px' }}>
      <span style={{
        width: '26px', height: '26px', borderRadius: '50%', background: ACCENT,
        color: '#fff', fontWeight: 700, fontSize: '13px',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>{num}</span>
      <span style={{ fontSize: '13px', lineHeight: '1.6', color: MUTED, paddingTop: '2px' }}>{children}</span>
    </div>
  );
}

function OnboardingPage() {
  const handleGetStarted = async () => {
    await browser.storage.local.set({ onboardingComplete: true });
    window.close();
  };

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto', padding: '48px 24px 64px' }}>
      {/* Hero */}
      <div style={{ textAlign: 'center', marginBottom: '48px' }}>
        <img src="../icons/icon-128.png" alt="Cloakfox Shield" style={{ width: '80px', height: '80px', marginBottom: '20px' }} />
        <h1 style={{
          fontSize: '32px', fontWeight: 700, marginBottom: '12px',
          background: `linear-gradient(135deg, ${ACCENT}, ${ACCENT_LIGHT})`,
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        }}>
          Welcome to Cloakfox Shield
        </h1>
        <p style={{ fontSize: '16px', color: MUTED, maxWidth: '520px', margin: '0 auto', lineHeight: '1.6' }}>
          Two layers of fingerprint protection — C++ engine-level spoofing and 50+ JavaScript API interceptors —
          with unique identities per container.
        </p>
      </div>

      {/* Section: How it works */}
      <h2 style={sectionHeading}>How Cloakfox Shield Works</h2>
      <div style={{ ...card, fontSize: '13px', lineHeight: '1.7', color: MUTED }}>
        <p>
          Websites use dozens of subtle signals — canvas rendering, WebGL parameters, audio processing,
          installed fonts, screen dimensions — to build a unique "fingerprint" that persists even when you clear cookies.
        </p>
        <p style={{ marginTop: '12px' }}>
          Cloakfox Shield uses a <strong style={{ color: '#e8e8f0' }}>two-layer approach</strong>:
        </p>
        <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
          <div style={{
            flex: 1, padding: '14px', borderRadius: '8px',
            background: `${GREEN}10`, border: `1px solid ${GREEN}25`,
          }}>
            <div style={{ fontSize: '12px', fontWeight: 600, color: GREEN, marginBottom: '6px' }}>
              Core Protection
            </div>
            <div style={{ fontSize: '12px', color: MUTED }}>
              17 signals spoofed at the <strong style={{ color: '#e8e8f0' }}>browser engine level</strong> (C++ patches).
              Completely undetectable — the browser natively returns spoofed values.
              Canvas, Audio, Navigator, Screen, Fonts, WebGL, WebRTC, Timezone, Speech.
            </div>
          </div>
          <div style={{
            flex: 1, padding: '14px', borderRadius: '8px',
            background: `${BLUE}10`, border: `1px solid ${BLUE}25`,
          }}>
            <div style={{ fontSize: '12px', fontWeight: 600, color: BLUE, marginBottom: '6px' }}>
              JS Protection
            </div>
            <div style={{ fontSize: '12px', color: MUTED }}>
              40+ additional signals spoofed via JavaScript API interception.
              Battery, CSS, Performance timing, Storage, Keyboard, Math, Workers, Devices, and more.
            </div>
          </div>
        </div>
      </div>

      {/* Section: Key Features */}
      <h2 style={sectionHeading}>Key Features</h2>

      <FeatureCard icon={ICONS.cpu} title="C++ Engine Integration" badge={{ text: 'Core', color: GREEN }}>
        Unlike JavaScript-only extensions, Cloakfox Shield hooks into the browser engine itself.
        Canvas noise is applied in the rendering pipeline, not after. Audio spoofing happens in the audio
        processing thread. These protections are invisible to fingerprinting detection scripts.
      </FeatureCard>

      <FeatureCard icon={ICONS.container} title="Per-Container Unique Identity">
        Each Firefox container receives a deterministic but unique fingerprint.
        Your "Work" and "Shopping" containers appear as completely different browsers to tracking scripts.
        Same container + same site = consistent identity across page loads.
      </FeatureCard>

      <FeatureCard icon={ICONS.layers} title="50+ Fingerprinting APIs Covered">
        Canvas, WebGL, AudioContext, fonts, screen resolution, DOMRect, SVG, TextMetrics, device memory,
        hardware concurrency, battery status, media devices, timezone, performance timing, keyboard layout,
        CSS media queries, storage estimation, and more.
      </FeatureCard>

      <FeatureCard icon={ICONS.stealth} title="Stealth & Consistency">
        Spoofed values are internally consistent — a Windows user agent gets Windows-appropriate screen sizes,
        GPU strings, and font lists. Passes detection checks on CreepJS, fingerprint.com, and BrowserLeaks.
      </FeatureCard>

      <FeatureCard icon={ICONS.network} title="IP Conflict Detection">
        When a tracked domain sees the same IP from two different containers, you get a warning
        before the request completes — preventing cross-container linkage via IP address.
      </FeatureCard>

      <FeatureCard icon={ICONS.rotate} title="Profile Rotation">
        Rotate your fingerprint on demand or automatically (per session, hourly, daily, weekly).
        Long-term tracking becomes impossible without any manual intervention.
      </FeatureCard>

      {/* Section: Quick Start */}
      <h2 style={sectionHeading}>Getting Started</h2>
      <div style={card}>
        <Step num={1}>
          Click the <strong style={{ color: '#e8e8f0' }}>Cloakfox Shield icon</strong> in your toolbar to open the control panel.
        </Step>
        <Step num={2}>
          Protection is <strong style={{ color: '#e8e8f0' }}>ON by default</strong> in Balanced mode — no setup needed.
        </Step>
        <Step num={3}>
          Open different <strong style={{ color: '#e8e8f0' }}>Container Tabs</strong> (File → New Container Tab) — each gets a unique fingerprint automatically.
        </Step>
        <Step num={4}>
          Use the <strong style={{ color: '#e8e8f0' }}>Signals</strong> tab for granular control. Signals marked
          <span style={{ fontSize: '10px', fontWeight: 600, padding: '1px 6px', borderRadius: '3px', color: GREEN, background: `${GREEN}18`, margin: '0 4px' }}>Core</span>
          are engine-level,
          <span style={{ fontSize: '10px', fontWeight: 600, padding: '1px 6px', borderRadius: '3px', color: BLUE, background: `${BLUE}18`, margin: '0 4px' }}>JS</span>
          are extension-level.
        </Step>
        <Step num={5}>
          Visit <a href="https://browserleaks.com" target="_blank" rel="noopener noreferrer" style={{ color: ACCENT, textDecoration: 'none' }}>browserleaks.com</a> or
          {' '}<a href="https://creepjs.com" target="_blank" rel="noopener noreferrer" style={{ color: ACCENT, textDecoration: 'none' }}>creepjs.com</a> to verify your fingerprint is unique.
        </Step>
      </div>

      {/* Section: Protection Levels */}
      <h2 style={sectionHeading}>Protection Levels</h2>
      <div style={card}>
        <LevelPill name="Off" color="#64748b" desc="No spoofing. Real values returned." />
        <LevelPill name="Low" color="#22c55e" desc="Light noise. Minimal site breakage." />
        <LevelPill name="Balanced" color={ACCENT} desc="Recommended. Strong protection, sites work normally." />
        <LevelPill name="Strict" color="#ef4444" desc="Maximum privacy. Some sites may break." />
      </div>

      {/* Section: Keyboard Shortcuts */}
      <h2 style={sectionHeading}>Keyboard Shortcuts</h2>
      <div style={card}>
        <Shortcut label="Toggle protection" win="Alt + Shift + P" mac="Ctrl + Shift + P" />
        <Shortcut label="Rotate fingerprint" win="Alt + Shift + R" mac="Ctrl + Shift + R" />
        <Shortcut label="Toggle site exception" win="Alt + Shift + E" mac="Ctrl + Shift + E" />
        <Shortcut label="Open popup" win="Alt + Shift + C" mac="Ctrl + Shift + C" />
        <p style={{ fontSize: '11px', color: DIM, marginTop: '10px' }}>
          {isMac ? 'Ctrl refers to the Control key, not Cmd.' : 'Showing Windows/Linux shortcuts.'}
        </p>
      </div>

      {/* Section: Privacy */}
      <h2 style={sectionHeading}>Your Privacy</h2>
      <div style={{ ...card, display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
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
          All fingerprint generation happens entirely within your browser.
          Source code is open and auditable on{' '}
          <a href="https://github.com/roshin8/cloakfox" target="_blank" rel="noopener noreferrer"
            style={{ color: ACCENT, textDecoration: 'none' }}>GitHub</a>.
        </div>
      </div>

      {/* CTA */}
      <div style={{ textAlign: 'center', marginTop: '40px' }}>
        <button onClick={handleGetStarted} style={{
          padding: '14px 48px', fontSize: '16px', fontWeight: 600,
          background: ACCENT, color: '#fff', border: 'none',
          borderRadius: '10px', cursor: 'pointer',
          boxShadow: `0 4px 24px ${ACCENT}44`,
          transition: 'transform 0.15s, box-shadow 0.15s',
        }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = `0 8px 32px ${ACCENT}66`;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = `0 4px 24px ${ACCENT}44`;
          }}
        >
          Get Started
        </button>
        <p style={{ fontSize: '12px', color: DIM, marginTop: '12px' }}>
          Protection is already active. This closes the onboarding tab.
        </p>
      </div>

      {/* Footer */}
      <div style={{ textAlign: 'center', marginTop: '48px', fontSize: '12px', color: DIM }}>
        Cloakfox Shield · Open Source ·{' '}
        <a href="https://github.com/roshin8/cloakfox" target="_blank" rel="noopener noreferrer"
          style={{ color: ACCENT, textDecoration: 'none' }}>GitHub</a>
      </div>
    </div>
  );
}

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(<OnboardingPage />);
}
