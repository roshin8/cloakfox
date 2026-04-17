import React from 'react';

export type TabId = 'dashboard' | 'fingerprint' | 'signals' | 'headers' | 'whitelist' | 'settings';

interface Tab {
  id: TabId;
  label: string;
  icon: React.ReactNode;
}

const iconProps = { className: 'w-[17px] h-[17px]', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7 };

const TABS: Tab[] = [
  {
    id: 'dashboard',
    label: 'Home',
    icon: <svg {...iconProps} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955a1.126 1.126 0 011.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" /></svg>,
  },
  {
    id: 'fingerprint',
    label: 'Profile',
    icon: <svg {...iconProps} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>,
  },
  {
    id: 'signals',
    label: 'Signals',
    icon: <svg {...iconProps} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M7.864 4.243A7.5 7.5 0 0119.5 10.5c0 2.92-.556 5.709-1.568 8.268M5.742 6.364A7.465 7.465 0 004.5 10.5a48.667 48.667 0 00-1.152 8.235M14.835 17.488a41.433 41.433 0 00-.76-4.988M6.09 13.938a41.98 41.98 0 01.564-3.438m2.262 8.025a46.886 46.886 0 00-.577-5.025M12 10.5a2.25 2.25 0 10-4.5 0 2.25 2.25 0 004.5 0z" /></svg>,
  },
  {
    id: 'headers',
    label: 'Headers',
    icon: <svg {...iconProps} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" /></svg>,
  },
  {
    id: 'whitelist',
    label: 'Rules',
    icon: <svg {...iconProps} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: <svg {...iconProps} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>,
  },
];

interface TabNavigationProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  isDark: boolean;
  onToggleTheme: () => void;
}

export default function TabNavigation({ activeTab, onTabChange, isDark, onToggleTheme }: TabNavigationProps) {
  return (
    <nav className="flex flex-col w-[54px] min-w-[54px] items-center py-2 gap-0.5 justify-between"
      style={{ background: 'var(--bg-surface)', borderRight: '1px solid var(--border)' }}>
      <div className="flex flex-col items-center gap-0.5">
        {TABS.map((tab) => {
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              title={tab.label}
              className="relative flex flex-col items-center justify-center w-[42px] h-[38px] rounded-md transition-all duration-150"
              style={{
                color: active ? 'var(--accent)' : 'var(--text-muted)',
                background: active ? 'var(--accent-muted)' : 'transparent',
              }}
              onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = 'var(--bg-hover)'; }}
              onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent'; }}
            >
              {tab.icon}
              <span style={{ fontSize: '8px', marginTop: '1px', fontWeight: 500, letterSpacing: '0.01em' }}>
                {tab.label}
              </span>
              {active && (
                <div className="absolute left-0 top-2 bottom-2 w-[2px] rounded-r" style={{ background: 'var(--accent)' }} />
              )}
            </button>
          );
        })}
      </div>

      {/* Theme toggle at bottom */}
      <button
        onClick={onToggleTheme}
        title={isDark ? 'Light mode' : 'Dark mode'}
        className="flex items-center justify-center w-[34px] h-[34px] rounded-md transition-all"
        style={{ color: 'var(--text-muted)' }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
      >
        {isDark ? (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.7}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.7}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
          </svg>
        )}
      </button>
    </nav>
  );
}
