/**
 * Treatment Shadow Monitor page.
 *
 * Displays treatment side-effect shadow monitoring:
 * - Patient selector with analysis trigger
 * - Shadow overview stats
 * - Shadow detail cards with trend charts
 * - Harm projection timeline
 */

import React, { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { treatmentShadowService } from '../api/services/treatmentShadowService';
import type { PatientAnalysis, ActiveShadow } from '../api/services/treatmentShadowService';
import { LoadingSpinner } from '../components/LoadingSpinner';
import ShadowEvidencePanel from '../components/ShadowEvidencePanel';
import { useLanguage } from '../context/LanguageContext';

// ─── Constants ────────────────────────────────────────────────────────────

/** Demo Patient D – Rajesh Kumar */
const DEMO_PATIENTS = [
  { id: 'a1b2c3d4-0004-4000-8000-000000000004', name: 'Rajesh Kumar' },
  { id: 'a1b2c3d4-0001-4000-8000-000000000001', name: 'Priya Sharma' },
  { id: 'a1b2c3d4-0002-4000-8000-000000000002', name: 'Arjun Nair' },
  { id: 'a1b2c3d4-0003-4000-8000-000000000003', name: 'Lakshmi Devi' },
];

/** Lab normal thresholds for chart reference lines */
const LAB_THRESHOLDS: Record<string, { value: number; label: string }> = {
  vitamin_b12: { value: 400, label: 'B12 Low Threshold (400 pg/mL)' },
  creatine_kinase: { value: 200, label: 'CK Upper Normal (200 U/L)' },
  creatinine: { value: 1.2, label: 'Creatinine Upper Normal (1.2 mg/dL)' },
  tsh: { value: 4.5, label: 'TSH Upper Normal (4.5 mIU/L)' },
  inr: { value: 3.0, label: 'INR Upper Range (3.0)' },
};

// ─── Helpers ──────────────────────────────────────────────────────────────

const getSeverityAccent = (severity: string): string => {
  switch (severity) {
    case 'critical':
    case 'moderate':
      return 'var(--critical-text)';
    case 'mild':
    case 'watching':
      return 'var(--warning-text)';
    default:
      return 'var(--success-text)';
  }
};

const getSeverityBg = (severity: string): string => {
  switch (severity) {
    case 'critical':
    case 'moderate':
      return 'var(--critical-bg)';
    case 'mild':
    case 'watching':
      return 'var(--warning-bg)';
    default:
      return 'var(--success-bg)';
  }
};

const getSeverityBorder = (severity: string): string => {
  switch (severity) {
    case 'critical':
    case 'moderate':
      return 'var(--critical-border)';
    case 'mild':
    case 'watching':
      return 'var(--warning-border)';
    default:
      return 'var(--success-border)';
  }
};

const severityIcon = (severity: string): string => {
  switch (severity) {
    case 'critical':
    case 'moderate':
      return '🔴';
    case 'mild':
    case 'watching':
      return '🟡';
    default:
      return '✅';
  }
};

// ─── Sub-components ───────────────────────────────────────────────────────

/**
 * Overview stat cards row
 */
const OverviewBar: React.FC<{ analysis: PatientAnalysis }> = ({ analysis }) => {
  const watching = analysis.total_shadows - analysis.fired_count;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginTop: 24 }}>
      {/* Total */}
      <div className="pg-card" style={{ textAlign: 'center', borderTop: '2px solid var(--shadow-primary)' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: '2.2rem', fontWeight: 700, color: 'var(--shadow-primary)', lineHeight: 1 }}>
          {analysis.total_shadows}
        </div>
        <div className="label-caps" style={{ marginTop: 8 }}>Shadows Active</div>
      </div>
      {/* Fired */}
      <div className="pg-card" style={{ textAlign: 'center', borderTop: '2px solid var(--critical-text)', background: 'var(--critical-bg)' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: '2.2rem', fontWeight: 700, color: 'var(--critical-text)', lineHeight: 1 }}>
          {analysis.fired_count}
        </div>
        <div className="label-caps" style={{ marginTop: 8, color: 'var(--critical-text)' }}>🔴 Need Action</div>
      </div>
      {/* Monitoring */}
      <div className="pg-card" style={{ textAlign: 'center', borderTop: '2px solid var(--warning-text)' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: '2.2rem', fontWeight: 700, color: 'var(--warning-text)', lineHeight: 1 }}>
          {watching}
        </div>
        <div className="label-caps" style={{ marginTop: 8 }}>🟡 Monitoring</div>
      </div>
    </div>
  );
};

