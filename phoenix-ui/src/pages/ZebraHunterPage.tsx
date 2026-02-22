/**
 * Zebra Hunter Page — Rare Disease Detector with Ghost Protocol.
 *
 * Sections:
 *  1. Patient selector + analyze button with progress steps
 *  2. Result display (zebra found vs ghost protocol)
 *  3. Missed Clue Timeline (animated, red dots for diagnosable visits)
 *  4. Ghost Cases Panel
 */

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { zebraHunterService } from '../api/services/zebraHunterService';
import EvidencePanel from '../components/EvidencePanel';
import { useLanguage } from '../context/LanguageContext';
import type {
  AnalyzeResponse,
  MatchResponse,
  TimelineEntry,
  GhostProtocolResult,
  GhostCaseResponse,
  ZebraHunterHealth,
} from '../api/services/zebraHunterService';

// ── Demo patients ─────────────────────────────────────────────────────────
const DEMO_PATIENTS = [
  { id: 'a1b2c3d4-0001-4000-8000-000000000001', name: 'Priya Sharma', label: 'Patient A — Priya Sharma (EDS suspected)' },
  { id: 'a1b2c3d4-0002-4000-8000-000000000002', name: 'Arjun Nair', label: 'Patient B — Arjun Nair (Novel cluster)' },
];

// ── Analysis progress steps ───────────────────────────────────────────────
const PROGRESS_STEPS = [
  'Loading visit history…',
  'Extracting symptoms with AI…',
  'Searching Orphadata rare-disease DB…',
  'Reconstructing missed clues…',
  'Generating clinical recommendation…',
];

// ── Sub-components ────────────────────────────────────────────────────────

/** Animated progress stepper shown during analysis */
const AnalysisProgress: React.FC<{ step: number }> = ({ step }) => (
  <div style={{
    background: 'var(--warning-bg)',
    border: '1px solid var(--warning-border)',
    borderLeft: '4px solid var(--zebra-primary)',
    borderRadius: 'var(--radius-lg)',
    padding: 20,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
      <div style={{
        width: 20, height: 20,
        border: '2px solid var(--zebra-primary)',
        borderTopColor: 'transparent',
        borderRadius: '50%',
        animation: 'spin 1s linear infinite',
      }} />
      <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, color: 'var(--zebra-primary)', fontSize: '0.85rem' }}>
        Analyzing…
      </span>
    </div>
    <ol style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {PROGRESS_STEPS.map((label, i) => (
        <li key={i} style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          fontSize: '0.8rem',
          color: i <= step ? 'var(--zebra-primary)' : 'var(--text-muted)',
          fontWeight: i <= step ? 500 : 400,
        }}>
          <span style={{
            width: 16, height: 16,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.65rem',
            flexShrink: 0,
          }}>
            {i < step ? '✓' : i === step ? '▸' : '○'}
          </span>
          {label}
        </li>
      ))}
    </ol>
  </div>
);

