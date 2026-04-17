import React from 'react';
import type { ProtectionLevel as Level } from '@/types';

interface Props {
  level: Level;
  onChange: (level: Level) => void;
  disabled?: boolean;
}

const LEVELS: { id: Level; label: string; color: string; hint: string }[] = [
  { id: 0, label: 'Off', color: 'var(--text-muted)', hint: 'No protection' },
  { id: 1, label: 'Low', color: 'var(--yellow)', hint: 'Headers & UA only' },
  { id: 2, label: 'Balanced', color: 'var(--green)', hint: 'All signals noised' },
  { id: 3, label: 'Strict', color: 'var(--red)', hint: 'Max protection' },
];

export default function ProtectionLevel({ level, onChange, disabled }: Props) {
  return (
    <div style={{ display: 'flex', gap: '6px', opacity: disabled ? 0.5 : 1 }}>
      {LEVELS.map((l) => {
        const active = level === l.id;
        return (
          <button
            key={l.id}
            onClick={() => !disabled && onChange(l.id)}
            disabled={disabled}
            style={{
              flex: 1,
              padding: '8px 4px 6px',
              borderRadius: '6px',
              textAlign: 'center',
              fontSize: '11px',
              fontWeight: 500,
              background: active ? l.color + '18' : 'var(--bg-elevated)',
              border: `1px solid ${active ? l.color + '40' : 'var(--border)'}`,
              color: active ? l.color : 'var(--text-muted)',
              cursor: disabled ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s',
            }}
          >
            <div>{l.label}</div>
            <div style={{ fontSize: '8px', marginTop: '2px', opacity: 0.7 }}>{l.hint}</div>
          </button>
        );
      })}
    </div>
  );
}