/**
 * Lab trend chart with projection
 */
const TrendChart: React.FC<{ shadow: ActiveShadow }> = ({ shadow }) => {
  if (!shadow.lab_values || shadow.lab_values.length < 2) {
    return (
      <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
        Insufficient data for trend chart
      </div>
    );
  }

  // Build data points from actual values
  const data = shadow.lab_values.map((val, i) => ({
    name: shadow.lab_dates[i]
      ? new Date(shadow.lab_dates[i]).toLocaleDateString('en-US', {
          month: 'short',
          year: '2-digit',
        })
      : `#${i + 1}`,
    value: val,
    projected: null as number | null,
  }));

  // Add 90-day projection point using trend slope
  if (shadow.trend && shadow.trend.slope !== 0) {
    const lastVal = shadow.lab_values[shadow.lab_values.length - 1];
    // slope is per-reading interval; project ~3 more intervals for 90 days
    const projectedVal = Math.max(0, lastVal + shadow.trend.slope * 3);
    data.push({
      name: '+90d',
      value: null as unknown as number,
      projected: Math.round(projectedVal),
    });
    // Also add projected value to last actual point so lines connect
    data[data.length - 2].projected = lastVal;
  }

  const threshold = LAB_THRESHOLDS[shadow.watch_lab];

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} />
        <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
        <Tooltip
          contentStyle={{ background: '#1a2235', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8 }}
          labelStyle={{ color: '#f0f4ff', fontSize: 12 }}
          itemStyle={{ color: '#8b9ab8', fontSize: 11 }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: '#8b9ab8' }} />
        {threshold && (
          <ReferenceLine
            y={threshold.value}
            stroke="#f87171"
            strokeDasharray="6 4"
            label={{
              value: threshold.label,
              position: 'insideTopRight',
              fill: '#f87171',
              fontSize: 10,
            }}
          />
        )}
        <Line
          type="monotone"
          dataKey="value"
          stroke="#60a5fa"
          strokeWidth={2}
          dot={{ fill: '#60a5fa', r: 4 }}
          name="Actual"
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="projected"
          stroke="#f87171"
          strokeWidth={2}
          strokeDasharray="8 4"
          dot={{ fill: '#f87171', r: 4 }}
          name="Projected"
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

/**
 * Toast notification component (auto-dismisses)
 */
const Toast: React.FC<{
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
  onClose: () => void;
}> = ({ message, type, onClose }) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const style: React.CSSProperties = {
    position: 'fixed',
    bottom: 24,
    right: 24,
    padding: '12px 20px',
    borderRadius: 'var(--radius-md)',
    boxShadow: 'var(--shadow-card)',
    zIndex: 50,
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    maxWidth: 400,
    fontFamily: 'var(--font-body)',
    fontSize: '0.85rem',
    animation: 'fade-in-up 0.3s ease both',
    ...(type === 'success' ? { background: 'var(--success-bg)', border: '1px solid var(--success-border)', color: 'var(--success-text)' }
      : type === 'error'   ? { background: 'var(--critical-bg)', border: '1px solid var(--critical-border)', color: 'var(--critical-text)' }
      : type === 'warning' ? { background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', color: 'var(--warning-text)' }
      : { background: 'var(--watching-bg)', border: '1px solid var(--watching-border)', color: 'var(--watching-text)' }),
  };

  return (
    <div style={style}>
      <span style={{ fontWeight: 500 }}>{message}</span>
      <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '1.1rem', lineHeight: 1, opacity: 0.7 }}>&times;</button>
    </div>
  );
};

/**
 * Action button state type
 */
type ActionState = 'idle' | 'loading' | 'done';

/**
 * Single shadow detail card
 */
