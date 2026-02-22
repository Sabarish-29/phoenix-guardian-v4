/**
 * Application header/navigation component — V5 dark design system.
 */

import React from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { useTheme } from '../hooks/useTheme';
import { useLanguage } from '../context/LanguageContext';
import { useConnectivity } from '../hooks/useConnectivity';
import ConnectivityBadge from './ConnectivityBadge';
import logoImg from '../assets/logo.png';

export const Header: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, user, logout, getFullName, canCreateEncounters } = useAuthStore();
  const { toggle, isDark } = useTheme();
  const { language, setLanguage } = useLanguage();
  const connectivity = useConnectivity();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const headerStyle: React.CSSProperties = {
    background: 'var(--bg-base)',
    borderBottom: '1px solid var(--border-muted)',
    position: 'sticky',
    top: 0,
    zIndex: 100,
    backdropFilter: 'blur(12px)',
  };

  const innerStyle: React.CSSProperties = {
    maxWidth: '1280px',
    margin: '0 auto',
    padding: '0 24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: '60px',
    gap: '24px',
  };

  if (!isAuthenticated) {
    return (
      <header style={headerStyle}>
        <div style={innerStyle}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '10px', textDecoration: 'none' }}>
            <img src={logoImg} alt="Phoenix Guardian" style={{ height: 36, width: 36, objectFit: 'contain' }} />
            <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.1rem', color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
              Phoenix Guardian
            </span>
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              onClick={toggle}
              title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: 34, height: 34, borderRadius: 'var(--radius-md)',
                background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
                border: '1px solid var(--border-muted)',
                cursor: 'pointer', fontSize: '1rem', transition: 'all 0.2s ease',
              }}
            >
              {isDark ? '☀️' : '🌙'}
            </button>
            <Link to="/login" className="btn-primary" style={{ textDecoration: 'none' }}>
              Sign In
            </Link>
          </div>
        </div>
      </header>
    );
  }

  return (
    <header style={headerStyle}>
      <div style={innerStyle}>

        {/* Logo */}
        <Link
          to={user?.role === 'admin' ? '/admin' : '/v5-dashboard'}
          style={{ display: 'flex', alignItems: 'center', gap: '10px', textDecoration: 'none', flexShrink: 0 }}
        >
          <img src={logoImg} alt="Phoenix Guardian" style={{ height: 36, width: 36, objectFit: 'contain' }} />
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
            <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
              Phoenix Guardian
            </span>
          </div>
          <ConnectivityBadge mode={connectivity.mode} />
        </Link>

        {/* Navigation */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '4px', flex: 1 }}>
          {user?.role === 'admin' ? (
            <>
              {[
                { to: '/admin', label: 'Home' },
                { to: '/admin/security', label: '🛡️ Security', color: '#f87171' },
                { to: '/admin/reports', label: 'Reports' },
                { to: '/admin/users', label: 'Users' },
                { to: '/admin/audit-logs', label: 'Audit Logs' },
              ].map(({ to, label, color }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/admin'}
                  style={({ isActive }) => ({
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 12px',
                    borderRadius: 'var(--radius-md)',
                    textDecoration: 'none',
                    fontSize: '0.82rem',
                    fontWeight: isActive ? 600 : 500,
                    color: isActive ? (color || 'var(--text-primary)') : (color || 'var(--text-secondary)'),
                    background: isActive ? 'var(--bg-elevated)' : 'transparent',
                    borderBottom: isActive ? `2px solid ${color || 'var(--border-active)'}` : '2px solid transparent',
                    transition: 'all 0.15s ease',
                  })}
                >
                  {label}
                </NavLink>
              ))}
            </>
          ) : (
            <>
              {/* V5 Dashboard — primary */}
              <NavLink
                to="/v5-dashboard"
                style={({ isActive }) => ({
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-md)',
                  textDecoration: 'none',
                  fontSize: '0.82rem',
                  fontWeight: isActive ? 700 : 600,
                  color: isActive ? '#34d399' : 'var(--text-secondary)',
                  background: isActive ? 'rgba(16,185,129,0.08)' : 'transparent',
                  borderBottom: isActive ? '2px solid #34d399' : '2px solid transparent',
                  transition: 'all 0.15s ease',
                })}
              >
                🛡️ <span>V5</span>
                <span className="dot-live" style={{ width: 6, height: 6 }} />
              </NavLink>

              {/* Legacy */}
              <NavLink
                to="/dashboard"
                style={({ isActive }) => ({
                  display: 'inline-flex',
                  alignItems: 'center',
                  padding: '6px 10px',
                  borderRadius: 'var(--radius-md)',
                  textDecoration: 'none',
                  fontSize: '0.8rem',
                  fontWeight: 500,
                  color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                  background: isActive ? 'var(--bg-elevated)' : 'transparent',
                  borderBottom: isActive ? '2px solid var(--border-active)' : '2px solid transparent',
                  transition: 'all 0.15s ease',
                })}
              >
                Legacy
              </NavLink>

              {canCreateEncounters() && (
                <NavLink
                  to="/encounters/new"
                  style={({ isActive }) => ({
                    display: 'inline-flex',
                    alignItems: 'center',
                    padding: '6px 10px',
                    borderRadius: 'var(--radius-md)',
                    textDecoration: 'none',
                    fontSize: '0.8rem',
                    fontWeight: 500,
                    color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                    background: isActive ? 'var(--bg-elevated)' : 'transparent',
                    borderBottom: isActive ? '2px solid var(--border-active)' : '2px solid transparent',
                    transition: 'all 0.15s ease',
                  })}
                >
                  + Encounter
                </NavLink>
              )}

              {/* Treatment Shadow — purple */}
              <NavLink
                to="/treatment-shadow"
                style={({ isActive }) => ({
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-md)',
                  textDecoration: 'none',
                  fontSize: '0.82rem',
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? 'var(--shadow-primary)' : 'var(--text-secondary)',
                  background: isActive ? 'var(--shadow-glow)' : 'transparent',
                  borderBottom: isActive ? '2px solid var(--shadow-primary)' : '2px solid transparent',
                  transition: 'all 0.15s ease',
                })}
              >
                🟣 <span>Shadow</span>
                <span className="dot-live" style={{ width: 6, height: 6, background: 'var(--shadow-primary)', boxShadow: '0 0 6px var(--shadow-primary)' }} />
              </NavLink>

              {/* Silent Voice — cyan */}
              <NavLink
                to="/silent-voice"
                style={({ isActive }) => ({
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-md)',
                  textDecoration: 'none',
                  fontSize: '0.82rem',
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? 'var(--voice-primary)' : 'var(--text-secondary)',
                  background: isActive ? 'var(--voice-glow)' : 'transparent',
                  borderBottom: isActive ? '2px solid var(--voice-primary)' : '2px solid transparent',
                  transition: 'all 0.15s ease',
                })}
              >
                🔵 <span>Voice</span>
                <span className="dot-critical" style={{ width: 6, height: 6 }} />
              </NavLink>

              {/* Zebra Hunter — amber */}
              <NavLink
                to="/zebra-hunter"
                style={({ isActive }) => ({
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-md)',
                  textDecoration: 'none',
                  fontSize: '0.82rem',
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? 'var(--zebra-primary)' : 'var(--text-secondary)',
                  background: isActive ? 'var(--zebra-glow)' : 'transparent',
                  borderBottom: isActive ? '2px solid var(--zebra-primary)' : '2px solid transparent',
                  transition: 'all 0.15s ease',
                })}
              >
                🦓 <span>Zebra</span>
                <span className="dot-polling" style={{ width: 6, height: 6, background: 'var(--zebra-primary)' }} />
              </NavLink>
            </>
          )}
        </nav>

        {/* Language toggle + User menu */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
          {/* Language toggle */}
          <div style={{
            display: 'flex',
            background: 'rgba(255,255,255,0.06)',
            borderRadius: 6,
            padding: 2,
            gap: 2,
          }}>
            {(['en', 'hi'] as const).map(lang => (
              <button
                key={lang}
                onClick={() => setLanguage(lang)}
                style={{
                  padding: '4px 10px',
                  borderRadius: 4,
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  background: language === lang
                    ? 'rgba(59,130,246,0.8)'
                    : 'transparent',
                  color: language === lang ? '#fff' : '#8b9ab8',
                  transition: 'all 0.2s ease',
                }}
              >
                {lang === 'en' ? 'EN' : 'हिंदी'}
              </button>
            ))}
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>{getFullName()}</div>
            <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-label)' }}>{user?.role}</div>
          </div>

          {/* Theme toggle */}
          <button
            onClick={toggle}
            title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 34,
              height: 34,
              borderRadius: 'var(--radius-md)',
              background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
              border: '1px solid var(--border-muted)',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: '1rem',
              transition: 'all 0.2s ease',
              flexShrink: 0,
            }}
          >
            {isDark ? '☀️' : '🌙'}
          </button>

          <button
            onClick={handleLogout}
            title="Sign out"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 34,
              height: 34,
              borderRadius: 'var(--radius-md)',
              background: 'transparent',
              border: '1px solid var(--border-muted)',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--critical-border)';
              (e.currentTarget as HTMLButtonElement).style.color = 'var(--critical-text)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border-muted)';
              (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-muted)';
            }}
          >
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>

      </div>
    </header>
  );
};

export default Header;