/** Disease match card */
const MatchCard: React.FC<{ match: MatchResponse; rank: number }> = ({ match, rank }) => {
  const isTop = rank === 1;
  return (
    <div style={{
      background: isTop
        ? 'linear-gradient(135deg, rgba(245,158,11,0.1), rgba(245,158,11,0.03))'
        : 'var(--bg-elevated)',
      border: `1px solid ${isTop ? 'rgba(245,158,11,0.4)' : 'var(--border-subtle)'}`,
      borderRadius: 'var(--radius-lg)',
      padding: 20,
      position: 'relative',
      overflow: 'hidden',
      transition: 'all 0.2s ease',
    }}>
      {/* Background confidence fill */}
      <div style={{
        position: 'absolute', top: 0, left: 0, bottom: 0,
        width: `${match.confidence}%`,
        background: isTop ? 'rgba(245,158,11,0.06)' : 'rgba(255,255,255,0.02)',
        transition: 'width 1.2s cubic-bezier(0.4,0,0.2,1)',
        pointerEvents: 'none',
      }} />

      <div style={{ position: 'relative' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
          <div>
            {isTop && <div className="label-caps" style={{ color: 'var(--zebra-primary)', marginBottom: 4 }}>#1 TOP MATCH</div>}
            {!isTop && <div className="label-caps" style={{ marginBottom: 4 }}>#{rank}</div>}
            <h4 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.95rem', margin: 0 }}>
              {match.disease}
            </h4>
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--text-muted)', margin: '3px 0 0' }}>
              ORPHA:{match.orphacode}
            </p>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 12 }}>
            <div style={{
              fontFamily: 'var(--font-display)',
              fontSize: isTop ? '2.4rem' : '1.8rem',
              fontWeight: 700,
              color: isTop ? 'var(--zebra-primary)' : match.confidence >= 50 ? 'var(--warning-text)' : 'var(--text-secondary)',
              lineHeight: 1,
            }}>
              {match.confidence}%
            </div>
            <div className="label-caps" style={{ color: 'var(--text-muted)', marginTop: 2 }}>CONFIDENCE</div>
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {match.matching_symptoms.map((s, i) => (
            <span key={i} style={{
              background: 'var(--bg-surface)',
              color: 'var(--text-secondary)',
              fontSize: '0.68rem',
              padding: '3px 8px',
              borderRadius: 100,
              border: '1px solid var(--border-subtle)',
            }}>
              {s}
            </span>
          ))}
        </div>

        {match.url && (
          <a href={match.url} target="_blank" rel="noreferrer" style={{
            display: 'inline-block',
            marginTop: 10,
            fontSize: '0.72rem',
            color: 'var(--voice-primary)',
            textDecoration: 'none',
          }}>
            View on Orphanet →
          </a>
        )}
      </div>
    </div>
  );
};

/** Single timeline dot */
const TimelineDot: React.FC<{ entry: TimelineEntry; isLast: boolean; animIndex: number; totalVisits: number }> = ({ entry, isLast, animIndex, totalVisits }) => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), animIndex * 400);
    return () => clearTimeout(timer);
  }, [animIndex]);

  const cardStyle: React.CSSProperties = isLast
    ? { border: '1px solid var(--success-border)', background: 'var(--success-bg)', borderLeft: '4px solid var(--success-text)' }
    : entry.was_diagnosable
    ? { border: '1px solid var(--critical-border)', background: 'var(--critical-bg)', borderLeft: '4px solid var(--critical-text)' }
    : { border: '1px solid var(--border-subtle)', background: 'var(--bg-elevated)', borderLeft: '4px solid var(--border-muted)' };

  const dotBg = isLast ? 'var(--success-text)' : entry.was_diagnosable ? 'var(--critical-text)' : 'var(--text-muted)';

  return (
    <div style={{
      display: 'flex',
      gap: 16,
      opacity: visible ? 1 : 0,
      transform: visible ? 'translateY(0)' : 'translateY(16px)',
      transition: 'opacity 0.5s ease, transform 0.5s ease',
    }}>
      {/* Vertical connector + dot */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
        <div style={{
          width: 28, height: 28, borderRadius: '50%',
          background: dotBg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontWeight: 700, fontSize: '0.72rem', color: '#000', flexShrink: 0, zIndex: 1,
        }}>
          {entry.visit_number}
        </div>
        {!isLast && <div style={{ width: 2, flex: 1, background: 'var(--border-subtle)', minHeight: 24, marginTop: 4 }} />}
      </div>

      {/* Content card */}
      <div style={{ ...cardStyle, borderRadius: 'var(--radius-md)', padding: '14px 16px', flex: 1, marginBottom: 12 }}>
        {/* Header row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--text-muted)' }}>
              {entry.visit_date}
            </div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.88rem', marginTop: 2 }}>
              {entry.diagnosis_given}
            </div>
          </div>
          <div>
            {isLast && (
              <span className="badge badge-success">🦓 EDS DETECTED</span>
            )}
            {!isLast && entry.was_diagnosable && (
              <span className="badge badge-critical">🔴 DIAGNOSABLE — {entry.confidence}%</span>
            )}
          </div>
        </div>

        {/* FIRST MISSED banner */}
        {entry.is_first_diagnosable && (
          <div style={{
            marginBottom: 8,
            padding: '7px 12px',
            background: 'rgba(239,68,68,0.15)',
            border: '1px solid var(--critical-border)',
            borderRadius: 'var(--radius-sm)',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <span style={{ fontSize: '0.85rem' }}>⚡</span>
            <span style={{ color: 'var(--critical-text)', fontWeight: 700, fontSize: '0.75rem' }}>
              FIRST MISSED — Diagnosis was possible from this visit
            </span>
          </div>
        )}

        {/* Missed clues list */}
        {entry.missed_clues.length > 0 && (
          <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 4 }}>
            {entry.missed_clues.map((clue, i) => (
              <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                <span style={{ color: 'var(--critical-text)', flexShrink: 0 }}>›</span>
                {clue}
              </li>
            ))}
          </ul>
        )}

        {/* Reason */}
        {entry.reason && (
          <div style={{ marginTop: 8, fontSize: '0.75rem', fontStyle: 'italic', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            {entry.reason}
          </div>
        )}
      </div>
    </div>
  );
};

/** Ghost Protocol full-screen modal */
const GhostModal: React.FC<{
  ghost: GhostProtocolResult;
  onClose: () => void;
  onReport: () => void;
  reporting: boolean;
}> = ({ ghost, onClose, onReport, reporting }) => (
  <div style={{
    position: 'fixed', inset: 0, zIndex: 50,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'rgba(0,0,0,0.8)',
    animation: 'fade-in 0.2s ease both',
  }}>
    <div style={{
      background: '#050a12',
      border: '2px solid var(--critical-border)',
      borderRadius: 'var(--radius-xl)',
      maxWidth: 480,
      width: '100%',
      margin: '0 16px',
      padding: 32,
      boxShadow: '0 24px 80px rgba(239,68,68,0.2)',
      animation: 'fade-in-up 0.3s ease both',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: '2.5rem' }}>👻</span>
          <div>
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.4rem', fontWeight: 900, color: 'var(--critical-text)', margin: 0, letterSpacing: '0.04em' }}>
              GHOST PROTOCOL
            </h2>
            <p style={{ color: 'var(--warning-text)', fontSize: '0.78rem', margin: '2px 0 0' }}>
              Unknown Disease Cluster Detected
            </p>
          </div>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.5rem', lineHeight: 1 }}>×</button>
      </div>

      {/* Body */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="alert-critical" style={{ padding: '12px 16px', borderRadius: 'var(--radius-md)' }}>
          <p style={{ fontSize: '0.82rem', color: 'var(--critical-text)', margin: 0 }}>{ghost.message}</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: '0.82rem' }}>
          <div style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', padding: '10px 12px' }}>
            <div className="label-caps">Ghost ID</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--critical-text)', fontSize: '0.78rem', marginTop: 3 }}>
              {ghost.ghost_id}
            </div>
          </div>
          <div style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', padding: '10px 12px' }}>
            <div className="label-caps">Patient Cluster</div>
            <div style={{ fontWeight: 700, color: 'var(--critical-text)', fontSize: '0.9rem', marginTop: 3 }}>
              {ghost.patient_count} patients
            </div>
          </div>
        </div>

        <div>
          <div className="label-caps" style={{ marginBottom: 6 }}>Symptom Signature</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {ghost.symptom_signature.map((s, i) => (
              <span key={i} className="badge badge-critical" style={{ fontFamily: 'var(--font-mono)', fontWeight: 400 }}>{s}</span>
            ))}
          </div>
        </div>

        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--text-muted)' }}>
          Hash: {ghost.symptom_hash}
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
        <button
          onClick={onReport}
          disabled={reporting}
          className="btn-primary"
          style={{ flex: 1, background: 'linear-gradient(135deg, #dc2626, #b91c1c)', justifyContent: 'center', opacity: reporting ? 0.7 : 1 }}
        >
          {reporting ? 'Reporting…' : '📋 Report to ICMR'}
        </button>
        <button onClick={onClose} className="btn-ghost" style={{ padding: '10px 16px' }}>Close</button>
      </div>
    </div>
  </div>
);

