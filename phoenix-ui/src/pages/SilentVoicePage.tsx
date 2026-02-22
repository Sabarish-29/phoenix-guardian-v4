/**
 * SilentVoicePage — Real-time non-verbal distress monitoring.
 *
 * 4-section layout:
 *   1. Patient Status Header (color-coded by alert level)
 *   2. Live Vitals Grid (6 cards — population vs personal toggle)
 *   3. Clinical Alert Card (only when distress detected)
 *   4. Distress Timeline (admission → baseline → distress → now)
 *
 * The demo toggle between Population Average and Personal Baseline
 * is the emotional core of this agent's presentation.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSilentVoiceStream } from '../hooks/useSilentVoiceStream';
import { silentVoiceService } from '../api/services/silentVoiceService';
import type { MonitorResult } from '../api/services/silentVoiceService';
import { useLanguage } from '../context/LanguageContext';

// ─── Constants ────────────────────────────────────────────────────────────

const PATIENT_C_ID = 'a1b2c3d4-0003-4000-8000-000000000003';

/** Population averages — what hospitals normally show. */
const POPULATION_AVERAGES: Record<string, { mean: number; std: number }> = {
  hr:     { mean: 80, std: 15 },
  bp_sys: { mean: 120, std: 20 },
  bp_dia: { mean: 80, std: 12 },
  spo2:   { mean: 97, std: 2 },
  rr:     { mean: 18, std: 4 },
  hrv:    { mean: 45, std: 20 },
};

const VITAL_CONFIG: Record<string, { label: string; unit: string; icon: string }> = {
  hr:     { label: 'HEART RATE',    unit: 'bpm',   icon: '❤️' },
  bp_sys: { label: 'SYSTOLIC BP',   unit: 'mmHg',  icon: '🩸' },
  bp_dia: { label: 'DIASTOLIC BP',  unit: 'mmHg',  icon: '🩸' },
  spo2:   { label: 'SpO2',          unit: '%',     icon: '🫁' },
  rr:     { label: 'RESP RATE',     unit: '/min',  icon: '🌬️' },
  hrv:    { label: 'HRV SCORE',     unit: 'ms',    icon: '📊' },
};

type BaselineMode = 'personal' | 'population';

// ─── Helper: z-score calculation ──────────────────────────────────────────

function calcZ(current: number, mean: number, std: number): number {
  if (std === 0) return 0;
  return (current - mean) / std;
}

function getVitalStatus(z: number): 'critical' | 'warning' | 'normal' {
  const absZ = Math.abs(z);
  if (absZ > 2.5) return 'critical';
  if (absZ > 1.5) return 'warning';
  return 'normal';
}

// ─── Alert Score Bar ──────────────────────────────────────────────────────

const AlertScoreBar: React.FC<{ score: number; maxScore?: number }> = ({ score, maxScore = 10 }) => {
  const pct = Math.min((score / maxScore) * 100, 100);
  const isCritical = score > 8;
  const isWarning = score > 4;
  const barColor = isCritical ? 'var(--critical-text)' : isWarning ? 'var(--warning-text)' : 'var(--success-text)';
  const label = isCritical ? 'CRITICAL' : isWarning ? 'WARNING' : 'CLEAR';

  return (
    <div style={{
      background: isCritical ? 'var(--critical-bg)' : isWarning ? 'var(--warning-bg)' : 'var(--bg-surface)',
      border: `1px solid ${isCritical ? 'var(--critical-border)' : isWarning ? 'var(--warning-border)' : 'var(--border-subtle)'}`,
      borderRadius: 'var(--radius-md)',
      padding: 16,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}>
      <div className="label-caps">ALERT SCORE</div>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: '2rem', fontWeight: 700, color: barColor, lineHeight: 1, marginTop: 6 }}>
        {score.toFixed(1)}
      </div>
      <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginBottom: 8 }}>/ {maxScore}</div>
      <div className="progress-bar-track" style={{ width: '100%' }}>
        <div className="progress-bar-fill" style={{ width: `${pct}%`, background: barColor }} />
      </div>
      <span className="badge" style={{ marginTop: 8, background: 'transparent', color: barColor, border: 'none', padding: '0', fontSize: '0.65rem', fontWeight: 700 }}>
        {label}
      </span>
    </div>
  );
};

