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
import { DashboardSkeleton } from '../components/shared/SkeletonCard';
import { useCountUp } from '../hooks/useCountUp';
import CrossAgentAlert, { DEMO_CORRELATIONS } from '../components/CrossAgentAlert';
import ImpactCalculator from '../components/ImpactCalculator';
import ConnectivityBadge from '../components/ConnectivityBadge';
import { useConnectivity } from '../hooks/useConnectivity';

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

const agentAccentColor = (agent: string): string => {
  const a = agent.toLowerCase();
  if (a.includes('shadow') || a.includes('treatment')) return 'var(--shadow-primary)';
  if (a.includes('voice') || a.includes('silent'))     return 'var(--voice-primary)';
  if (a.includes('zebra') || a.includes('ghost'))      return 'var(--ghost-text)';
  return 'var(--critical-text)';
};

const AlertRow: React.FC<{ alert: ActiveAlert; index: number }> = ({ alert, index }) => {
  const navigate = useNavigate();
  const accentColor = agentAccentColor(alert.agent);
  const isCritical = alert.severity === 'critical';

  return (
    <div
      onClick={() => navigate(alert.link)}
      role="button"
      tabIndex={0}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '14px 18px',
        background: isCritical ? 'var(--critical-bg)' : 'var(--bg-elevated)',
        border: `1px solid ${isCritical ? 'var(--critical-border)' : 'var(--border-subtle)'}`,
        borderLeft: `4px solid ${accentColor}`,
        borderRadius: 'var(--radius-md)',
        marginBottom: 8,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        animation: `fade-in-up 0.4s ease both`,
        animationDelay: `${index * 0.08}s`,
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.background = isCritical
          ? 'rgba(239,68,68,0.14)'
          : 'var(--bg-highlight)';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.background = isCritical ? 'var(--critical-bg)' : 'var(--bg-elevated)';
      }}
    >
      <span className={isCritical ? 'dot-critical' : 'dot-live'} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="label-caps" style={{ color: accentColor, marginBottom: 2 }}>
          {alert.agent_icon} {alert.agent.toUpperCase()}
          {alert.location && ` — ${alert.location}`}
        </div>
        <div style={{
          fontFamily: 'var(--font-display)',
          fontWeight: 600,
          fontSize: '0.95rem',
          color: 'var(--text-primary)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {alert.patient_name}
        </div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', marginTop: 2 }}>
          {alert.summary}
        </div>
      </div>

      <button
        className="btn-ghost"
        style={{ borderColor: accentColor, color: accentColor, flexShrink: 0, fontSize: '0.78rem' }}
        onClick={e => { e.stopPropagation(); navigate(alert.link); }}
      >
        View →
      </button>
    </div>
  );
};

// ─── Agent Card ──────────────────────────────────────────────────────────

interface AgentCardProps {
  icon: string;
  name: string;
  accentColor: string;
  stats: { label: string; value: React.ReactNode }[];
  link: string;
}

const AgentCard: React.FC<AgentCardProps> = ({ icon, name, accentColor, stats, link }) => {
  const navigate = useNavigate();

  return (
    <div
      className="pg-card animate-entry"
      onClick={() => navigate(link)}
      role="button"
      tabIndex={0}
      style={{
        borderTop: `2px solid ${accentColor}`,
        cursor: 'pointer',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Subtle gradient overlay matching agent color */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 60,
        background: `linear-gradient(180deg, ${accentColor}08 0%, transparent 100%)`,
        pointerEvents: 'none',
      }} />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, position: 'relative' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '1.4rem' }}>{icon}</span>
          <span style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 700,
            fontSize: '0.9rem',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: accentColor,
          }}>
            {name}
          </span>
        </div>
        <span className="dot-live" title="Healthy" />
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '12px 20px',
        position: 'relative',
      }}>
        {stats.map((stat, i) => (
          <div key={i}>
            <div className="label-caps">{stat.label}</div>
            <div style={{ marginTop: 4, fontSize: '1.3rem', fontFamily: 'var(--font-display)', fontWeight: 700 }}>
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 16,
        paddingTop: 12,
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        justifyContent: 'flex-end',
      }}>
        <span style={{ fontSize: '0.78rem', color: accentColor, fontWeight: 600 }}>
          Open →
        </span>
      </div>
    </div>
  );
};

// ─── Impact Grid ─────────────────────────────────────────────────────────

interface ImpactItem {
  label: string;
  value: React.ReactNode;
  sub?: string;
  color: string;
}

const ImpactGrid: React.FC<{ items: ImpactItem[] }> = ({ items }) => (
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 1 }}>
    {items.map((item, i) => (
      <div
        key={i}
        className="animate-entry"
        style={{
          textAlign: 'center',
          padding: '20px 12px',
          background: 'var(--bg-surface)',
          borderRight: i < items.length - 1 ? '1px solid var(--border-subtle)' : 'none',
        }}
      >
        <div style={{
          fontFamily: 'var(--font-display)',
          fontSize: '2.4rem',
          fontWeight: 700,
          color: item.color,
          lineHeight: 1,
        }}>
          {item.value}
        </div>
        <div style={{
          fontFamily: 'var(--font-body)',
          fontSize: '0.78rem',
          color: 'var(--text-primary)',
          fontWeight: 500,
          marginTop: 6,
          lineHeight: 1.3,
        }}>
          {item.label}
        </div>
        {item.sub && (
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: 4, fontStyle: 'italic' }}>
            {item.sub}
          </div>
        )}
      </div>
    ))}
  </div>
);

