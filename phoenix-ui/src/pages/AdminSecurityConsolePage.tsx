/**
 * Admin Security Console Page.
 *
 * SOC-style dark-themed dashboard with 6 security panels:
 * 1. Live Threat Feed — real-time attack stream via WebSocket
 * 2. Honeytoken Registry — synthetic patient identifiers for intrusion detection
 * 3. Attacker Fingerprinting — tracked attacker profiles with risk scores
 * 4. Learning Impact — security → clinical AI improvement metrics
 * 5. PQC Status — post-quantum cryptography health
 * 6. System Health — agent status grid
 *
 * Access: Admin role only (RBAC-enforced via ProtectedRoute).
 */

import React, { useEffect, useState } from 'react';
import apiClient from '../api/client';
import {
  LiveThreatFeed,
  HoneytokenPanel,
  AttackerFingerprint,
  LearningImpactPanel,
  PQCStatusPanel,
  SystemHealthDashboard,
} from '../components/security';

interface SecuritySummary {
  total_events: number;
  blocked: number;
  block_rate: number;
  honeytoken_triggers: number;
  active_attackers: number;
  avg_detection_time_ms: number;
  severity_distribution: Record<string, number>;
  threat_type_distribution: Record<string, number>;
}

export const AdminSecurityConsolePage: React.FC = () => {
  const [summary, setSummary] = useState<SecuritySummary | null>(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await apiClient.get('/security-console/summary');
        setSummary(res.data);
      } catch (err) {
        console.error('Failed to fetch security summary', err);
      }
    };
    fetch();
    const interval = setInterval(fetch, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-[#0f1419] -m-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
            <span className="text-red-400">🛡️</span>
            Security Operations Console
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Phoenix Guardian v4 — Real-time threat detection, PQC encryption, and AI-driven security analytics
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-900/30 text-green-400 text-xs font-semibold border border-green-700/50">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            MONITORING ACTIVE
          </span>
        </div>
      </div>

      {/* Summary metrics strip */}
      {summary && (
        <div className="grid grid-cols-6 gap-3 mb-6">
          <MetricCard label="Total Events" value={summary.total_events} color="text-gray-200" />
          <MetricCard label="Blocked" value={summary.blocked} color="text-red-400" />
          <MetricCard label="Block Rate" value={`${summary.block_rate.toFixed(1)}%`} color="text-green-400" />
          <MetricCard label="Avg Detection" value={`${summary.avg_detection_time_ms.toFixed(0)}ms`} color="text-cyan-400" />
          <MetricCard label="Critical" value={summary.severity_distribution?.CRITICAL || 0} color="text-red-400" />
          <MetricCard label="Attackers" value={summary.active_attackers} color="text-amber-400" />
        </div>
      )}

      {/* 6-panel grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Row 1: Live Threat Feed (full width) */}
        <div className="col-span-12">
          <LiveThreatFeed />
        </div>

        {/* Row 2: Honeytokens (6) + Attacker Fingerprints (6) */}
        <div className="col-span-6">
          <HoneytokenPanel />
        </div>
        <div className="col-span-6">
          <AttackerFingerprint />
        </div>

        {/* Row 3: Learning Impact (4) + PQC Status (4) + System Health (4) */}
        <div className="col-span-4">
          <LearningImpactPanel />
        </div>
        <div className="col-span-4">
          <PQCStatusPanel />
        </div>
        <div className="col-span-4">
          <SystemHealthDashboard />
        </div>
      </div>

      {/* Footer */}
      <div className="mt-6 text-center text-[10px] text-gray-600">
        HIPAA-compliant security monitoring • All IP addresses anonymized • Honeytokens contain no real PHI •
        Kyber-1024 post-quantum encryption active
      </div>
    </div>
  );
};

/**
 * Small metric card for the summary strip.
 */
const MetricCard: React.FC<{ label: string; value: string | number; color: string }> = ({ label, value, color }) => (
  <div className="bg-[#1a1f29] border border-[#2d3748] rounded-lg px-4 py-3 text-center">
    <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">{label}</div>
    <div className={`text-xl font-bold ${color}`}>{value}</div>
  </div>
);

export default AdminSecurityConsolePage;