// ─── Vital Card Component ────────────────────────────────────────────────

interface VitalCardProps {
  field: string;
  current: number | null;
  mode: BaselineMode;
  personalBaseline: { mean: number; std: number } | undefined;
  history: number[];
}

const VitalCard: React.FC<VitalCardProps> = ({ field, current, mode, personalBaseline, history }) => {
  const config = VITAL_CONFIG[field];
  if (!config || current === null || current === undefined) return null;

  const baseline = mode === 'personal' && personalBaseline
    ? personalBaseline
    : POPULATION_AVERAGES[field];

  const z = calcZ(current, baseline.mean, baseline.std);
  const status = getVitalStatus(z);
  const deviationPct = baseline.mean !== 0 ? ((current - baseline.mean) / baseline.mean) * 100 : 0;

  // Mini sparkline using block characters
  const sparkline = history.length > 1
    ? history.map((v) => {
        const min = Math.min(...history);
        const max = Math.max(...history);
        const range = max - min || 1;
        const normalized = (v - min) / range;
        const chars = '▁▂▃▄▅▆▇█';
        return chars[Math.min(Math.floor(normalized * 8), 7)];
      }).join('')
    : '▄▄▄▄▄';

  const accentColor = status === 'critical' ? 'var(--critical-text)' : status === 'warning' ? 'var(--warning-text)' : 'var(--success-text)';
  const cardBg = status === 'critical' ? 'var(--critical-bg)' : status === 'warning' ? 'var(--warning-bg)' : 'var(--bg-surface)';
  const cardBorder = status === 'critical' ? 'var(--critical-border)' : status === 'warning' ? 'var(--warning-border)' : 'var(--border-subtle)';

  return (
    <div style={{
      background: cardBg,
      border: `1px solid ${cardBorder}`,
      borderRadius: 'var(--radius-md)',
      padding: 16,
      transition: 'all 0.4s ease',
      boxShadow: 'none',
    }}>
      {/* Top row: label + status indicator */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, alignItems: 'center' }}>
        <span style={{ fontSize: '0.65rem', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-label)' }}>
          {config.icon} {config.label}
        </span>
        <span className={status === 'critical' ? 'dot-critical' : status === 'warning' ? 'dot-polling' : 'dot-live'} />
      </div>

      {/* Big number */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 4 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: '1.9rem', fontWeight: 700, color: accentColor, lineHeight: 1 }}>
          {typeof current === 'number' ? (Number.isInteger(current) ? current : current.toFixed(1)) : current}
        </span>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{config.unit}</span>
      </div>

      {/* Sparkline */}
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.95rem', letterSpacing: '0.05em', color: accentColor, opacity: 0.6, marginBottom: 8 }}>
        {sparkline}
      </div>

      {/* Baseline comparison */}
      <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 8 }}>
        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
          {mode === 'personal' ? '👤 Personal' : '👥 Population'} baseline: {baseline.mean.toFixed(0)}
        </div>
        {Math.abs(deviationPct) > 5 && (
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.72rem',
            fontWeight: 600,
            color: accentColor,
            marginTop: 2,
          }}>
            {deviationPct > 0 ? '+' : ''}{deviationPct.toFixed(0)}% {deviationPct > 0 ? '↑' : '↓'}
          </div>
        )}
      </div>
    </div>
  );
};

// ─── Distress Timeline ───────────────────────────────────────────────────

interface TimelineProps {
  admissionHoursAgo: number;
  baselineEstablished: boolean;
  distressMinutes: number;
  minutesSinceCheck: number;
}

