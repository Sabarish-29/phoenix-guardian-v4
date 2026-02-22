/**
 * CrossAgentAlert — shows when the same patient triggers multiple V5 agents.
 *
 * Uses hardcoded demo data that mirrors the backend CrossAgentCorrelator
 * output.  In production the dashboard would fetch
 * GET /api/v1/correlations/{patient_id} for every active patient.
 */

import React from 'react';

// ── Types ────────────────────────────────────────────────────────────────

interface Correlation {
  correlation_id: string;
  name: string;
  agents_involved: string[];
  insight: string;
  severity: 'critical' | 'warning';
}

export interface CrossAgentAlertProps {
  patientName: string;
  patientId: string;
  correlations: Correlation[];
}

// ── Agent Pill ───────────────────────────────────────────────────────────

const AGENT_META: Record<string, { icon: string; color: string; label: string }> = {
  silent_voice:     { icon: '🔵', color: 'var(--voice-primary)',  label: 'Silent Voice' },
  treatment_shadow: { icon: '🟣', color: 'var(--shadow-primary)', label: 'Treatment Shadow' },
  zebra_hunter:     { icon: '🦓', color: 'var(--zebra-primary)',  label: 'Zebra Hunter' },
};

const AgentPill: React.FC<{ agent: string }> = ({ agent }) => {
  const meta = AGENT_META[agent] ?? { icon: '🔘', color: 'var(--text-secondary)', label: agent };
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '3px 10px',
        borderRadius: 100,
        border: `1px solid ${meta.color}33`,
        background: `${meta.color}0d`,
        fontSize: '0.72rem',
        fontFamily: 'var(--font-mono)',
        fontWeight: 600,
        color: meta.color,
        whiteSpace: 'nowrap',
      }}
    >
      {meta.icon} {meta.label}
    </span>
  );
};

// ── Severity badge ──────────────────────────────────────────────────────

const SeverityBadge: React.FC<{ severity: string }> = ({ severity }) => {
  const isCritical = severity === 'critical';
  return (
    <span
      className={isCritical ? 'badge badge-critical' : 'badge badge-warning'}
      style={{ fontSize: '0.65rem', letterSpacing: '0.06em', textTransform: 'uppercase' }}
    >
      {severity}
    </span>
  );
};

// ── Single Correlation Row ──────────────────────────────────────────────

const CorrelationRow: React.FC<{ c: Correlation; index: number }> = ({ c, index }) => {
  const isCritical = c.severity === 'critical';
  return (
    <div
      style={{
        padding: '14px 18px',
        background: isCritical ? 'var(--critical-bg)' : 'rgba(234,179,8,0.06)',
        border: `1px solid ${isCritical ? 'var(--critical-border)' : 'rgba(234,179,8,0.25)'}`,
        borderLeft: `4px solid ${isCritical ? 'var(--critical-text)' : '#eab308'}`,
        borderRadius: 'var(--radius-md)',
        marginBottom: 8,
        animation: 'fade-in-up 0.4s ease both',
        animationDelay: `${index * 0.1}s`,
      }}
    >
      {/* Header: name + severity + agent pills */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 8,
          marginBottom: 8,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 700,
            fontSize: '0.85rem',
            color: 'var(--text-primary)',
          }}
        >
          🔗 {c.name}
        </span>
        <SeverityBadge severity={c.severity} />
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {c.agents_involved.map((a) => (
            <AgentPill key={a} agent={a} />
          ))}
        </div>
      </div>

      {/* Insight text */}
      <p
        style={{
          margin: 0,
          fontSize: '0.8rem',
          lineHeight: 1.55,
          color: 'var(--text-secondary)',
        }}
      >
        {c.insight}
      </p>
    </div>
  );
};

// ── Main Component ──────────────────────────────────────────────────────

const CrossAgentAlert: React.FC<CrossAgentAlertProps> = ({
  patientName,
  patientId,
  correlations,
}) => {
  if (correlations.length === 0) return null;

  return (
    <div className="pg-card animate-entry">
      <div className="section-header">
        <span style={{ fontSize: '1rem' }}>🔗</span>
        <span className="section-header-title">
          Cross-Agent Correlations
        </span>
        <span
          className="badge badge-critical"
          style={{ marginLeft: 'auto' }}
        >
          {correlations.length} Correlation{correlations.length > 1 ? 's' : ''}
        </span>
      </div>

      {/* Patient context */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 12,
          fontSize: '0.78rem',
          color: 'var(--text-secondary)',
        }}
      >
        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
          {patientName}
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', opacity: 0.7 }}>
          ({patientId})
        </span>
        <span>— flagged by multiple V5 agents simultaneously</span>
      </div>

      {/* Correlation rows */}
      {correlations.map((c, i) => (
        <CorrelationRow key={c.correlation_id} c={c} index={i} />
      ))}

      {/* Disclaimer */}
      <p
        style={{
          margin: '10px 0 0',
          fontSize: '0.65rem',
          color: 'var(--text-muted)',
          fontStyle: 'italic',
          textAlign: 'center',
        }}
      >
        Cross-agent correlations are AI-generated hypotheses — always verify with attending physician.
      </p>
    </div>
  );
};

export default CrossAgentAlert;

// ── Demo data (mirrors backend correlator output) ────────────────────────

export const DEMO_CORRELATIONS: Correlation[] = [
  {
    correlation_id: 'pain_plus_analgesic_tolerance',
    name: 'Pain Distress + Analgesic Tolerance',
    agents_involved: ['silent_voice', 'treatment_shadow'],
    insight:
      'Active pain distress signal detected alongside escalating analgesic medication pattern. ' +
      'Combined finding suggests breakthrough pain or analgesic tolerance development. ' +
      'Recommend immediate pain management consultation and analgesic rotation evaluation.',
    severity: 'critical',
  },
  {
    correlation_id: 'rare_disease_plus_shadow',
    name: 'Rare Disease + Treatment Shadow',
    agents_involved: ['zebra_hunter', 'treatment_shadow'],
    insight:
      'Rare disease pattern detected alongside active treatment shadow. ' +
      'Medications prescribed for symptomatic treatment may be masking or worsening ' +
      'an underlying connective tissue disorder. ' +
      'Recommend specialist review of current medication regimen in context of rare disease diagnosis.',
    severity: 'warning',
  },
];
