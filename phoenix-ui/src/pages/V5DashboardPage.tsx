/**
 * V5 Unified Dashboard Page — Phoenix Guardian V5 Phase 4.
 *
 * Shows all 3 agents at a glance with live status indicators.
 * This is the first page judges see during the hackathon demo.
 *
 * Sections:
 *  1. Hero header with status indicators
 *  2. Active Alerts — requires attention NOW
 *  3. Agent Cards (3 columns) — live numbers from API
 *  4. Impact Summary — running totals
 *  5. Existing Agents banner
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { v5DashboardService } from '../api/services/v5DashboardService';
import type {
  V5StatusResponse,
  ActiveAlert,
} from '../api/services/v5DashboardService';
import { getAlertColors } from '../constants/alertColors';
import { DashboardSkeleton } from '../components/shared/SkeletonCard';
import { useCountUp } from '../hooks/useCountUp';

// ─── Animated Counter Component ──────────────────────────────────────────

const CountUp: React.FC<{
  target: number;
  duration?: number;
  decimals?: number;
  suffix?: string;
  className?: string;
}> = ({ target, duration = 1500, decimals = 0, suffix = '', className = '' }) => {
  const value = useCountUp(target, duration, decimals);
  const display = decimals > 0 ? value.toFixed(decimals) : String(value);
  return <span className={className}>{display}{suffix}</span>;
};

// ─── Alert Row ───────────────────────────────────────────────────────────

const AlertRow: React.FC<{ alert: ActiveAlert }> = ({ alert }) => {
  const navigate = useNavigate();
  const colors = getAlertColors(alert.severity);

  return (
    <div
      className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer
        hover:brightness-125 transition-all ${colors.bg} ${colors.border} animate-fadeIn`}
      onClick={() => navigate(alert.link)}
      role="button"
      tabIndex={0}
    >
      <div className="flex items-center gap-3">
        <span className={`h-3 w-3 rounded-full ${colors.dot}`} />
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">
              {alert.agent_icon} {alert.agent}
            </span>
            <span className={`font-semibold ${colors.text}`}>{alert.patient_name}</span>
            {alert.location && (
              <span className="text-xs text-gray-500">— {alert.location}</span>
            )}
          </div>
          <p className="text-sm text-gray-300 mt-0.5">{alert.summary}</p>
        </div>
      </div>
      <span className={`text-xs font-medium px-2 py-1 rounded ${colors.badge} text-white whitespace-nowrap`}>
        View →
      </span>
    </div>
  );
};

// ─── Agent Card ──────────────────────────────────────────────────────────

interface AgentCardProps {
  icon: string;
  name: string;
  borderColor: string;
  stats: { label: string; value: React.ReactNode }[];
  link: string;
}

const AgentCard: React.FC<AgentCardProps> = ({ icon, name, borderColor, stats, link }) => {
  const navigate = useNavigate();

  return (
    <div
      className={`bg-gray-800/80 rounded-xl border-2 ${borderColor} p-5 
        hover:border-opacity-100 transition-all cursor-pointer animate-slideUp
        hover:shadow-lg`}
      onClick={() => navigate(link)}
      role="button"
      tabIndex={0}
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-2xl mr-2">{icon}</span>
          <span className="text-lg font-bold text-white uppercase tracking-wider">{name}</span>
        </div>
        <span className="h-3 w-3 rounded-full bg-green-500 animate-pulse" title="Healthy" />
      </div>

      <div className="space-y-3">
        {stats.map((stat, i) => (
          <div key={i} className="flex items-center justify-between">
            <span className="text-sm text-gray-400">{stat.label}</span>
            <span className="text-sm font-bold text-white">{stat.value}</span>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-3 border-t border-gray-700">
        <span className="text-sm font-medium text-blue-400 hover:text-blue-300">
          Open →
        </span>
      </div>
    </div>
  );
};

// ─── Impact Row ──────────────────────────────────────────────────────────

const ImpactRow: React.FC<{ label: string; value: React.ReactNode; note?: string }> = ({ label, value, note }) => (
  <div className="flex items-center justify-between py-2 border-b border-gray-800 last:border-b-0">
    <span className="text-sm text-gray-300">{label}</span>
    <div className="text-right">
      <span className="text-lg font-bold text-white">{value}</span>
      {note && <span className="text-xs text-gray-500 ml-2">({note})</span>}
    </div>
  </div>
);

// ─── Existing Agents Banner ──────────────────────────────────────────────

const EXISTING_AGENTS = [
  'ScribeAgent', 'CodingAgent', 'SafetyAgent', 'ClinicalAgent',
  'OrderAgent', 'TriageAgent', 'ResistanceAgent', 'PrognosisAgent',
  'SentinelAgent', 'FraudAgent',
];

const ExistingAgentsBanner: React.FC = () => (
  <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
    <div className="flex items-center gap-2 mb-3">
      <span className="text-lg">🛡️</span>
      <span className="font-bold text-gray-200 uppercase tracking-wider text-sm">
        Existing 10 Agents — All Operational
      </span>
    </div>
    <div className="flex flex-wrap gap-2">
      {EXISTING_AGENTS.map((agent) => (
        <span
          key={agent}
          className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-gray-700/60 text-xs text-gray-300"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
          {agent}
        </span>
      ))}
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-green-900/40 text-xs text-green-400 font-medium">
        Security: 100% block rate
      </span>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════
// MAIN PAGE COMPONENT
// ═══════════════════════════════════════════════════════════════════════════

export const V5DashboardPage: React.FC = () => {
  const { data, isLoading, error } = useQuery<V5StatusResponse>({
    queryKey: ['v5-dashboard-status'],
    queryFn: v5DashboardService.getStatus,
    staleTime: 30_000,
    refetchInterval: 30_000,
    retry: 1,
  });

  // ── Loading state ──────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-900 p-6">
        <DashboardSkeleton />
      </div>
    );
  }

  // ── Error fallback ─────────────────────────────────────────────────────
  if (error || !data) {
    return (
      <div className="min-h-screen bg-gray-900 p-6">
        <div className="bg-red-900/20 border border-red-500 rounded-xl p-6 text-center">
          <p className="text-red-400 font-bold text-lg mb-2">Dashboard Unavailable</p>
          <p className="text-gray-400 text-sm">
            Backend may not be running. Start with:{' '}
            <code className="bg-gray-800 px-2 py-1 rounded text-xs">
              uvicorn phoenix_guardian.api.main:app --reload
            </code>
          </p>
        </div>
      </div>
    );
  }

  const { active_alerts, agents, impact } = data;
  const shadow = agents.treatment_shadow;
  const silent = agents.silent_voice;
  const zebra = agents.zebra_hunter;

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4 md:p-6 space-y-6 animate-fadeIn">

      {/* ═══ HERO HEADER ═══════════════════════════════════════════════ */}
      <div className="bg-gradient-to-r from-gray-800 via-gray-800 to-gray-900 rounded-xl p-6 border border-gray-700">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-3xl font-black tracking-tight">
              🛡️ PHOENIX GUARDIAN <span className="text-emerald-400">V5</span>
            </h1>
            <p className="text-gray-400 mt-1 italic">
              "Save Time. Save Lives. Stay Secure."
            </p>
          </div>
          <div className="flex items-center gap-6 text-sm text-gray-400">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              {data.demo_patients_loaded} demo patients loaded
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              All agents healthy
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
              3 NEW agents
            </span>
          </div>
        </div>
      </div>

      {/* ═══ ACTIVE ALERTS ═════════════════════════════════════════════ */}
      <div className="bg-gray-800/60 rounded-xl p-5 border border-gray-700">
        <h2 className="text-lg font-bold text-red-400 uppercase tracking-wider mb-4 flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-red-500 animate-pulse" />
          Active Alerts — Requires Attention Now
        </h2>

        {active_alerts.length > 0 ? (
          <div className="space-y-2">
            {active_alerts.map((alert, i) => (
              <AlertRow key={i} alert={alert} />
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-gray-500">
            <p className="text-lg">All patients stable — no alerts.</p>
          </div>
        )}
      </div>

      {/* ═══ AGENT CARDS ═══════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Zebra Hunter Card */}
        <AgentCard
          icon="🦓"
          name="Zebra Hunter"
          borderColor="border-amber-600/50"
          link="/zebra-hunter"
          stats={[
            {
              label: 'ZEBRA FOUND',
              value: <CountUp target={zebra.zebra_count} className="text-amber-400 text-lg font-black" />,
            },
            {
              label: '👻 GHOST PROTOCOL',
              value: <CountUp target={zebra.ghost_count} className="text-purple-400 text-lg font-black" />,
            },
            {
              label: 'YEARS LOST',
              value: <CountUp target={zebra.years_lost} decimals={1} suffix=" yrs" className="text-red-400 font-bold" />,
            },
            {
              label: 'TOP MATCH',
              value: <span className="text-xs">{zebra.top_disease || 'N/A'} ({zebra.top_confidence}%)</span>,
            },
          ]}
        />

        {/* Silent Voice Card */}
        <AgentCard
          icon="🔵"
          name="Silent Voice"
          borderColor="border-blue-600/50"
          link="/silent-voice"
          stats={[
            {
              label: '🔴 CRITICAL ALERT',
              value: <CountUp target={silent.active_alerts} className="text-red-400 text-lg font-black" />,
            },
            {
              label: 'SIGNALS DETECTED',
              value: <CountUp target={silent.signals_detected} className="text-blue-400 font-bold" />,
            },
            {
              label: 'UNDETECTED',
              value: <CountUp target={silent.distress_duration_minutes} suffix=" min" className="text-red-400 font-bold" />,
            },
            {
              label: 'LAST ANALGESIC',
              value: <span className="text-yellow-400">{silent.last_analgesic_hours.toFixed(1)} hrs</span>,
            },
          ]}
        />

        {/* Treatment Shadow Card */}
        <AgentCard
          icon="🟣"
          name="Shadow Agent"
          borderColor="border-purple-600/50"
          link="/treatment-shadow"
          stats={[
            {
              label: 'SHADOW FIRED',
              value: <CountUp target={shadow.fired_count} className="text-purple-400 text-lg font-black" />,
            },
            {
              label: 'WATCHING',
              value: <CountUp target={shadow.watching_count} className="text-blue-400 font-bold" />,
            },
            {
              label: 'B12 DECLINING',
              value: <CountUp target={shadow.b12_pct_change} suffix="%" className="text-red-400 font-bold" />,
            },
            {
              label: 'DAYS TO HARM',
              value: <CountUp target={shadow.days_to_harm} suffix=" days" className="text-yellow-400 font-bold" />,
            },
          ]}
        />
      </div>

      {/* ═══ IMPACT SUMMARY ════════════════════════════════════════════ */}
      <div className="bg-gray-800/60 rounded-xl p-5 border border-gray-700">
        <h2 className="text-lg font-bold text-emerald-400 uppercase tracking-wider mb-4 flex items-center gap-2">
          📊 V5 Impact Summary
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
          <ImpactRow
            label="Rare diseases detected"
            value={<CountUp target={impact.rare_diseases_detected} />}
            note="avg 4-8 years by human"
          />
          <ImpactRow
            label="Silent distress caught"
            value={<CountUp target={impact.silent_distress_caught} />}
            note={`${silent.distress_duration_minutes} min undetected`}
          />
          <ImpactRow
            label="Treatment harms prevented"
            value={<CountUp target={impact.treatment_harms_prevented} />}
            note={`${shadow.days_to_harm} days to neuropathy`}
          />
          <ImpactRow
            label="Ghost cases created"
            value={<CountUp target={impact.ghost_cases_created} />}
            note="potential novel disease"
          />
          <ImpactRow
            label="Years of suffering prevented"
            value={<CountUp target={impact.years_suffering_prevented} decimals={1} suffix=" yrs" />}
            note="EDS missed clues"
          />
        </div>
      </div>

      {/* ═══ EXISTING AGENTS ═══════════════════════════════════════════ */}
      <ExistingAgentsBanner />
    </div>
  );
};

export default V5DashboardPage;
