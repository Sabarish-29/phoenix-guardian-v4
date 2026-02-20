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

// ── Helpers ───────────────────────────────────────────────────────────────

const confidenceColor = (pct: number): string => {
  if (pct >= 75) return 'text-red-600';
  if (pct >= 50) return 'text-amber-600';
  return 'text-gray-600';
};

const confidenceBg = (pct: number): string => {
  if (pct >= 75) return 'bg-red-100 border-red-300';
  if (pct >= 50) return 'bg-amber-100 border-amber-300';
  return 'bg-gray-100 border-gray-300';
};

const severityBadge = (status: string) => {
  switch (status) {
    case 'alert_fired':
      return <span className="bg-red-100 text-red-700 text-xs font-bold px-2 py-0.5 rounded-full">🚨 ALERT</span>;
    case 'reported':
      return <span className="bg-blue-100 text-blue-700 text-xs font-bold px-2 py-0.5 rounded-full">📋 Reported</span>;
    default:
      return <span className="bg-gray-100 text-gray-600 text-xs font-bold px-2 py-0.5 rounded-full">👁️ Watching</span>;
  }
};

// ── Sub-components ────────────────────────────────────────────────────────

/** Animated progress stepper shown during analysis */
const AnalysisProgress: React.FC<{ step: number }> = ({ step }) => (
  <div className="card border-l-4 border-amber-400 animate-pulse">
    <div className="flex items-center gap-3 mb-4">
      <div className="animate-spin h-6 w-6 border-2 border-amber-500 border-t-transparent rounded-full" />
      <span className="font-semibold text-amber-700">Analyzing…</span>
    </div>
    <ol className="space-y-2">
      {PROGRESS_STEPS.map((label, i) => (
        <li key={i} className={`flex items-center gap-2 text-sm ${i <= step ? 'text-amber-700 font-medium' : 'text-gray-400'}`}>
          {i < step ? (
            <span className="text-green-500">✓</span>
          ) : i === step ? (
            <span className="text-amber-500">▸</span>
          ) : (
            <span className="text-gray-300">○</span>
          )}
          {label}
        </li>
      ))}
    </ol>
  </div>
);

/** Disease match card */
const MatchCard: React.FC<{ match: MatchResponse; rank: number }> = ({ match, rank }) => (
  <div className={`rounded-lg border p-4 ${confidenceBg(match.confidence)}`}>
    <div className="flex items-start justify-between mb-2">
      <div>
        <span className="text-xs text-gray-500 font-medium">#{rank}</span>
        <h4 className="font-bold text-gray-900 text-lg">{match.disease}</h4>
        <p className="text-xs text-gray-500">ORPHA:{match.orphacode}</p>
      </div>
      <span className={`text-3xl font-black ${confidenceColor(match.confidence)}`}>{match.confidence}%</span>
    </div>
    <div className="flex flex-wrap gap-1 mt-2">
      {match.matching_symptoms.map((s, i) => (
        <span key={i} className="bg-white/60 text-gray-700 text-xs px-2 py-0.5 rounded-full border border-gray-300">{s}</span>
      ))}
    </div>
    {match.url && (
      <a href={match.url} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline mt-2 inline-block">
        View on Orphanet →
      </a>
    )}
  </div>
);

