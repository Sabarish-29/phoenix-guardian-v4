import React from 'react';

interface ConnectivityBadgeProps {
  mode: 'online' | 'degraded' | 'demo' | 'offline' | 'checking';
}

const CONFIG: Record<string, {
  dot: string;
  text: string;
  textColor: string;
  bg: string;
  border: string;
  subtext: string | null;
}> = {
  online: {
    dot: '#34d399',
    text: 'ONLINE',
    textColor: '#34d399',
    bg: 'rgba(16,185,129,0.08)',
    border: 'rgba(16,185,129,0.25)',
    subtext: null,
  },
  degraded: {
    dot: '#fbbf24',
    text: 'DEGRADED',
    textColor: '#fbbf24',
    bg: 'rgba(245,158,11,0.08)',
    border: 'rgba(245,158,11,0.25)',
    subtext: 'Some services unavailable',
  },
  demo: {
    dot: '#34d399',
    text: 'DEMO',
    textColor: '#34d399',
    bg: 'rgba(16,185,129,0.08)',
    border: 'rgba(16,185,129,0.25)',
    subtext: null,
  },
  offline: {
    dot: '#f87171',
    text: 'OFFLINE MODE',
    textColor: '#f87171',
    bg: 'rgba(239,68,68,0.08)',
    border: 'rgba(239,68,68,0.25)',
    subtext: 'Showing cached results',
  },
  checking: {
    dot: '#8b9ab8',
    text: 'CHECKING...',
    textColor: '#8b9ab8',
    bg: 'rgba(255,255,255,0.04)',
    border: 'rgba(255,255,255,0.1)',
    subtext: null,
  },
};

const ConnectivityBadge: React.FC<ConnectivityBadgeProps> = ({ mode }) => {
  const config = CONFIG[mode] || CONFIG.checking;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      padding: '4px 10px',
      background: config.bg,
      border: `1px solid ${config.border}`,
      borderRadius: 100,
      fontSize: '0.65rem',
      fontWeight: 700,
      letterSpacing: '0.06em',
    }}>
      <span style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: config.dot,
        display: 'inline-block',
        flexShrink: 0,
      }} />
      <span style={{ color: config.textColor }}>{config.text}</span>
      {config.subtext && (
        <span style={{ color: '#4a5568', fontWeight: 400 }}>
          — {config.subtext}
        </span>
      )}
    </div>
  );
};

export default ConnectivityBadge;