// ─── Existing Agents Banner ──────────────────────────────────────────────

const EXISTING_AGENTS = [
  'ScribeAgent', 'CodingAgent', 'SafetyAgent', 'ClinicalAgent',
  'OrderAgent', 'TriageAgent', 'ResistanceAgent', 'PrognosisAgent',
  'SentinelAgent', 'FraudAgent',
];

const ExistingAgentsBanner: React.FC = () => (
  <div className="pg-card">
    <div className="section-header">
      <span style={{ fontSize: '1rem' }}>🛡️</span>
      <span className="section-header-title">Existing 10 Agents — All Operational</span>
      <span className="badge badge-success" style={{ marginLeft: 'auto' }}>100% Block Rate</span>
    </div>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {EXISTING_AGENTS.map((agent) => (
        <span
          key={agent}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-subtle)',
            fontSize: '0.72rem',
            color: 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          <span className="dot-live" style={{ width: 5, height: 5 }} />
          {agent}
        </span>
      ))}
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

  const connectivity = useConnectivity();

  // ── Loading state ──────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="min-h-screen" style={{ background: 'var(--bg-deep)', padding: 24 }}>
        <DashboardSkeleton />
      </div>
    );
  }

  // ── Error fallback ─────────────────────────────────────────────────────
  if (error || !data) {
    return (
      <div className="min-h-screen" style={{ background: 'var(--bg-deep)', padding: 24 }}>
        <div className="alert-critical" style={{ padding: 24, maxWidth: 600, margin: '60px auto', textAlign: 'center' }}>
          <p style={{ color: 'var(--critical-text)', fontWeight: 700, fontSize: '1.1rem', marginBottom: 8 }}>
            Dashboard Unavailable
          </p>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Backend may not be running. Start with:{' '}
            <code style={{ background: 'var(--bg-elevated)', padding: '2px 8px', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
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
    <div className="min-h-screen" style={{ background: 'var(--bg-deep)' }}>

      {/* ═══ HERO HEADER ═══════════════════════════════════════════════ */}
      <div style={{
        borderBottom: '1px solid var(--border-subtle)',
        padding: '20px 32px 18px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <span style={{ fontSize: '1.5rem' }}>🛡️</span>
          <div>
            <h1 style={{
              fontFamily: 'var(--font-display)',
              fontSize: '1.3rem',
              fontWeight: 700,
              color: 'var(--text-primary)',
              margin: 0,
              letterSpacing: '-0.01em',
            }}>
              PHOENIX GUARDIAN <span style={{ color: '#60a5fa' }}>V5</span>
            </h1>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <ConnectivityBadge mode={connectivity.mode} />
            {[
              `${data.demo_patients_loaded} demo patients`,
              'All agents healthy',
              '3 V5 AGENTS',
            ].map((s, i) => (
              <span key={i} className="badge" style={{
                background: 'rgba(16,185,129,0.1)',
                color: '#34d399',
                border: '1px solid rgba(16,185,129,0.3)',
                fontFamily: 'var(--font-mono)',
              }}>
                ● {s}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ═══ PAGE CONTENT ════════════════════════════════════════════ */}
      <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

          {/* ═══ ACTIVE ALERTS ═════════════════════════════════════════ */}
          <div className="pg-card">
            <div className="section-header">
              <span className="dot-critical" />
              <span className="section-header-title" style={{ color: 'var(--critical-text)' }}>
                Active Alerts — Requires Attention Now
              </span>
              {active_alerts.length > 0 && (
                <span className="badge badge-critical" style={{ marginLeft: 'auto' }}>
                  {active_alerts.length} Active
                </span>
              )}
            </div>

            {active_alerts.length > 0 ? (
              <div>
                {active_alerts.map((alert, i) => (
                  <AlertRow key={i} alert={alert} index={i} />
                ))}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)' }}>
                <span style={{ fontSize: '1.5rem', display: 'block', marginBottom: 8 }}>✅</span>
                All patients stable — no alerts.
              </div>
            )}
          </div>

          {/* ═══ CROSS-AGENT CORRELATIONS ══════════════════════════ */}
          <CrossAgentAlert
            patientName="Priya Sharma"
            patientId="PT-1001"
            correlations={DEMO_CORRELATIONS}
          />

          {/* ═══ AGENT CARDS ═══════════════════════════════════════════ */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
            {/* Zebra Hunter Card */}
            <AgentCard
              icon="🦓"
              name="Zebra Hunter"
              accentColor="var(--zebra-primary)"
              link="/zebra-hunter"
              stats={[
                {
                  label: 'ZEBRA FOUND',
                  value: <CountUp target={zebra.zebra_count} className="" />,
                },
                {
                  label: '👻 GHOST PROTOCOL',
                  value: <CountUp target={zebra.ghost_count} className="" />,
                },
                {
                  label: 'YEARS LOST',
                  value: (
                    <span style={{ color: 'var(--critical-text)' }}>
                      <CountUp target={zebra.years_lost} decimals={1} /> <span className="stat-unit">yrs</span>
                    </span>
                  ),
                },
                {
                  label: 'TOP MATCH',
                  value: (
                    <span style={{ color: 'var(--zebra-primary)', fontSize: '0.85rem' }}>
                      {zebra.top_disease || 'N/A'}
                      <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginLeft: 4 }}>
                        {zebra.top_confidence}%
                      </span>
                    </span>
                  ),
                },
              ]}
            />

            {/* Silent Voice Card */}
            <AgentCard
              icon="🔵"
              name="Silent Voice"
              accentColor="var(--voice-primary)"
              link="/silent-voice"
              stats={[
                {
                  label: '🔴 CRITICAL ALERT',
                  value: (
                    <span style={{ color: 'var(--critical-text)' }}>
                      <CountUp target={silent.active_alerts} />
                    </span>
                  ),
                },
                {
                  label: 'SIGNALS DETECTED',
                  value: (
                    <span style={{ color: 'var(--voice-primary)' }}>
                      <CountUp target={silent.signals_detected} />
                    </span>
                  ),
                },
                {
                  label: 'UNDETECTED FOR',
                  value: (
                    <span style={{ color: 'var(--critical-text)' }}>
                      <CountUp target={silent.distress_duration_minutes} /> <span className="stat-unit">min</span>
                    </span>
                  ),
                },
                {
                  label: 'LAST ANALGESIC',
                  value: (
                    <span style={{ color: 'var(--warning-text)' }}>
                      {silent.last_analgesic_hours.toFixed(1)} <span className="stat-unit">hrs</span>
                    </span>
                  ),
                },
              ]}
            />

            {/* Treatment Shadow Card */}
            <AgentCard
              icon="🟣"
              name="Shadow Agent"
              accentColor="var(--shadow-primary)"
              link="/treatment-shadow"
              stats={[
                {
                  label: 'SHADOW FIRED',
                  value: (
                    <span style={{ color: 'var(--shadow-primary)' }}>
                      <CountUp target={shadow.fired_count} />
                    </span>
                  ),
                },
                {
                  label: 'WATCHING',
                  value: (
                    <span style={{ color: 'var(--watching-text)' }}>
                      <CountUp target={shadow.watching_count} />
                    </span>
                  ),
                },
                {
                  label: 'B12 DECLINING',
                  value: (
                    <span style={{ color: 'var(--critical-text)' }}>
                      <CountUp target={shadow.b12_pct_change} /> <span className="stat-unit">%</span>
                    </span>
                  ),
                },
                {
                  label: 'DAYS TO HARM',
                  value: (
                    <span style={{ color: 'var(--warning-text)' }}>
                      <CountUp target={shadow.days_to_harm} /> <span className="stat-unit">days</span>
                    </span>
                  ),
                },
              ]}
            />
          </div>

          {/* ═══ IMPACT SUMMARY ════════════════════════════════════════ */}
          <div className="pg-card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
              <div className="section-header" style={{ marginBottom: 0, paddingBottom: 0, border: 'none' }}>
                <span style={{ fontSize: '1rem' }}>📊</span>
                <span className="section-header-title">V5 Impact Summary</span>
              </div>
            </div>
            <ImpactGrid items={[
              {
                label: 'Rare Diseases Detected',
                value: <CountUp target={impact.rare_diseases_detected} />,
                sub: 'avg 4-8 years by human',
                color: 'var(--zebra-primary)',
              },
              {
                label: 'Silent Distress Caught',
                value: <CountUp target={impact.silent_distress_caught} />,
                sub: `${silent.distress_duration_minutes} min undetected`,
                color: 'var(--voice-primary)',
              },
              {
                label: 'Treatment Harms Prevented',
                value: <CountUp target={impact.treatment_harms_prevented} />,
                sub: `${shadow.days_to_harm} days to neuropathy`,
                color: 'var(--shadow-primary)',
              },
              {
                label: 'Ghost Cases Created',
                value: <CountUp target={impact.ghost_cases_created} />,
                sub: 'potential novel disease',
                color: 'var(--ghost-text)',
              },
              {
                label: 'Years Suffering Prevented',
                value: <CountUp target={impact.years_suffering_prevented} decimals={1} />,
                sub: 'EDS missed clues',
                color: 'var(--critical-text)',
              },
            ]} />
          </div>

          {/* ═══ IMPACT CALCULATOR ═════════════════════════════════ */}
          <ImpactCalculator />

          {/* ═══ EXISTING AGENTS ═══════════════════════════════════════ */}
          <ExistingAgentsBanner />

        </div>
      </div>
    </div>
  );
};

export default V5DashboardPage;