/** Single timeline dot */
const TimelineDot: React.FC<{ entry: TimelineEntry; isLast: boolean; animIndex: number }> = ({ entry, isLast, animIndex }) => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), animIndex * 400);
    return () => clearTimeout(timer);
  }, [animIndex]);

  const dotColor = entry.was_diagnosable
    ? 'bg-red-500 ring-red-200'
    : 'bg-gray-300 ring-gray-100';

  return (
    <div
      className={`flex gap-4 transition-all duration-500 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
    >
      {/* Vertical bar + dot */}
      <div className="flex flex-col items-center">
        <div className={`w-4 h-4 rounded-full ring-4 ${dotColor} flex-shrink-0 z-10`} />
        {!isLast && <div className="w-0.5 flex-1 bg-gray-200 min-h-[40px]" />}
      </div>

      {/* Content */}
      <div className={`pb-6 ${entry.is_first_diagnosable ? 'bg-red-50 -ml-2 p-3 rounded-lg border border-red-200' : ''}`}>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-gray-800">Visit {entry.visit_number}</span>
          <span className="text-xs text-gray-500">{entry.visit_date}</span>
          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{entry.diagnosis_given}</span>
          {entry.was_diagnosable && (
            <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-bold">
              Diagnosable — {entry.confidence}%
            </span>
          )}
          {entry.is_first_diagnosable && (
            <span className="text-xs bg-red-600 text-white px-2 py-0.5 rounded-full font-bold animate-pulse">
              ⚡ First Miss
            </span>
          )}
        </div>
        {entry.missed_clues.length > 0 && (
          <ul className="mt-1 space-y-0.5">
            {entry.missed_clues.map((clue, i) => (
              <li key={i} className="text-xs text-red-700 flex items-start gap-1">
                <span className="text-red-400 mt-0.5">•</span> {clue}
              </li>
            ))}
          </ul>
        )}
        {entry.reason && (
          <p className="text-xs text-gray-500 mt-1 italic">{entry.reason}</p>
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
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 animate-fadeIn">
    <div className="bg-gray-950 text-white border-2 border-red-600 rounded-2xl max-w-lg w-full mx-4 p-8 shadow-2xl shadow-red-900/30 animate-slideUp">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <span className="text-4xl animate-pulse">👻</span>
          <div>
            <h2 className="text-2xl font-black text-red-500 tracking-wide">GHOST PROTOCOL</h2>
            <p className="text-red-400 text-sm">Unknown Disease Cluster Detected</p>
          </div>
        </div>
        <button onClick={onClose} className="text-gray-500 hover:text-white text-2xl leading-none">×</button>
      </div>

      {/* Body */}
      <div className="space-y-4">
        <div className="bg-red-900/30 border border-red-800 rounded-lg p-4">
          <p className="text-sm text-red-300">{ghost.message}</p>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="bg-gray-900 rounded-lg p-3">
            <p className="text-gray-500 text-xs">Ghost ID</p>
            <p className="font-mono font-bold text-red-400">{ghost.ghost_id}</p>
          </div>
          <div className="bg-gray-900 rounded-lg p-3">
            <p className="text-gray-500 text-xs">Patient Cluster</p>
            <p className="font-bold text-red-400">{ghost.patient_count} patients</p>
          </div>
        </div>

        <div>
          <p className="text-xs text-gray-500 mb-1">Symptom Signature</p>
          <div className="flex flex-wrap gap-1">
            {ghost.symptom_signature.map((s, i) => (
              <span key={i} className="bg-red-900/40 text-red-300 border border-red-700 text-xs px-2 py-0.5 rounded-full">{s}</span>
            ))}
          </div>
        </div>

        <div className="text-xs text-gray-600 font-mono">Hash: {ghost.symptom_hash}</div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 mt-6">
        <button
          onClick={onReport}
          disabled={reporting}
          className="flex-1 bg-red-600 hover:bg-red-700 disabled:bg-red-800 text-white font-bold py-3 px-4 rounded-lg transition-colors"
        >
          {reporting ? 'Reporting…' : '📋 Report to ICMR'}
        </button>
        <button
          onClick={onClose}
          className="px-4 py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors"
        >
          Close
        </button>
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
      <div className="card text-center py-8">
        <span className="text-4xl mb-2 block">👻</span>
        <p className="text-gray-500">No ghost cases yet. Analyze patients to activate Ghost Protocol.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {cases.map((c) => (
        <div key={c.ghost_id} className="card border-l-4 border-red-400 flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono font-bold text-red-600">{c.ghost_id}</span>
              {severityBadge(c.status)}
              <span className="text-xs text-gray-500">{c.patient_count} patient(s)</span>
            </div>
            <div className="flex flex-wrap gap-1 mt-1">
              {c.symptom_signature.map((s, i) => (
                <span key={i} className="bg-red-50 text-red-700 text-xs px-1.5 py-0.5 rounded border border-red-200">{s}</span>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-1">First seen: {c.first_seen}</p>
          </div>
          {c.status === 'alert_fired' && (
            <button
              onClick={() => onReport(c.ghost_id)}
              className="text-xs bg-red-600 hover:bg-red-700 text-white font-bold px-3 py-1.5 rounded-lg transition-colors flex-shrink-0"
            >
              Report
            </button>
          )}
          {c.status === 'reported' && (
            <span className="text-xs text-blue-600 font-medium">Reported to {c.reported_to}</span>
          )}
        </div>
      ))}
    </div>
  );
};

/** Loading skeleton */
const AnalysisSkeleton: React.FC = () => (
  <div className="space-y-4 animate-pulse">
    <div className="card">
      <div className="h-6 bg-gray-200 rounded w-1/3 mb-3" />
      <div className="h-4 bg-gray-200 rounded w-2/3 mb-2" />
      <div className="h-4 bg-gray-200 rounded w-1/2" />
    </div>
    <div className="card">
      <div className="h-5 bg-gray-200 rounded w-1/4 mb-3" />
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex gap-3">
            <div className="w-4 h-4 bg-gray-200 rounded-full flex-shrink-0" />
            <div className="flex-1">
              <div className="h-3 bg-gray-200 rounded w-full mb-1" />
              <div className="h-3 bg-gray-200 rounded w-3/4" />
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
    mutationFn: (patientId: string) => zebraHunterService.analyzePatient(patientId),
    onSuccess: (data) => {
      setProgressStep(PROGRESS_STEPS.length);
      setAnalysisTriggered(false);

      // Cache the result
      queryClient.setQueryData(['zebra-hunter-result', data.patient_id], data);

      // Auto-open Ghost Modal if ghost protocol activated
      if (data.ghost_protocol?.activated) {
        setGhostModalData(data.ghost_protocol);
        setShowGhostModal(true);
      }

      // Refresh ghost cases
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
  const patientLabel = DEMO_PATIENTS.find((p) => p.id === selectedPatient)?.name ?? selectedPatient;
  const hasResult = !!result;
  const isZebraFound = result?.status === 'zebra_found';
  const isGhostProtocol = result?.status === 'ghost_protocol';

  const yearsLostDisplay = useMemo(() => {
    if (!result?.years_lost) return null;
    const y = result.years_lost;
    if (y >= 3) return { text: `${y.toFixed(1)} years`, color: 'text-red-600 bg-red-50' };
    if (y >= 1) return { text: `${y.toFixed(1)} years`, color: 'text-amber-600 bg-amber-50' };
    return { text: `${y.toFixed(1)} years`, color: 'text-gray-600 bg-gray-50' };
  }, [result]);

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* ── Ghost Protocol Modal ─────────────────────────────────────── */}
      {showGhostModal && ghostModalData && (
        <GhostModal
          ghost={ghostModalData}
          onClose={() => setShowGhostModal(false)}
          onReport={() => ghostModalData.ghost_id && reportMutation.mutate(ghostModalData.ghost_id)}
          reporting={reportMutation.isPending}
        />
      )}

      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            🦓 Zebra Hunter
          </h1>
          <p className="text-gray-500 mt-1">
            AI-powered rare disease detection • Orphadata integration • Ghost Protocol
          </p>
        </div>

        {/* Health pill */}
        {health && (
          <span className={`text-xs font-medium px-3 py-1.5 rounded-full ${
            health.status === 'healthy'
              ? 'bg-green-100 text-green-700'
              : 'bg-red-100 text-red-700'
          }`}>
            {health.status === 'healthy' ? '● Healthy' : '● Degraded'}
            {health.demo_fallback_loaded && ' (Demo)'}
          </span>
        )}
      </div>

      {/* ── Patient Selector + Analyze ───────────────────────────────── */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Select Patient</h2>
        <div className="flex flex-col sm:flex-row gap-3">
          <select
            value={selectedPatient}
            onChange={(e) => setSelectedPatient(e.target.value)}
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-gray-700 focus:ring-2 focus:ring-amber-400 focus:border-amber-400 outline-none"
            disabled={analysisTriggered}
          >
            {DEMO_PATIENTS.map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
          <button
            onClick={handleAnalyze}
            disabled={analysisTriggered || analyzeMutation.isPending}
            className="bg-amber-500 hover:bg-amber-600 disabled:bg-gray-300 text-white font-bold px-6 py-2 rounded-lg transition-colors flex items-center gap-2"
          >
            {analysisTriggered ? (
              <>
                <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                Analyzing…
              </>
            ) : (
              <>🔍 Analyze</>
            )}
          </button>
        </div>
      </div>

      {/* ── Progress Steps ───────────────────────────────────────────── */}
      {analysisTriggered && <AnalysisProgress step={progressStep} />}

      {/* ── Error ────────────────────────────────────────────────────── */}
      {analyzeMutation.isError && (
        <div className="card border-l-4 border-red-500 bg-red-50">
          <p className="text-red-700 font-medium">Analysis failed</p>
          <p className="text-red-600 text-sm mt-1">
            {(analyzeMutation.error as Error)?.message || 'An unknown error occurred.'}
          </p>
        </div>
      )}

      {/* ── Results ──────────────────────────────────────────────────── */}
      {hasResult && !analysisTriggered && (
        <div className="space-y-6">
          {/* Status banner */}
          <div className={`card border-l-4 ${
            isZebraFound ? 'border-red-500 bg-red-50' : isGhostProtocol ? 'border-purple-500 bg-purple-50' : 'border-gray-300'
          }`}>
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  {isZebraFound ? '🦓 Zebra Found!' : isGhostProtocol ? '👻 Ghost Protocol Activated' : '✅ Analysis Complete'}
                </h2>
                <p className="text-gray-600 text-sm mt-1">
                  Patient: <strong>{result.patient_name}</strong> • {result.total_visits} visits analyzed
                  {result.analysis_time_seconds > 0 && (
                    <> • Analyzed in <strong>{result.analysis_time_seconds.toFixed(1)}s</strong></>
                  )}
                </p>
              </div>
              {yearsLostDisplay && (
                <div className={`text-center px-4 py-2 rounded-lg ${yearsLostDisplay.color}`}>
                  <p className="text-2xl font-black">{yearsLostDisplay.text}</p>
                  <p className="text-xs opacity-70">diagnostic delay</p>
                </div>
              )}
            </div>
          </div>

          {/* Symptoms found */}
          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-2">Symptoms Extracted ({result.symptoms_found.length})</h3>
            <div className="flex flex-wrap gap-1.5">
              {result.symptoms_found.map((s, i) => (
                <span key={i} className="bg-amber-50 text-amber-800 border border-amber-200 text-xs px-2 py-1 rounded-full">{s}</span>
              ))}
            </div>
          </div>

          {/* Top matches (zebra found path) */}
          {isZebraFound && result.top_matches.length > 0 && (
            <div>
              <h3 className="font-semibold text-gray-900 mb-3">🔬 Top Rare Disease Matches</h3>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {result.top_matches.map((m, i) => (
                  <MatchCard key={m.orphacode} match={m} rank={i + 1} />
                ))}
              </div>
            </div>
          )}

          {/* Missed Clue Timeline */}
          {result.missed_clue_timeline.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-900 mb-4">
                🕰️ Missed Clue Timeline
                {result.first_diagnosable_visit && (
                  <span className="text-sm font-normal text-red-600 ml-2">
                    — First diagnosable at Visit {result.first_diagnosable_visit.visit_number}
                  </span>
                )}
              </h3>
              <div className="ml-2">
                {result.missed_clue_timeline.map((entry, i) => (
                  <TimelineDot
                    key={entry.visit_number}
                    entry={entry}
                    isLast={i === result.missed_clue_timeline.length - 1}
                    animIndex={i}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Recommendation */}
          {result.recommendation && (
            <div className="card border-l-4 border-green-500 bg-green-50">
              <h3 className="font-semibold text-green-900 mb-2">📋 Clinical Recommendation</h3>
              <p className="text-green-800 text-sm whitespace-pre-line">{result.recommendation}</p>
            </div>
          )}

          {/* Ghost Protocol result (inline — not modal) */}
          {isGhostProtocol && result.ghost_protocol && (
            <div className="card border-2 border-red-500 bg-gray-950 text-white">
              <div className="flex items-center gap-3 mb-3">
                <span className="text-3xl animate-pulse">👻</span>
                <div>
                  <h3 className="text-xl font-black text-red-500">Ghost Protocol</h3>
                  <p className="text-red-400 text-sm">{result.ghost_protocol.message}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-gray-900 rounded-lg p-3">
                  <p className="text-gray-500 text-xs">Ghost ID</p>
                  <p className="font-mono font-bold text-red-400">{result.ghost_protocol.ghost_id}</p>
                </div>
                <div className="bg-gray-900 rounded-lg p-3">
                  <p className="text-gray-500 text-xs">Cluster Size</p>
                  <p className="font-bold text-red-400">{result.ghost_protocol.patient_count} patients</p>
                </div>
              </div>
              <div className="mt-3">
                <p className="text-xs text-gray-500 mb-1">Hash</p>
                <p className="font-mono text-xs text-gray-400">{result.ghost_protocol.symptom_hash}</p>
              </div>
              <button
                onClick={() => {
                  setGhostModalData(result.ghost_protocol!);
                  setShowGhostModal(true);
                }}
                className="mt-4 bg-red-600 hover:bg-red-700 text-white font-bold px-4 py-2 rounded-lg transition-colors w-full"
              >
                Open Ghost Protocol Details
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Ghost Cases Section ──────────────────────────────────────── */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-3 flex items-center gap-2">
          👻 Ghost Cases
          {ghostCases && ghostCases.alert_fired_count > 0 && (
            <span className="bg-red-100 text-red-700 text-xs font-bold px-2 py-0.5 rounded-full">
              {ghostCases.alert_fired_count} alert(s)
            </span>
          )}
        </h2>
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
  );
};

export default ZebraHunterPage;
