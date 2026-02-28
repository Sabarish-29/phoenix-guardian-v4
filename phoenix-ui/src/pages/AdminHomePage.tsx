/**
 * Admin Home Page — Landing page for admin users.
 *
 * Shows security overview metrics, recent events, and quick action cards.
 * Admins are explicitly separated from clinical workflows per HIPAA
 * minimum necessary principle — no patient encounters or SOAP generation.
 *
 * Uses CSS custom-property design tokens so both dark and light themes render correctly.
 */

import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '../api/client';
import { useAuthStore } from '../stores/authStore';

interface SystemMetrics {
  total_events: number;
  blocked: number;
  block_rate: number;
  honeytoken_triggers: number;
  active_attackers: number;
  avg_detection_time_ms: number;
}

interface SecurityEvent {
  id: string;
  timestamp: string;
  threat_type: string;
  severity: string;
  status: string;
  detection_time_ms: number;
  agent: string;
}

/* ── Severity palette using design-system tokens ── */
const SEVERITY_STYLE: Record<string, React.CSSProperties> = {
  CRITICAL: { background: 'var(--critical-bg)', color: 'var(--critical-text)', border: '1px solid var(--critical-border)' },
  HIGH:     { background: 'var(--warning-bg)',  color: 'var(--warning-text)',  border: '1px solid var(--warning-border)' },
  MEDIUM:   { background: 'var(--watching-bg)', color: 'var(--watching-text)', border: '1px solid var(--watching-border)' },
  LOW:      { background: 'var(--success-bg)',  color: 'var(--success-text)',  border: '1px solid var(--success-border)' },
};

/* ── Quick-action card definitions ── */
const QUICK_ACTIONS = [
  { to: '/admin/security',    icon: '🛡️', title: 'Security Console',   desc: 'Real-time threat monitoring & PQC status',        accent: 'var(--voice-primary)' },
  { to: '/admin/reports',     icon: '📊', title: 'Security Reports',   desc: 'Export audit logs & compliance reports',            accent: 'var(--shadow-primary)' },
  { to: '/admin/users',       icon: '👥', title: 'User Management',    desc: 'Manage roles & permissions',                       accent: 'var(--zebra-primary)' },
  { to: '/admin/audit-logs',  icon: '📋', title: 'Audit Logs',         desc: 'HIPAA-compliant audit trail',                      accent: 'var(--watching-text)' },
];

