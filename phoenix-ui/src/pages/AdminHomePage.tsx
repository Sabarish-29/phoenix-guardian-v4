/**
 * Admin Home Page — Landing page for admin users.
 *
 * Shows security overview metrics, recent events, and quick action cards.
 * Admins are explicitly separated from clinical workflows per HIPAA
 * minimum necessary principle — no patient encounters or SOAP generation.
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

const SEVERITY_BADGE: Record<string, string> = {
  CRITICAL: 'bg-red-100 text-red-700',
  HIGH: 'bg-amber-100 text-amber-700',
  MEDIUM: 'bg-yellow-100 text-yellow-700',
  LOW: 'bg-green-100 text-green-700',
};

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
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          🛡️ Admin Control Center
        </h1>
        <p className="text-gray-500 mt-1 text-sm">
          Welcome back, {getFullName()}. Security monitoring and system administration.
        </p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Link
          to="/admin/security"
          className="p-5 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 hover:shadow-md transition-all group"
        >
          <div className="text-3xl mb-2">🛡️</div>
          <h3 className="font-semibold text-gray-900 group-hover:text-blue-700">Security Console</h3>
          <p className="text-xs text-gray-500 mt-1">Real-time threat monitoring &amp; PQC status</p>
        </Link>

        <Link
          to="/admin/reports"
          className="p-5 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 hover:shadow-md transition-all group"
        >
          <div className="text-3xl mb-2">📊</div>
          <h3 className="font-semibold text-gray-900 group-hover:text-green-700">Security Reports</h3>
          <p className="text-xs text-gray-500 mt-1">Export audit logs &amp; compliance reports</p>
        </Link>

        <Link
          to="/admin/users"
          className="p-5 bg-purple-50 border border-purple-200 rounded-lg hover:bg-purple-100 hover:shadow-md transition-all group"
        >
          <div className="text-3xl mb-2">👥</div>
          <h3 className="font-semibold text-gray-900 group-hover:text-purple-700">User Management</h3>
          <p className="text-xs text-gray-500 mt-1">Manage roles &amp; permissions</p>
        </Link>

        <Link
          to="/admin/audit-logs"
          className="p-5 bg-amber-50 border border-amber-200 rounded-lg hover:bg-amber-100 hover:shadow-md transition-all group"
        >
          <div className="text-3xl mb-2">📋</div>
          <h3 className="font-semibold text-gray-900 group-hover:text-amber-700">Audit Logs</h3>
          <p className="text-xs text-gray-500 mt-1">HIPAA-compliant audit trail</p>
        </Link>
      </div>

      {/* System Overview */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">System Overview</h2>
        {loading ? (
          <p className="text-gray-400 text-sm">Loading metrics…</p>
        ) : metrics ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <MetricTile icon="🚨" label="Threats Detected" value={metrics.total_events} color="red" />
            <MetricTile icon="🛡️" label="Blocked" value={metrics.blocked} color="green" />
            <MetricTile icon="📈" label="Block Rate" value={`${metrics.block_rate.toFixed(1)}%`} color="green" />
            <MetricTile icon="👤" label="Attackers Tracked" value={metrics.active_attackers} color="amber" />
            <MetricTile icon="🍯" label="Honeytoken Hits" value={metrics.honeytoken_triggers} color="yellow" />
            <MetricTile icon="⚡" label="Avg Detection" value={`${metrics.avg_detection_time_ms.toFixed(0)}ms`} color="cyan" />
          </div>
        ) : (
          <p className="text-gray-400 text-sm">Metrics unavailable</p>
        )}
      </div>

      {/* Recent Security Events */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Security Events</h2>
          <Link to="/admin/security" className="text-sm text-blue-600 hover:text-blue-800 font-medium">
            View All →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-500 text-xs uppercase">
                <th className="pb-2 pr-4">Time</th>
                <th className="pb-2 pr-4">Severity</th>
                <th className="pb-2 pr-4">Threat Type</th>
                <th className="pb-2 pr-4">Agent</th>
                <th className="pb-2 pr-4">Status</th>
                <th className="pb-2 text-right">Detection</th>
              </tr>
            </thead>
            <tbody>
              {recentEvents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center text-gray-400 py-6">No events recorded</td>
                </tr>
              ) : (
                recentEvents.map((e) => (
                  <tr key={e.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 pr-4 text-gray-600 font-mono text-xs">{formatTime(e.timestamp)}</td>
                    <td className="py-2 pr-4">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${SEVERITY_BADGE[e.severity] || SEVERITY_BADGE.LOW}`}>
                        {e.severity}
                      </span>
                    </td>
                    <td className="py-2 pr-4 text-gray-800 font-mono text-xs">{e.threat_type}</td>
                    <td className="py-2 pr-4 text-gray-500 text-xs">{e.agent}</td>
                    <td className="py-2 pr-4">
                      <span className="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-700">
                        {e.status}
                      </span>
                    </td>
                    <td className="py-2 text-right text-gray-600 font-mono text-xs">{e.detection_time_ms.toFixed(1)}ms</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Admin Role Notice */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
        <span className="text-xl mt-0.5">⚠️</span>
        <div>
          <h3 className="font-semibold text-amber-900 text-sm">Admin Role Notice</h3>
          <p className="text-xs text-amber-800 mt-1 leading-relaxed">
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
 * Small metric tile for system overview.
 */
const MetricTile: React.FC<{ icon: string; label: string; value: string | number; color: string }> = ({
  icon, label, value, color,
}) => (
  <div className={`p-3 bg-${color}-50 rounded-lg border border-${color}-100`}>
    <div className="text-xl font-bold text-gray-900">{value}</div>
    <div className="text-xs text-gray-500 mt-0.5">{icon} {label}</div>
  </div>
);

export default AdminHomePage;