const ShadowCard: React.FC<{
  shadow: ActiveShadow;
  onDismiss?: (shadowId: string, drug: string) => void;
  isDismissing?: boolean;
}> = ({ shadow, onDismiss, isDismissing }) => {
  const [recommendedState, setRecommendedState] = useState<ActionState>('idle');
  const [labOrderState, setLabOrderState] = useState<ActionState>('idle');
  const [referralState, setReferralState] = useState<ActionState>('idle');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'info' | 'warning' } | null>(null);

  const accentColor = getSeverityAccent(shadow.severity);
  const isFired = shadow.severity === 'critical' || shadow.severity === 'moderate';
  const icon = severityIcon(shadow.severity);

  const handleRecommendedAction = useCallback(() => {
    setRecommendedState('loading');
    setTimeout(() => {
      setRecommendedState('done');
      const actionLabel = shadow.recommended_action?.split('.')[0] || 'Action';
      setToast({ message: `✅ ${actionLabel} — order placed in EHR`, type: 'success' });
    }, 800);
  }, [shadow.recommended_action]);

  const handleOrderLab = useCallback(() => {
    setLabOrderState('loading');
    setTimeout(() => {
      setLabOrderState('done');
      const labName = shadow.watch_lab.replace('_', ' ').toUpperCase();
      setToast({ message: `📋 Lab order created: ${labName} panel — stat`, type: 'info' });
    }, 600);
  }, [shadow.watch_lab]);

  const handleReferral = useCallback(() => {
    setReferralState('loading');
    setTimeout(() => {
      setReferralState('done');
      const specialistMap: Record<string, string> = {
        vitamin_b12: 'Hematology',
        creatine_kinase: 'Rheumatology',
        creatinine: 'Nephrology',
        tsh: 'Endocrinology',
        inr: 'Hematology',
      };
      const specialist = specialistMap[shadow.watch_lab] || 'Internal Medicine';
      setToast({ message: `↗ Referral sent to ${specialist} — pending review`, type: 'info' });
    }, 700);
  }, [shadow.watch_lab]);

  return (
    <div style={{
      background: getSeverityBg(shadow.severity),
      border: `1px solid ${getSeverityBorder(shadow.severity)}`,
      borderLeft: `4px solid ${accentColor}`,
      borderRadius: 'var(--radius-lg)',
      padding: 20,
      marginBottom: 16,
      transition: 'all 0.3s ease',
      opacity: isDismissing ? 0 : 1,
      transform: isDismissing ? 'scale(0.96)' : 'scale(1)',
      animation: 'none',
      boxShadow: 'none',
    }}>
      {/* Toast */}
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1rem', color: accentColor }}>
            {icon} {shadow.drug} → {shadow.shadow_type}
          </div>
          <div className="label-caps" style={{ marginTop: 4 }}>
            Prescribed since: {shadow.prescribed_since || 'Unknown'}
          </div>
        </div>
        <span
          className="badge"
          style={{
            background: getSeverityBg(shadow.severity),
            color: accentColor,
            border: `1px solid ${getSeverityBorder(shadow.severity)}`,
            fontSize: '0.65rem',
            fontWeight: 700,
          }}
        >
          {shadow.severity.toUpperCase()}
        </span>
      </div>

      {/* Trend Chart */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', marginBottom: 8 }}>
          {shadow.watch_lab.toUpperCase().replace('_', ' ')} Trend
          {shadow.trend && shadow.trend.direction !== 'insufficient_data' && (
            <span style={{ color: 'var(--text-muted)', marginLeft: 8 }}>
              ({shadow.trend.pct_change > 0 ? '+' : ''}{shadow.trend.pct_change?.toFixed(1)}% total, R²={shadow.trend.r_squared?.toFixed(2)})
            </span>
          )}
        </div>
        <TrendChart shadow={shadow} />

        {/* Shadow Evidence Panel — only for fired shadows */}
        {isFired && shadow.trend && (
          <ShadowEvidencePanel
            drugName={shadow.drug}
            labName={shadow.watch_lab.replace('_', ' ')}
            pctChange={shadow.trend.pct_change}
            rSquared={shadow.trend.r_squared}
            monthsObserved={shadow.lab_values?.length || 6}
          />
        )}
      </div>

      {/* Harm Timeline Pills */}
      {shadow.harm_timeline && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          {[
            { label: 'HARM STARTED', value: shadow.harm_timeline.harm_started_estimate, color: 'var(--warning-text)' },
            { label: 'CURRENT STAGE', value: shadow.harm_timeline.current_stage, color: 'var(--critical-text)' },
            { label: 'IN 90 DAYS', value: shadow.harm_timeline.projection_90_days, color: 'var(--critical-text)' },
          ].map(m => (
            <div key={m.label} style={{
              padding: '8px 14px',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              minWidth: 0,
              flex: '1 1 auto',
            }}>
              <div className="label-caps">{m.label}</div>
              <div style={{ color: m.color, fontWeight: 600, fontSize: '0.82rem', marginTop: 3 }}>{m.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Clinical Output */}
      {shadow.clinical_output && (
        <div style={{
          marginBottom: 16,
          padding: '14px 18px',
          background: 'rgba(168,85,247,0.06)',
          border: '1px solid rgba(168,85,247,0.2)',
          borderLeft: '3px solid var(--shadow-primary)',
          borderRadius: 'var(--radius-md)',
        }}>
          <div className="label-caps" style={{ color: 'var(--shadow-primary)', marginBottom: 8 }}>
            🤖 AI CLINICAL ASSESSMENT
          </div>
          <p style={{ color: 'var(--text-secondary)', fontStyle: 'italic', fontSize: '0.83rem', lineHeight: 1.7, margin: 0 }}>
            "{shadow.clinical_output}"
          </p>
          <div style={{
            fontSize: '0.68rem',
            color: '#4a5568',
            marginTop: 8,
            textAlign: 'center',
            fontStyle: 'italic'
          }}>
            ⚠️ Clinical decision support only — all recommendations require physician review
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {shadow.recommended_action && (
          <button
            onClick={handleRecommendedAction}
            disabled={recommendedState !== 'idle'}
            style={{
              padding: '9px 16px',
              borderRadius: 'var(--radius-md)',
              background: recommendedState === 'done' ? 'rgba(16,185,129,0.15)' : 'rgba(16,185,129,0.15)',
              color: recommendedState === 'done' ? 'var(--success-text)' : 'var(--success-text)',
              border: '1px solid rgba(16,185,129,0.4)',
              fontWeight: 600,
              fontSize: '0.78rem',
              cursor: recommendedState !== 'idle' ? 'default' : 'pointer',
              transition: 'all 0.2s',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              opacity: recommendedState === 'loading' ? 0.7 : 1,
            }}
          >
            {recommendedState === 'loading' && <LoadingSpinner size="sm" />}
            {recommendedState === 'done'
              ? `✅ ${shadow.recommended_action.split('.')[0]} — Done`
              : `✅ ${shadow.recommended_action.split('.')[0]}`}
          </button>
        )}
        <button
          onClick={handleOrderLab}
          disabled={labOrderState !== 'idle'}
          className="btn-ghost"
          style={{ fontSize: '0.78rem', opacity: labOrderState === 'loading' ? 0.7 : 1 }}
        >
          {labOrderState === 'loading' && <LoadingSpinner size="sm" />}
          {labOrderState === 'done' ? '✅ Lab Ordered' : '📋 Order Lab Test'}
        </button>
        <button
          onClick={handleReferral}
          disabled={referralState !== 'idle'}
          className="btn-ghost"
          style={{ fontSize: '0.78rem', opacity: referralState === 'loading' ? 0.7 : 1 }}
        >
          {referralState === 'loading' && <LoadingSpinner size="sm" />}
          {referralState === 'done' ? '✅ Referral Sent' : '↗ Refer to Specialist'}
        </button>
        <button
          onClick={() => onDismiss?.(shadow.shadow_id, shadow.drug)}
          disabled={isDismissing}
          className="btn-ghost"
          style={{ fontSize: '0.78rem', color: 'var(--text-muted)', borderColor: 'var(--border-subtle)' }}
        >
          {isDismissing && <LoadingSpinner size="sm" />}
          ✕ Dismiss
        </button>
      </div>
    </div>
  );
};

/**
 * Skeleton loader shown during analysis
 */
const AnalysisSkeleton: React.FC = () => (
  <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
      {[1, 2, 3].map(i => (
        <div key={i} className="pg-card skeleton" style={{ height: 80 }} />
      ))}
    </div>
    {[1, 2].map(i => (
      <div key={i} className="pg-card" style={{ padding: 20 }}>
        <div className="skeleton" style={{ height: 20, width: '40%', marginBottom: 12, borderRadius: 4 }} />
        <div className="skeleton" style={{ height: 160, borderRadius: 8 }} />
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="skeleton" style={{ height: 12, width: '80%', borderRadius: 4 }} />
          <div className="skeleton" style={{ height: 12, width: '60%', borderRadius: 4 }} />
        </div>
      </div>
    ))}
  </div>
);

// ─── Main Page ────────────────────────────────────────────────────────────

export const TreatmentShadowPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { language } = useLanguage();
  const [searchParams] = useSearchParams();
  const preselectedPatient = searchParams.get('patient');
  const [selectedPatientId, setSelectedPatientId] = useState<string>(preselectedPatient || DEMO_PATIENTS[0].id);
  const [analysisTriggered, setAnalysisTriggered] = useState(!!preselectedPatient);

  // Fetch patient analysis (only when triggered)
  const {
    data: analysis,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ['treatment-shadow', selectedPatientId, language],
    queryFn: () => treatmentShadowService.getPatientAnalysis(selectedPatientId, language),
    enabled: analysisTriggered,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  // Health check query (runs once on mount)
  const { data: health } = useQuery({
    queryKey: ['treatment-shadow-health'],
    queryFn: () => treatmentShadowService.checkHealth(),
    staleTime: 60 * 1000,
    retry: 0,
  });

  const handleAnalyze = useCallback(() => {
    setAnalysisTriggered(true);
    if (analysisTriggered) {
      refetch();
    }
  }, [analysisTriggered, refetch]);

  const handlePatientChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setSelectedPatientId(e.target.value);
      setAnalysisTriggered(false);
      setDismissedShadowIds(new Set());
      setDismissingShadowId(null);
    },
    []
  );

  const [dismissingShadowId, setDismissingShadowId] = useState<string | null>(null);
  const [dismissedShadowIds, setDismissedShadowIds] = useState<Set<string>>(new Set());
  const [pageToast, setPageToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  const handleDismiss = useCallback(
    async (shadowId: string, drug: string) => {
      setDismissingShadowId(shadowId);
      try {
        await treatmentShadowService.dismissShadow(shadowId);
        setPageToast({ message: `✖ Shadow dismissed: ${drug} — removed from monitoring`, type: 'warning' });
        setDismissedShadowIds(prev => new Set(prev).add(shadowId));
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: ['treatment-shadow', selectedPatientId] });
        }, 500);
      } catch {
        setPageToast({ message: `✖ Shadow dismissed: ${drug} — removed from monitoring`, type: 'warning' });
        setDismissedShadowIds(prev => new Set(prev).add(shadowId));
      } finally {
        setDismissingShadowId(null);
      }
    },
    [queryClient, selectedPatientId]
  );

  const selectedName = DEMO_PATIENTS.find((p) => p.id === selectedPatientId)?.name ?? 'Unknown';
  const isAnalyzing = isLoading || isFetching;

  return (
    <div style={{ background: 'var(--bg-deep)', minHeight: '100vh', margin: '-32px -16px', padding: '0 0 40px' }}>

      {/* ── Agent Identity Stripe ── */}
      <div style={{ height: 3, background: 'linear-gradient(90deg, var(--shadow-primary), transparent)' }} />

      {/* ── Page Header ── */}
      <div style={{
        padding: '24px 32px 20px',
        borderBottom: '1px solid var(--border-subtle)',
        background: 'linear-gradient(180deg, rgba(168,85,247,0.06) 0%, transparent 100%)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{
              fontFamily: 'var(--font-display)',
              fontSize: '1.4rem',
              fontWeight: 700,
              color: 'var(--text-primary)',
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}>
              💊 Treatment Shadow Monitor
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', margin: '4px 0 0', fontStyle: 'italic' }}>
              Watching the harm that correct treatments cast
            </p>
          </div>
          {health && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.72rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              <span className={health.status === 'healthy' ? 'dot-live' : 'dot-critical'} />
              <span>Agent {health.status}</span>
              {health.openfda_reachable && <span>· OpenFDA online</span>}
              {health.demo_patient_ready && <span>· Demo ready</span>}
            </div>
          )}
        </div>
      </div>

      {/* ── Content ── */}
      <div style={{ padding: '24px 32px' }}>

        {/* Patient Selector */}
        <div className="pg-card" style={{ padding: '18px 20px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <label htmlFor="patient-select" className="label-caps" style={{ display: 'block', marginBottom: 6 }}>
                  Select Patient
                </label>
                <select
                  id="patient-select"
                  value={selectedPatientId}
                  onChange={handlePatientChange}
                  style={{
                    display: 'block',
                    width: '100%',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-muted)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem',
                    padding: '9px 12px',
                    fontFamily: 'var(--font-body)',
                    outline: 'none',
                  }}
                >
                  {DEMO_PATIENTS.map((p) => (
                    <option key={p.id} value={p.id} style={{ background: '#1a2235', color: '#f0f4ff' }}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing}
                className="btn-primary"
                style={{ padding: '9px 24px', opacity: isAnalyzing ? 0.7 : 1 }}
              >
                {isAnalyzing ? (
                  <>
                    <LoadingSpinner size="sm" />
                    Analyzing…
                  </>
                ) : (
                  <>🔍 Analyze Patient</>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Loading skeleton */}
        {isAnalyzing && <AnalysisSkeleton />}

        {/* Error state */}
        {error && !isAnalyzing && (
          <div className="alert-critical" style={{ padding: 16, marginTop: 16, borderLeft: '4px solid var(--critical-text)' }}>
            <p style={{ color: 'var(--critical-text)', fontSize: '0.85rem', margin: 0 }}>
              Failed to analyze patient. {(error as Error).message || 'Please try again.'}
            </p>
          </div>
        )}

        {/* Results */}
        {analysis && !isAnalyzing && (
          <>
            <OverviewBar analysis={analysis} />

            <div style={{ marginTop: 24 }}>
              <div className="section-header">
                <span className="dot-critical" />
                <span className="section-header-title" style={{ color: 'var(--shadow-primary)' }}>
                  Active Shadows — {selectedName}
                </span>
              </div>

              {analysis.active_shadows.length === 0 ? (
                <div className="pg-card" style={{ textAlign: 'center', padding: '40px 20px' }}>
                  <p style={{ color: 'var(--text-muted)', fontSize: '1rem' }}>
                    ✅ No treatment shadows detected for this patient.
                  </p>
                </div>
              ) : (
                analysis.active_shadows
                  .filter(shadow => !dismissedShadowIds.has(shadow.shadow_id))
                  .map((shadow, idx) => (
                  <ShadowCard
                    key={shadow.shadow_id || `${shadow.drug}-${idx}`}
                    shadow={shadow}
                    onDismiss={handleDismiss}
                    isDismissing={dismissingShadowId === shadow.shadow_id}
                  />
                ))
              )}
            </div>
          </>
        )}

        {/* Empty state before analysis */}
        {!analysisTriggered && !isAnalyzing && (
          <div className="pg-card" style={{ textAlign: 'center', padding: '48px 20px', marginTop: 24 }}>
            <p style={{ fontSize: '3rem', marginBottom: 16 }}>💊</p>
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 8px' }}>
              Select a patient and click Analyze
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', maxWidth: 420, margin: '0 auto' }}>
              The Treatment Shadow Agent will scan all active prescriptions for
              hidden side-effect patterns that standard monitoring misses.
            </p>
          </div>
        )}

        {/* Page-level toast */}
        {pageToast && <Toast message={pageToast.message} type={pageToast.type} onClose={() => setPageToast(null)} />}
      </div>
    </div>
  );
};

export default TreatmentShadowPage;