export const AdminHomePage: React.FC = () => {
  const { getFullName } = useAuthStore();
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [recentEvents, setRecentEvents] = useState<SecurityEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [summaryRes, eventsRes] = await Promise.all([
          apiClient.get('/security-console/summary'),
          apiClient.get('/security-console/events?limit=10'),
        ]);
        setMetrics(summaryRes.data);
        setRecentEvents(eventsRes.data.events || []);
      } catch (err) {
        console.error('Failed to fetch admin metrics', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleTimeString('en-US', {
        hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    } catch { return iso; }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1
          className="text-2xl font-bold flex items-center gap-2"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
        >
          🛡️ Admin Control Center
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Welcome back, {getFullName()}. Security monitoring and system administration.
        </p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {QUICK_ACTIONS.map((a) => (
          <Link
            key={a.to}
            to={a.to}
            className="p-5 rounded-lg transition-all"
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderLeft: `3px solid ${a.accent}`,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--bg-elevated)';
              e.currentTarget.style.borderColor = 'var(--border-muted)';
              e.currentTarget.style.borderLeftColor = a.accent;
              e.currentTarget.style.boxShadow = 'var(--shadow-card)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'var(--bg-surface)';
              e.currentTarget.style.borderColor = 'var(--border-subtle)';
              e.currentTarget.style.borderLeftColor = a.accent;
              e.currentTarget.style.boxShadow = 'none';
            }}
          >
            <div className="text-3xl mb-2">{a.icon}</div>
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>{a.title}</h3>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{a.desc}</p>
          </Link>
        ))}
      </div>

      {/* System Overview */}
      <div className="pg-card" style={{ padding: '20px' }}>
        <h2
          className="text-lg font-semibold mb-4"
          style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
        >
          System Overview
        </h2>
        {loading ? (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading metrics…</p>
        ) : metrics ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <MetricTile icon="🚨" label="Threats Detected" value={metrics.total_events} accent="var(--critical-text)" />
            <MetricTile icon="🛡️" label="Blocked" value={metrics.blocked} accent="var(--voice-primary)" />
            <MetricTile icon="📈" label="Block Rate" value={`${metrics.block_rate.toFixed(1)}%`} accent="var(--success-text)" />
            <MetricTile icon="👤" label="Attackers Tracked" value={metrics.active_attackers} accent="var(--shadow-primary)" />
            <MetricTile icon="🍯" label="Honeytoken Hits" value={metrics.honeytoken_triggers} accent="var(--zebra-primary)" />
            <MetricTile icon="⚡" label="Avg Detection" value={`${metrics.avg_detection_time_ms.toFixed(0)}ms`} accent="var(--watching-text)" />
          </div>
        ) : (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Metrics unavailable</p>
        )}
      </div>

      {/* Recent Security Events */}
      <div className="pg-card" style={{ padding: '20px' }}>
        <div className="flex items-center justify-between mb-4">
          <h2
            className="text-lg font-semibold"
            style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
          >
            Recent Security Events
          </h2>
          <Link
            to="/admin/security"
            className="text-sm font-medium"
            style={{ color: 'var(--voice-primary)' }}
          >
            View All →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                {['Time', 'Severity', 'Threat Type', 'Agent', 'Status', ''].map((h, i) => (
                  <th
                    key={h || 'det'}
                    className={`pb-2 ${i < 5 ? 'pr-4 text-left' : 'text-right'} text-xs uppercase`}
                    style={{ color: 'var(--text-label)', letterSpacing: '0.08em', fontWeight: 600 }}
                  >
                    {h || 'Detection'}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recentEvents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-6" style={{ color: 'var(--text-muted)' }}>
                    No events recorded
                  </td>
                </tr>
              ) : (
                recentEvents.map((ev) => (
                  <tr
                    key={ev.id}
                    className="transition-colors"
                    style={{ borderBottom: '1px solid var(--border-subtle)' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-elevated)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <td className="py-2 pr-4 font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {formatTime(ev.timestamp)}
                    </td>
                    <td className="py-2 pr-4">
                      <span
                        className="inline-block px-2 py-0.5 rounded text-xs font-semibold"
                        style={SEVERITY_STYLE[ev.severity] || SEVERITY_STYLE.LOW}
                      >
                        {ev.severity}
                      </span>
                    </td>
                    <td className="py-2 pr-4 font-mono text-xs" style={{ color: 'var(--text-primary)' }}>
                      {ev.threat_type}
                    </td>
                    <td className="py-2 pr-4 text-xs" style={{ color: 'var(--text-muted)' }}>
                      {ev.agent}
                    </td>
                    <td className="py-2 pr-4">
                      <span
                        className="inline-block px-2 py-0.5 rounded text-xs font-semibold"
                        style={SEVERITY_STYLE.CRITICAL}
                      >
                        {ev.status}
                      </span>
                    </td>
                    <td className="py-2 text-right font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {ev.detection_time_ms.toFixed(1)}ms
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Admin Role Notice */}
      <div
        className="rounded-lg p-4 flex items-start gap-3"
        style={{
          background: 'var(--warning-bg)',
          border: '1px solid var(--warning-border)',
        }}
      >
        <span className="text-xl mt-0.5">⚠️</span>
        <div>
          <h3 className="font-semibold text-sm" style={{ color: 'var(--warning-text)' }}>
            Admin Role Notice
          </h3>
          <p className="text-xs mt-1 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            Your role is limited to security monitoring and system administration.
            Clinical operations (patient encounters, SOAP generation, prescriptions)
            are restricted to physician and nurse roles per HIPAA minimum necessary principle
            (45 CFR §164.502(b)).
          </p>
        </div>
      </div>
    </div>
  );
};

/**
 * Small metric tile for system overview — theme-aware via CSS variables.
 */
const MetricTile: React.FC<{ icon: string; label: string; value: string | number; accent: string }> = ({
  icon, label, value, accent,
}) => (
  <div
    className="p-3 rounded-lg"
    style={{
      background: 'var(--bg-elevated)',
      border: '1px solid var(--border-subtle)',
    }}
  >
    <div
      className="text-xl font-bold"
      style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}
    >
      {value}
    </div>
    <div className="text-xs mt-0.5" style={{ color: accent }}>
      {icon} {label}
    </div>
  </div>
);

export default AdminHomePage;