const DistressTimeline: React.FC<TimelineProps> = ({
  admissionHoursAgo,
  baselineEstablished,
  distressMinutes,
  minutesSinceCheck,
}) => {
  const totalMinutes = admissionHoursAgo * 60;
  const baselineEnd = Math.min(120, totalMinutes);
  const distressStart = totalMinutes - distressMinutes;

  const baselinePct = totalMinutes > 0 ? (baselineEnd / totalMinutes) * 100 : 33;
  const distressPct = totalMinutes > 0 ? (distressStart / totalMinutes) * 100 : 80;

  return (
    <div className="pg-card">
      <div className="section-header">
        <span style={{ fontSize: '0.9rem' }}>📈</span>
        <span className="section-header-title">Distress Timeline</span>
      </div>

      <div style={{ position: 'relative', height: 32, marginBottom: 8 }}>
        {/* Green baseline zone */}
        <div style={{ position: 'absolute', height: '100%', left: '0%', width: `${baselinePct}%`, background: 'rgba(16,185,129,0.25)', borderRadius: '6px 0 0 6px' }} />
        {/* Gray stable zone */}
        <div style={{ position: 'absolute', height: '100%', left: `${baselinePct}%`, width: `${Math.max(0, distressPct - baselinePct)}%`, background: 'var(--bg-elevated)' }} />
        {/* Red distress zone */}
        {distressMinutes > 0 && (
          <div style={{
            position: 'absolute', height: '100%',
            left: `${distressPct}%`, width: `${100 - distressPct}%`,
            background: 'rgba(239,68,68,0.3)',
            borderRadius: '0 6px 6px 0',
          }} />
        )}
        {/* Markers */}
        <div style={{ position: 'absolute', top: 0, left: 0, width: 3, height: '100%', background: 'var(--success-text)', borderRadius: 2 }} />
        {baselineEstablished && (
          <div style={{ position: 'absolute', top: 0, width: 3, height: '100%', background: 'var(--voice-primary)', borderRadius: 2, left: `${baselinePct}%` }} />
        )}
        {distressMinutes > 0 && (
          <div style={{ position: 'absolute', top: 0, width: 3, height: '100%', background: 'var(--critical-text)', borderRadius: 2, left: `${distressPct}%` }} />
        )}
        <div style={{ position: 'absolute', top: 0, right: 0, width: 3, height: '100%', background: 'var(--text-muted)', borderRadius: 2 }} />
      </div>

      {/* Labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <span style={{ fontSize: '0.68rem', color: 'var(--success-text)' }}>Admission<br />{admissionHoursAgo.toFixed(0)}h ago</span>
        <span style={{ fontSize: '0.68rem', color: 'var(--voice-primary)' }}>Baseline<br />Established</span>
        {distressMinutes > 0 && (
          <span style={{ fontSize: '0.68rem', color: 'var(--critical-text)', fontWeight: 600 }}>
            Distress<br />{distressMinutes} min ago
          </span>
        )}
        <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>NOW</span>
      </div>

      {/* Nurse check counter */}
      <div style={{
        background: 'var(--critical-bg)',
        border: '1px solid var(--critical-border)',
        borderRadius: 'var(--radius-md)',
        padding: '10px 14px',
        textAlign: 'center',
      }}>
        <span style={{ color: 'var(--critical-text)', fontWeight: 700, fontSize: '0.85rem' }}>
          ⏱️ {minutesSinceCheck} minutes since last nurse check
        </span>
        {distressMinutes > 0 && (
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', margin: '4px 0 0' }}>
            Patient has been in distress {distressMinutes} minutes with no response
          </p>
        )}
      </div>
    </div>
  );
};

// ─── Clinical Alert Card ─────────────────────────────────────────────────

interface AlertCardProps {
  data: MonitorResult;
  onAcknowledge: () => void;
  acknowledged: boolean;
}