/** Ghost Cases Panel */
const GhostCasesPanel: React.FC<{
  cases: GhostCaseResponse[];
  onReport: (ghostId: string) => void;
}> = ({ cases, onReport }) => {
  if (cases.length === 0) {
    return (
      <div className="pg-card" style={{ textAlign: 'center', padding: '32px 20px' }}>
        <span style={{ fontSize: '2.5rem', display: 'block', marginBottom: 8 }}>👻</span>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
          No ghost cases yet. Analyze patients to activate Ghost Protocol.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {cases.map((c) => (
        <div key={c.ghost_id} style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 16,
          padding: '14px 16px',
          background: 'var(--ghost-bg)',
          border: '1px solid var(--ghost-border)',
          borderLeft: '4px solid var(--ghost-text)',
          borderRadius: 'var(--radius-md)',
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--ghost-text)', fontSize: '0.8rem' }}>
                {c.ghost_id}
              </span>
              {c.status === 'alert_fired' && <span className="badge badge-critical">🚨 ALERT</span>}
              {c.status === 'reported' && <span className="badge badge-watching">📋 Reported</span>}
              {c.status !== 'alert_fired' && c.status !== 'reported' && <span className="badge" style={{ color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}>👁️ Watching</span>}
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{c.patient_count} patient(s)</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
              {c.symptom_signature.map((s, i) => (
                <span key={i} className="badge badge-ghost" style={{ fontFamily: 'var(--font-mono)', fontWeight: 400 }}>{s}</span>
              ))}
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>First seen: {c.first_seen}</div>
          </div>
          {c.status === 'alert_fired' && (
            <button
              onClick={() => onReport(c.ghost_id)}
              style={{
                padding: '7px 14px',
                background: 'rgba(239,68,68,0.15)',
                border: '1px solid var(--critical-border)',
                color: 'var(--critical-text)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer',
                flexShrink: 0,
              }}
            >
              Report
            </button>
          )}
          {c.status === 'reported' && (
            <span style={{ fontSize: '0.75rem', color: 'var(--watching-text)', flexShrink: 0 }}>
              Reported to {c.reported_to}
            </span>
          )}
        </div>
      ))}
    </div>
  );
};

/** Loading skeleton */
const AnalysisSkeleton: React.FC = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
    <div className="pg-card skeleton" style={{ height: 80 }} />
    <div className="pg-card" style={{ padding: 20 }}>
      <div className="skeleton" style={{ height: 16, width: '30%', marginBottom: 12, borderRadius: 4 }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ display: 'flex', gap: 12 }}>
            <div className="skeleton" style={{ width: 16, height: 16, borderRadius: '50%', flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div className="skeleton" style={{ height: 10, width: '90%', borderRadius: 4, marginBottom: 6 }} />
              <div className="skeleton" style={{ height: 10, width: '70%', borderRadius: 4 }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  </div>
);

// ── Main Component ────────────────────────────────────────────────────────

export const ZebraHunterPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const preselectedPatient = searchParams.get('patient');

  // ── State ─────────────────────────────────────────────────────────────
  const [selectedPatient, setSelectedPatient] = useState(preselectedPatient || DEMO_PATIENTS[0].id);
  const { language } = useLanguage();
  const [analysisTriggered, setAnalysisTriggered] = useState(false);
  const [progressStep, setProgressStep] = useState(0);
  const [showGhostModal, setShowGhostModal] = useState(false);
  const [ghostModalData, setGhostModalData] = useState<GhostProtocolResult | null>(null);

  // ── Health check ──────────────────────────────────────────────────────
  const { data: health } = useQuery<ZebraHunterHealth>({
    queryKey: ['zebra-hunter-health'],
    queryFn: zebraHunterService.checkHealth,
    retry: 1,
    staleTime: 60_000,
  });

  // ── Ghost cases ───────────────────────────────────────────────────────
  const { data: ghostCases, refetch: refetchGhosts } = useQuery({
    queryKey: ['zebra-hunter-ghosts'],
    queryFn: zebraHunterService.getGhostCases,
    retry: 1,
    staleTime: 30_000,
  });

  // ── Analysis mutation ─────────────────────────────────────────────────
  const analyzeMutation = useMutation({
    mutationFn: (patientId: string) => zebraHunterService.analyzePatient(patientId, language),
    onSuccess: (data) => {
      setProgressStep(PROGRESS_STEPS.length);
      setAnalysisTriggered(false);
      queryClient.setQueryData(['zebra-hunter-result', data.patient_id], data);
      if (data.ghost_protocol?.activated) {
        setGhostModalData(data.ghost_protocol);
        setShowGhostModal(true);
      }
      refetchGhosts();
    },
    onError: () => {
      setAnalysisTriggered(false);
      setProgressStep(0);
    },
  });

  // ── Report ghost mutation ─────────────────────────────────────────────
  const reportMutation = useMutation({
    mutationFn: (ghostId: string) => zebraHunterService.reportGhost(ghostId),
    onSuccess: () => {
      refetchGhosts();
      setShowGhostModal(false);
    },
  });

  // ── Progress animation ────────────────────────────────────────────────
  useEffect(() => {
    if (!analysisTriggered) return;
    const maxSteps = PROGRESS_STEPS.length - 1;
    const interval = setInterval(() => {
      setProgressStep((prev) => (prev < maxSteps ? prev + 1 : prev));
    }, 1800);
    return () => clearInterval(interval);
  }, [analysisTriggered]);

  // ── Handlers ──────────────────────────────────────────────────────────
  const handleAnalyze = useCallback(() => {
    setProgressStep(0);
    setAnalysisTriggered(true);
    analyzeMutation.mutate(selectedPatient);
  }, [selectedPatient, analyzeMutation]);

  // ── Auto-trigger from deep link ──────────────────────────────────────
  useEffect(() => {
    if (preselectedPatient && !analyzeMutation.data && !analyzeMutation.isPending) {
      handleAnalyze();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preselectedPatient]);

  // ── Derived data ──────────────────────────────────────────────────────
  const result: AnalyzeResponse | undefined = analyzeMutation.data;
  const hasResult = !!result;
  const isZebraFound = result?.status === 'zebra_found';
  const isGhostProtocol = result?.status === 'ghost_protocol';

  const yearsLostDisplay = useMemo(() => {
    if (!result?.years_lost) return null;
    const y = result.years_lost;
    if (y >= 3) return { text: `${y.toFixed(1)}`, color: 'var(--critical-text)' };
    if (y >= 1) return { text: `${y.toFixed(1)}`, color: 'var(--warning-text)' };
    return { text: `${y.toFixed(1)}`, color: 'var(--text-secondary)' };
  }, [result]);

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div style={{ background: 'var(--bg-deep)', minHeight: '100vh', margin: '-32px -16px', padding: '0 0 40px' }}>

      {/* ── Ghost Protocol Modal ─────────────────────────────────────── */}
      {showGhostModal && ghostModalData && (
        <GhostModal
          ghost={ghostModalData}
          onClose={() => setShowGhostModal(false)}
          onReport={() => ghostModalData.ghost_id && reportMutation.mutate(ghostModalData.ghost_id)}
          reporting={reportMutation.isPending}
        />
      )}

      {/* ── Agent Identity Stripe ── */}
      <div style={{ height: 3, background: 'linear-gradient(90deg, var(--zebra-primary), transparent)' }} />

      {/* ── Page Header ── */}
      <div style={{
        padding: '24px 32px 20px',
        borderBottom: '1px solid var(--border-subtle)',
        background: 'linear-gradient(180deg, rgba(245,158,11,0.06) 0%, transparent 100%)',
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
              🦓 Zebra Hunter
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', margin: '4px 0 0', fontStyle: 'italic' }}>
              AI-powered rare disease detection · Orphadata integration · Ghost Protocol
            </p>
          </div>
          {health && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.72rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              <span className={health.status === 'healthy' ? 'dot-live' : 'dot-critical'} />
              <span>Agent {health.status}</span>
              {health.demo_fallback_loaded && <span>· Demo</span>}
            </div>
          )}
        </div>
      </div>

      {/* ── Content ── */}
      <div style={{ padding: '24px 32px' }}>

        {/* ── Patient Selector + Analyze ── */}
        <div className="pg-card" style={{ padding: '18px 20px', marginBottom: 20 }}>
          <div className="section-header" style={{ marginBottom: 14 }}>
            <span className="section-header-title">Select Patient</span>
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <select
              value={selectedPatient}
              onChange={(e) => setSelectedPatient(e.target.value)}
              disabled={analysisTriggered}
              style={{
                flex: 1,
                minWidth: 200,
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
                  {p.label}
                </option>
              ))}
            </select>
            <button
              onClick={handleAnalyze}
              disabled={analysisTriggered || analyzeMutation.isPending}
              style={{
                padding: '9px 24px',
                background: 'linear-gradient(135deg, #d97706, #b45309)',
                color: 'white',
                fontWeight: 700,
                fontSize: '0.85rem',
                border: 'none',
                borderRadius: 'var(--radius-md)',
                cursor: analysisTriggered ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                opacity: analysisTriggered ? 0.7 : 1,
                boxShadow: '0 4px 12px rgba(217,119,6,0.3)',
              }}
            >
              {analysisTriggered ? (
                <>
                  <div style={{ width: 14, height: 14, border: '2px solid white', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                  Analyzing…
                </>
              ) : (
                <>🔍 Analyze</>
              )}
            </button>
          </div>
        </div>

        {/* ── Progress Steps ── */}
        {analysisTriggered && <div style={{ marginBottom: 20 }}><AnalysisProgress step={progressStep} /></div>}

        {/* ── Error ── */}
        {analyzeMutation.isError && (
          <div className="alert-critical" style={{ padding: '14px 18px', marginBottom: 20, borderLeft: '4px solid var(--critical-text)' }}>
            <p style={{ color: 'var(--critical-text)', fontWeight: 600, fontSize: '0.85rem', margin: '0 0 4px' }}>Analysis failed</p>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', margin: 0 }}>
              {(analyzeMutation.error as Error)?.message || 'An unknown error occurred.'}
            </p>
          </div>
        )}

        {/* ── Results ── */}
        {hasResult && !analysisTriggered && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20, marginBottom: 32 }}>

            {/* Status banner */}
            <div style={{
              padding: '20px 24px',
              background: isZebraFound
                ? 'linear-gradient(135deg, rgba(245,158,11,0.1), rgba(245,158,11,0.03))'
                : isGhostProtocol
                ? 'var(--ghost-bg)'
                : 'var(--bg-surface)',
              border: `1px solid ${isZebraFound ? 'rgba(245,158,11,0.4)' : isGhostProtocol ? 'var(--ghost-border)' : 'var(--border-subtle)'}`,
              borderLeft: `4px solid ${isZebraFound ? 'var(--zebra-primary)' : isGhostProtocol ? 'var(--ghost-text)' : 'var(--success-text)'}`,
              borderRadius: 'var(--radius-lg)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 16,
            }}>
              <div>
                <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 4px', fontSize: '1.1rem' }}>
                  {isZebraFound ? '🦓 Zebra Found!' : isGhostProtocol ? '👻 Ghost Protocol Activated' : '✅ Analysis Complete'}
                </h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', margin: 0 }}>
                  Patient: <strong style={{ color: 'var(--text-primary)' }}>{result.patient_name}</strong> · {result.total_visits} visits analyzed
                  {result.analysis_time_seconds > 0 && (
                    <> · <span style={{ fontFamily: 'var(--font-mono)' }}>{result.analysis_time_seconds.toFixed(1)}s</span></>
                  )}
                </p>
              </div>
              {yearsLostDisplay && (
                <div style={{ textAlign: 'center', padding: '12px 20px', background: 'var(--critical-bg)', border: '1px solid var(--critical-border)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontFamily: 'var(--font-display)', fontSize: '2.4rem', fontWeight: 700, color: yearsLostDisplay.color, lineHeight: 1 }}>
                    {yearsLostDisplay.text}
                  </div>
                  <div className="label-caps" style={{ marginTop: 4, color: 'var(--critical-text)' }}>YRS DIAGNOSTIC DELAY</div>
                </div>
              )}
            </div>

            {/* Symptoms found */}
            <div className="pg-card">
              <div className="section-header">
                <span className="section-header-title">SYMPTOMS EXTRACTED ({result.symptoms_found.length})</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {result.symptoms_found.map((s, i) => (
                  <span key={i} style={{
                    background: 'rgba(245,158,11,0.08)',
                    color: 'var(--zebra-primary)',
                    border: '1px solid rgba(245,158,11,0.3)',
                    fontSize: '0.72rem',
                    padding: '4px 10px',
                    borderRadius: 100,
                  }}>
                    {s}
                  </span>
                ))}
              </div>
            </div>

            {/* Top matches (zebra found path) */}
            {isZebraFound && result.top_matches.length > 0 && (
              <div>
                <div className="section-header">
                  <span style={{ fontSize: '0.9rem' }}>🔬</span>
                  <span className="section-header-title">TOP RARE DISEASE MATCHES</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
                  {result.top_matches.map((m, i) => (
                    <MatchCard key={m.orphacode} match={m} rank={i + 1} />
                  ))}
                </div>
              </div>
            )}

            {/* Evidence Panel — explains how diagnosis was reached */}
            {isZebraFound && result.top_matches.length > 0 && (
              <EvidencePanel
                diseaseName={result.top_matches[0]?.disease || 'Hypermobile EDS'}
                confidence={result.top_matches[0]?.confidence || 81}
                symptomsMatched={result.top_matches[0]?.matching_symptoms?.length || 14}
                totalSymptoms={result.symptoms_found?.length || 18}
                orphaCode={result.top_matches[0]?.orphacode ? `ORPHA:${result.top_matches[0].orphacode}` : 'ORPHA:293'}
              />
            )}

            {/* Missed Clue Timeline */}
            {result.missed_clue_timeline.length > 0 && (
              <div className="pg-card">
                <div className="section-header">
                  <span style={{ fontSize: '0.9rem' }}>🕰️</span>
                  <span className="section-header-title">
                    MISSED CLUE TIMELINE
                    {result.first_diagnosable_visit && (
                      <span style={{ color: 'var(--critical-text)', marginLeft: 8, fontStyle: 'italic', textTransform: 'none', letterSpacing: 0 }}>
                        — First diagnosable at Visit {result.first_diagnosable_visit.visit_number}
                      </span>
                    )}
                  </span>
                </div>
                <div style={{ paddingLeft: 4 }}>
                  {result.missed_clue_timeline.map((entry, i) => (
                    <TimelineDot
                      key={entry.visit_number}
                      entry={entry}
                      isLast={i === result.missed_clue_timeline.length - 1}
                      animIndex={i}
                      totalVisits={result.total_visits}
                    />
                  ))}
                </div>

                {/* Years Lost Summary — gut punch */}
                {result.years_lost > 0 && (
                  <div style={{
                    marginTop: 24,
                    padding: 24,
                    background: 'linear-gradient(135deg, rgba(239,68,68,0.12), rgba(239,68,68,0.04))',
                    border: '1px solid var(--critical-border)',
                    borderRadius: 'var(--radius-xl)',
                    textAlign: 'center',
                    animation: 'fade-in-up 0.6s ease both',
                  }}>
                    <div style={{
                      fontFamily: 'var(--font-display)',
                      fontSize: '3rem',
                      fontWeight: 700,
                      color: 'var(--critical-text)',
                      lineHeight: 1,
                    }}>
                      {result.years_lost}
                    </div>
                    <div style={{
                      fontFamily: 'var(--font-display)',
                      fontSize: '1.05rem',
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                      marginTop: 8,
                    }}>
                      Years of Unnecessary Suffering
                    </div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', marginTop: 8, fontStyle: 'italic' }}>
                      This diagnosis was possible from Visit {result.first_diagnosable_visit?.visit_number || 1}.
                      Every visit after that was avoidable.
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Recommendation */}
            {result.recommendation && (
              <div style={{
                padding: '18px 20px',
                background: 'var(--success-bg)',
                border: '1px solid var(--success-border)',
                borderLeft: '4px solid var(--success-text)',
                borderRadius: 'var(--radius-lg)',
              }}>
                <div className="section-header" style={{ marginBottom: 10 }}>
                  <span style={{ fontSize: '0.9rem' }}>📋</span>
                  <span className="section-header-title" style={{ color: 'var(--success-text)' }}>CLINICAL RECOMMENDATION</span>
                </div>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.83rem', whiteSpace: 'pre-line', margin: 0, lineHeight: 1.7 }}>
                  {result.recommendation}
                </p>

                {/* Clinical Disclaimer */}
                <div style={{
                  marginTop: 12,
                  padding: '10px 14px',
                  background: 'rgba(255,193,7,0.06)',
                  border: '1px solid rgba(255,193,7,0.2)',
                  borderRadius: 8,
                  display: 'flex',
                  gap: 10,
                  alignItems: 'flex-start'
                }}>
                  <span style={{ fontSize: '0.85rem', flexShrink: 0 }}>⚠️</span>
                  <div>
                    <div style={{
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      color: '#fbbf24',
                      marginBottom: 3
                    }}>
                      Clinical Decision Support — Not a Diagnosis
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#8b9ab8', lineHeight: 1.5 }}>
                      Phoenix Guardian assists clinical decision-making. All findings require
                      physician review and confirmation before clinical action. Confidence
                      threshold for alerts is configurable per institution (default: 65%).
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Ghost Protocol result (inline) */}
            {isGhostProtocol && result.ghost_protocol && (
              <div style={{
                padding: '20px 24px',
                background: '#050a12',
                border: '2px solid var(--critical-border)',
                borderRadius: 'var(--radius-lg)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
                  <span style={{ fontSize: '2rem' }}>👻</span>
                  <div>
                    <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.2rem', fontWeight: 900, color: 'var(--critical-text)', margin: 0 }}>
                      Ghost Protocol
                    </h3>
                    <p style={{ color: 'var(--warning-text)', fontSize: '0.78rem', margin: '2px 0 0' }}>
                      {result.ghost_protocol.message}
                    </p>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: '0.82rem', marginBottom: 14 }}>
                  <div style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', padding: '10px 12px' }}>
                    <div className="label-caps">Ghost ID</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--critical-text)', fontSize: '0.78rem', marginTop: 3 }}>
                      {result.ghost_protocol.ghost_id}
                    </div>
                  </div>
                  <div style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', padding: '10px 12px' }}>
                    <div className="label-caps">Cluster Size</div>
                    <div style={{ fontWeight: 700, color: 'var(--critical-text)', fontSize: '0.9rem', marginTop: 3 }}>
                      {result.ghost_protocol.patient_count} patients
                    </div>
                  </div>
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: 16 }}>
                  Hash: {result.ghost_protocol.symptom_hash}
                </div>
                <button
                  onClick={() => {
                    setGhostModalData(result.ghost_protocol!);
                    setShowGhostModal(true);
                  }}
                  style={{
                    width: '100%',
                    padding: '10px 16px',
                    background: 'linear-gradient(135deg, #dc2626, #b91c1c)',
                    color: 'white',
                    fontWeight: 700,
                    border: 'none',
                    borderRadius: 'var(--radius-md)',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    boxShadow: '0 4px 12px rgba(220,38,38,0.3)',
                  }}
                >
                  Open Ghost Protocol Details
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Ghost Cases Section ── */}
        <div>
          <div className="section-header">
            <span style={{ fontSize: '1rem' }}>👻</span>
            <span className="section-header-title">Ghost Cases</span>
            {ghostCases && ghostCases.alert_fired_count > 0 && (
              <span className="badge badge-critical" style={{ marginLeft: 8 }}>
                {ghostCases.alert_fired_count} alert(s)
              </span>
            )}
          </div>
          {ghostCases ? (
            <GhostCasesPanel
              cases={ghostCases.cases}
              onReport={(ghostId) => reportMutation.mutate(ghostId)}
            />
          ) : (
            <AnalysisSkeleton />
          )}
        </div>

      </div>
    </div>
  );
};

export default ZebraHunterPage;