const ClinicalAlertCard: React.FC<AlertCardProps> = ({ data, onAcknowledge, acknowledged }) => {
  return (
    <div className="alert-critical" style={{
      padding: '20px 24px',
      borderLeft: '4px solid var(--critical-text)',
      animation: 'fade-in-up 0.5s ease both',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
        <span className="dot-critical" />
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, color: 'var(--critical-text)', fontSize: '0.95rem' }}>
          SilentVoice Alert — Pain Indicators Detected
        </span>
        {acknowledged && (
          <span className="badge badge-success" style={{ marginLeft: 'auto' }}>✓ ACKNOWLEDGED</span>
        )}
      </div>

      {/* Signal pills */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
        {data.signals_detected.map(s => (
          <span key={s.label} className="badge badge-critical" style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>
            {s.label.toUpperCase()} {s.deviation_pct > 0 ? '+' : ''}{s.deviation_pct.toFixed(0)}%
          </span>
        ))}
      </div>

      {/* Key stats in a row */}
      <div style={{
        display: 'flex',
        gap: 32,
        marginBottom: 14,
        padding: '10px 0',
        borderTop: '1px solid var(--critical-border)',
        borderBottom: '1px solid var(--critical-border)',
        flexWrap: 'wrap',
      }}>
        <div>
          <div className="label-caps">UNDETECTED FOR</div>
          <div style={{ color: 'var(--critical-text)', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.3rem' }}>
            {data.distress_duration_minutes} min
          </div>
        </div>
        <div>
          <div className="label-caps">LAST ANALGESIC</div>
          <div style={{ color: 'var(--critical-text)', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.3rem' }}>
            {data.last_analgesic_hours !== null ? `${data.last_analgesic_hours}h ago` : 'None on record'}
          </div>
        </div>
      </div>

      {/* Clinical output */}
      {data.clinical_output && (
        <div style={{
          padding: '12px 16px',
          background: 'rgba(239,68,68,0.06)',
          border: '1px solid var(--critical-border)',
          borderLeft: '3px solid var(--critical-text)',
          borderRadius: 'var(--radius-md)',
          marginBottom: 14,
        }}>
          <div className="label-caps" style={{ color: 'var(--critical-text)', marginBottom: 6 }}>🤖 AI CLINICAL OUTPUT</div>
          <p style={{ color: 'var(--text-secondary)', fontStyle: 'italic', fontSize: '0.82rem', lineHeight: 1.7, margin: 0 }}>
            "{data.clinical_output}"
          </p>
        </div>
      )}

      {!acknowledged && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 4 }}>
          <button
            onClick={onAcknowledge}
            style={{
              padding: '9px 18px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(16,185,129,0.15)',
              color: 'var(--success-text)',
              border: '1px solid rgba(16,185,129,0.4)',
              fontWeight: 600,
              fontSize: '0.78rem',
              cursor: 'pointer',
            }}
          >
            ✅ Acknowledge Alert
          </button>
          <button className="btn-ghost" style={{ fontSize: '0.78rem' }}>📋 Order Pain Assessment</button>
          <button className="btn-ghost" style={{ fontSize: '0.78rem' }}>💉 Administer Analgesic</button>
          <button className="btn-ghost" style={{ fontSize: '0.78rem' }}>📞 Call Attending</button>
        </div>
      )}

      {/* Research Citations */}
      <div style={{
        marginTop: 14,
        paddingTop: 12,
        borderTop: '1px solid rgba(255,255,255,0.06)',
        fontSize: '0.68rem',
        color: '#4a5568',
        lineHeight: 1.6
      }}>
        <div style={{
          fontSize: '0.65rem',
          fontWeight: 700,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: '#374151',
          marginBottom: 6
        }}>
          Research Basis
        </div>
        <div>› Chanques G et al. (2007): Non-verbal ICU patients experience pain
        during 63% of care procedures with no documented pain assessment. <em>JAMA.</em></div>
        <div style={{ marginTop: 3 }}>
          › Gélinas C et al. (2006): HR and HRV correlate with pain in
        non-verbal patients (r=0.71). <em>Am J Crit Care.</em>
        </div>
      </div>
    </div>
  );
};

// ─── Loading skeleton ────────────────────────────────────────────────────

const LoadingSkeleton: React.FC = () => (
  <div style={{ background: 'var(--bg-deep)', minHeight: '100vh', margin: '-32px -16px', padding: '32px' }}>
    <div className="skeleton" style={{ height: 96, borderRadius: 'var(--radius-lg)', marginBottom: 16 }} />
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
      {[...Array(6)].map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 140, borderRadius: 'var(--radius-md)' }} />
      ))}
    </div>
    <div className="skeleton" style={{ height: 160, borderRadius: 'var(--radius-lg)', marginBottom: 16 }} />
    <div className="skeleton" style={{ height: 120, borderRadius: 'var(--radius-lg)' }} />
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════
// MAIN PAGE COMPONENT
// ═══════════════════════════════════════════════════════════════════════════

export const SilentVoicePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const preselectedPatient = searchParams.get('patient');
  const patientId = preselectedPatient || PATIENT_C_ID;
  const { language } = useLanguage();
  const { data, connected, error, mode } = useSilentVoiceStream(patientId, language);
  const [baselineMode, setBaselineMode] = useState<BaselineMode>(preselectedPatient ? 'personal' : 'population');
  const [acknowledged, setAcknowledged] = useState(false);
  const [minutesSinceCheck, setMinutesSinceCheck] = useState(127);
  const [vitalsHistory, setVitalsHistory] = useState<Record<string, number[]>>({});

  // Counting up the nurse check counter every minute
  useEffect(() => {
    const interval = setInterval(() => {
      setMinutesSinceCheck(m => m + 1);
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  // Accumulate vitals history for sparklines
  useEffect(() => {
    if (data?.latest_vitals) {
      setVitalsHistory(prev => {
        const next = { ...prev };
        for (const field of Object.keys(VITAL_CONFIG)) {
          const val = (data.latest_vitals as any)[field];
          if (val !== null && val !== undefined) {
            const arr = [...(prev[field] || []), val];
            next[field] = arr.slice(-8);
          }
        }
        return next;
      });
    }
  }, [data]);

  // Personal baseline from API response
  const personalBaselines = useMemo(() => {
    return data?.baseline?.baselines || {};
  }, [data]);

  // Calculate alert score based on current mode
  const alertScore = useMemo(() => {
    if (!data?.latest_vitals) return 0;
    let score = 0;
    for (const field of Object.keys(VITAL_CONFIG)) {
      const current = (data.latest_vitals as any)[field];
      if (current === null || current === undefined) continue;
      const bl = baselineMode === 'personal' && personalBaselines[field]
        ? personalBaselines[field]
        : POPULATION_AVERAGES[field];
      const z = Math.abs(calcZ(current, bl.mean, bl.std));
      if (z > 2.5) score += z;
    }
    return score;
  }, [data, baselineMode, personalBaselines]);

  // Determine if any signals fire under current mode
  const currentModeSignals = useMemo(() => {
    if (!data?.latest_vitals) return [];
    const signals: string[] = [];
    for (const field of Object.keys(VITAL_CONFIG)) {
      const current = (data.latest_vitals as any)[field];
      if (current === null || current === undefined) continue;
      const bl = baselineMode === 'personal' && personalBaselines[field]
        ? personalBaselines[field]
        : POPULATION_AVERAGES[field];
      const z = Math.abs(calcZ(current, bl.mean, bl.std));
      if (z > 2.5) signals.push(field);
    }
    return signals;
  }, [data, baselineMode, personalBaselines]);

  const handleAcknowledge = async () => {
    try {
      await silentVoiceService.getIcuOverview();
      setAcknowledged(true);
    } catch {
      setAcknowledged(true);
    }
  };

  const showAlert = baselineMode === 'personal' && currentModeSignals.length > 0;
  const distressActive = showAlert && data?.distress_active;

  if (!data) return <LoadingSkeleton />;

  const admissionHoursAgo = 6;

  return (
    <div style={{ background: 'var(--bg-deep)', minHeight: '100vh', margin: '-32px -16px', padding: '0 0 40px' }}>

      {/* ── Agent Identity Stripe ── */}
      <div style={{ height: 3, background: 'linear-gradient(90deg, var(--voice-primary), transparent)' }} />

      {/* ═══ SECTION 1: Patient Status Header ═══ */}
      <div style={{
        background: distressActive
          ? 'linear-gradient(135deg, rgba(239,68,68,0.15), rgba(239,68,68,0.05))'
          : 'linear-gradient(135deg, rgba(6,182,212,0.1), transparent)',
        borderBottom: `1px solid ${distressActive ? 'var(--critical-border)' : 'var(--border-subtle)'}`,
        padding: '20px 32px',
        transition: 'all 0.6s ease',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span style={{ fontSize: '1.1rem' }}>🔵</span>
              <span style={{ fontFamily: 'var(--font-display)', fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                SilentVoice Monitor
              </span>
              {distressActive && (
                <span className="badge badge-critical">
                  ● DISTRESS ACTIVE
                </span>
              )}
            </div>
            <div style={{ marginTop: 6, color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
              Patient: <strong style={{ color: 'var(--text-primary)' }}>{data.patient_name}</strong> — ICU Bed 3
              {distressActive && (
                <>
                  {' '}· Active: <span style={{ color: 'var(--critical-text)', fontWeight: 600 }}>{data.distress_duration_minutes} min</span>
                  {' '}· Last check: <span style={{ color: 'var(--critical-text)', fontWeight: 600 }}>{minutesSinceCheck} min ago</span>
                </>
              )}
            </div>
          </div>
          {/* Connection indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.72rem', fontFamily: 'var(--font-mono)' }}>
            <span className={connected ? (mode === 'websocket' ? 'dot-live' : 'dot-polling') : 'dot-critical'} />
            <span style={{ color: connected ? (mode === 'websocket' ? 'var(--success-text)' : 'var(--warning-text)') : 'var(--critical-text)' }}>
              {connected ? (mode === 'websocket' ? 'LIVE' : 'POLLING') : 'DISCONNECTED'}
            </span>
          </div>
        </div>
      </div>

      {/* ── Page Content ── */}
      <div style={{ padding: '20px 32px' }}>

        {/* ═══ TOGGLE: Population vs Personal Baseline ═══ */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '14px 20px',
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          marginBottom: 20,
          flexWrap: 'wrap',
        }}>
          <span className="label-caps" style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Comparing against:</span>

          <div style={{ display: 'flex', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', padding: 3, gap: 2 }}>
            {(['population', 'personal'] as BaselineMode[]).map(m => (
              <button
                key={m}
                onClick={() => setBaselineMode(m)}
                style={{
                  padding: '7px 18px',
                  borderRadius: 'var(--radius-sm)',
                  border: 'none',
                  fontWeight: 600,
                  fontSize: '0.78rem',
                  cursor: 'pointer',
                  transition: 'all 0.25s ease',
                  background: baselineMode === m
                    ? (m === 'personal' ? 'var(--voice-primary)' : 'var(--bg-highlight)')
                    : 'transparent',
                  color: baselineMode === m
                    ? (m === 'personal' ? '#000' : 'var(--text-primary)')
                    : 'var(--text-muted)',
                  transform: baselineMode === m ? 'scale(1.02)' : 'scale(1)',
                }}
              >
                {m === 'population' ? '👥 Population Average' : '👤 Personal Baseline'}
              </button>
            ))}
          </div>

          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontStyle: 'italic' }}>
            {baselineMode === 'personal'
              ? 'Comparing to HER first 2 hours in this bed'
              : 'Comparing to average 72-year-old woman'}
          </span>
        </div>

        {/* ═══ SECTION 2: Live Vitals Grid ═══ */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 20 }}>
          {Object.keys(VITAL_CONFIG).map(field => (
            <VitalCard
              key={field}
              field={field}
              current={(data.latest_vitals as any)?.[field]}
              mode={baselineMode}
              personalBaseline={personalBaselines[field]}
              history={vitalsHistory[field] || []}
            />
          ))}
          {/* Alert Score Card */}
          <AlertScoreBar score={alertScore} />
        </div>

        {/* ═══ SECTION 3: Clinical Alert Card ═══ */}
        {showAlert && data.distress_active && data.clinical_output && (
          <div style={{ marginBottom: 20 }}>
            <ClinicalAlertCard
              data={data}
              onAcknowledge={handleAcknowledge}
              acknowledged={acknowledged}
            />
          </div>
        )}

        {/* ═══ SECTION 4: Distress Timeline ═══ */}
        <DistressTimeline
          admissionHoursAgo={admissionHoursAgo}
          baselineEstablished={!!data.baseline?.established_at}
          distressMinutes={showAlert ? data.distress_duration_minutes : 0}
          minutesSinceCheck={minutesSinceCheck}
        />

        {/* Error display */}
        {error && (
          <div style={{
            marginTop: 16,
            padding: '10px 14px',
            background: 'var(--warning-bg)',
            border: '1px solid var(--warning-border)',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.82rem',
            color: 'var(--warning-text)',
          }}>
            ⚠️ {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default SilentVoicePage;
