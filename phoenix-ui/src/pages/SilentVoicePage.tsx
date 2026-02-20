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
import type { MonitorResult, SignalData } from '../api/services/silentVoiceService';

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

function getVitalColor(z: number): string {
  const absZ = Math.abs(z);
  if (absZ > 2.5) return 'red';
  if (absZ > 1.5) return 'yellow';
  return 'green';
}

function getVitalBg(color: string): string {
  if (color === 'red') return 'bg-red-50 border-red-300';
  if (color === 'yellow') return 'bg-yellow-50 border-yellow-300';
  return 'bg-green-50 border-green-300';
}

function getVitalTextColor(color: string): string {
  if (color === 'red') return 'text-red-700';
  if (color === 'yellow') return 'text-yellow-700';
  return 'text-green-700';
}

function getVitalIndicator(color: string): string {
  if (color === 'red') return '🔴';
  if (color === 'yellow') return '🟡';
  return '✅';
}

// ─── Alert Score Bar ──────────────────────────────────────────────────────

const AlertScoreBar: React.FC<{ score: number; maxScore?: number }> = ({ score, maxScore = 10 }) => {
  const pct = Math.min((score / maxScore) * 100, 100);
  const barColor = score > 8 ? 'bg-red-500' : score > 4 ? 'bg-yellow-500' : 'bg-green-500';
  const label = score > 8 ? 'CRITICAL' : score > 4 ? 'WARNING' : 'CLEAR';

  return (
    <div className="bg-white border rounded-lg p-4 flex flex-col items-center">
      <span className="text-xs font-bold text-gray-500 mb-1">ALERT SCORE</span>
      <span className="text-2xl font-bold">{score.toFixed(1)}</span>
      <span className="text-xs text-gray-400">/ {maxScore}</span>
      <div className="w-full bg-gray-200 rounded-full h-3 mt-2">
        <div className={`${barColor} h-3 rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-bold mt-1 ${score > 8 ? 'text-red-600' : score > 4 ? 'text-yellow-600' : 'text-green-600'}`}>
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
  const color = getVitalColor(z);
  const deviationPct = baseline.mean !== 0 ? ((current - baseline.mean) / baseline.mean) * 100 : 0;
  const isNormal = Math.abs(z) <= 1.5;

  // Mini sparkline using block characters
  const sparkline = history.length > 1
    ? history.map((v, i) => {
        const min = Math.min(...history);
        const max = Math.max(...history);
        const range = max - min || 1;
        const normalized = (v - min) / range;
        const chars = '▁▂▃▄▅▆▇█';
        return chars[Math.min(Math.floor(normalized * 8), 7)];
      }).join('')
    : '▄▄▄▄▄';

  return (
    <div className={`border-2 rounded-lg p-4 transition-all duration-500 ${getVitalBg(color)}`}>
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs font-bold text-gray-600">{config.icon} {config.label}</span>
        <span className="text-sm">{getVitalIndicator(color)}</span>
      </div>
      <div className={`text-3xl font-bold mb-1 ${getVitalTextColor(color)}`}>
        {typeof current === 'number' ? (Number.isInteger(current) ? current : current.toFixed(1)) : current}
        <span className="text-sm font-normal text-gray-500 ml-1">{config.unit}</span>
      </div>
      <div className="text-lg font-mono tracking-wider text-gray-500 mb-2">{sparkline}</div>
      <div className="text-xs text-gray-500">
        {mode === 'personal' ? '👤 Personal' : '👥 Population'} baseline: {baseline.mean.toFixed(0)}
      </div>
      {!isNormal && (
        <div className={`text-xs font-semibold mt-1 ${getVitalTextColor(color)}`}>
          {deviationPct > 0 ? '+' : ''}{deviationPct.toFixed(0)}% {deviationPct > 0 ? '⬆' : '⬇'}
        </div>
      )}
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
  const baselineEnd = Math.min(120, totalMinutes); // 2-hour baseline window
  const distressStart = totalMinutes - distressMinutes;

  // Percentage positions on timeline
  const baselinePct = totalMinutes > 0 ? (baselineEnd / totalMinutes) * 100 : 33;
  const distressPct = totalMinutes > 0 ? (distressStart / totalMinutes) * 100 : 80;

  return (
    <div className="bg-white border rounded-lg p-6">
      <h3 className="text-sm font-bold text-gray-700 mb-4">📈 Distress Timeline</h3>

      <div className="relative h-8 mb-2">
        {/* Green baseline zone */}
        <div
          className="absolute h-full bg-green-200 rounded-l"
          style={{ left: '0%', width: `${baselinePct}%` }}
        />
        {/* Gray stable zone */}
        <div
          className="absolute h-full bg-gray-100"
          style={{ left: `${baselinePct}%`, width: `${Math.max(0, distressPct - baselinePct)}%` }}
        />
        {/* Red distress zone */}
        {distressMinutes > 0 && (
          <div
            className="absolute h-full bg-red-200 rounded-r animate-pulse"
            style={{ left: `${distressPct}%`, width: `${100 - distressPct}%` }}
          />
        )}

        {/* Markers */}
        <div className="absolute top-0 left-0 w-3 h-full bg-green-500 rounded-sm" />
        {baselineEstablished && (
          <div
            className="absolute top-0 w-3 h-full bg-blue-500 rounded-sm"
            style={{ left: `${baselinePct}%` }}
          />
        )}
        {distressMinutes > 0 && (
          <div
            className="absolute top-0 w-3 h-full bg-red-500 rounded-sm"
            style={{ left: `${distressPct}%` }}
          />
        )}
        <div className="absolute top-0 right-0 w-3 h-full bg-gray-800 rounded-sm" />
      </div>

      {/* Labels */}
      <div className="flex justify-between text-xs text-gray-500 mb-4">
        <span>Admission<br />{admissionHoursAgo.toFixed(0)}h ago</span>
        <span className="text-blue-600">Baseline<br />Established</span>
        {distressMinutes > 0 && (
          <span className="text-red-600 font-semibold">
            Distress<br />{distressMinutes} min ago
          </span>
        )}
        <span>NOW</span>
      </div>

      {/* Nurse check counter */}
      <div className="bg-red-50 border border-red-200 rounded p-3 text-center">
        <span className="text-red-700 font-semibold text-sm">
          ⏱️ {minutesSinceCheck} minutes since last nurse check
        </span>
        {distressMinutes > 0 && (
          <p className="text-red-500 text-xs mt-1">
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
  const signalSummary = data.signals_detected
    .map(s => `${s.label} ${s.deviation_pct > 0 ? '+' : ''}${s.deviation_pct.toFixed(0)}%`)
    .join(' | ');

  const bgColor = data.alert_level === 'critical' ? 'bg-red-50 border-red-400' : 'bg-yellow-50 border-yellow-400';
  const headerColor = data.alert_level === 'critical' ? 'text-red-700' : 'text-yellow-700';
  const icon = data.alert_level === 'critical' ? '🔴' : '🟡';

  return (
    <div className={`border-2 rounded-lg p-5 ${bgColor}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg">{icon}</span>
        <h3 className={`text-lg font-bold ${headerColor}`}>
          SilentVoice Alert — Pain Indicators Detected
        </h3>
        {acknowledged && (
          <span className="bg-green-100 text-green-700 text-xs font-bold px-2 py-0.5 rounded-full ml-auto">
            ✓ ACKNOWLEDGED
          </span>
        )}
      </div>

      <div className="border-t border-gray-200 pt-3 space-y-2">
        <p className="text-sm text-gray-700">
          <span className="font-semibold">Signals:</span> {signalSummary}
        </p>
        <p className="text-sm text-gray-700">
          <span className="font-semibold">Active for:</span> {data.distress_duration_minutes} minutes undetected
        </p>
        <p className="text-sm text-gray-700">
          <span className="font-semibold">Last analgesic:</span>{' '}
          {data.last_analgesic_hours !== null ? `${data.last_analgesic_hours} hours ago` : 'None on record'}
        </p>

        {data.clinical_output && (
          <blockquote className="mt-3 border-l-4 border-blue-400 pl-3 py-2 bg-blue-50 rounded-r text-sm italic text-gray-800">
            "{data.clinical_output}"
          </blockquote>
        )}
      </div>

      {!acknowledged && (
        <div className="flex flex-wrap gap-2 mt-4">
          <button
            onClick={onAcknowledge}
            className="px-4 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700 transition-colors text-sm"
          >
            ✅ Acknowledge Alert
          </button>
          <button className="px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700 transition-colors text-sm">
            📋 Order Pain Assessment
          </button>
          <button className="px-4 py-2 bg-purple-600 text-white rounded font-semibold hover:bg-purple-700 transition-colors text-sm">
            💉 Administer Analgesic
          </button>
          <button className="px-4 py-2 bg-gray-600 text-white rounded font-semibold hover:bg-gray-700 transition-colors text-sm">
            📞 Call Attending
          </button>
        </div>
      )}
    </div>
  );
};

// ─── Loading skeleton ────────────────────────────────────────────────────

const LoadingSkeleton: React.FC = () => (
  <div className="p-8 space-y-6 animate-pulse">
    <div className="h-24 bg-gray-200 rounded-lg" />
    <div className="grid grid-cols-3 gap-4">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="h-36 bg-gray-200 rounded-lg" />
      ))}
    </div>
    <div className="h-40 bg-gray-200 rounded-lg" />
    <div className="h-32 bg-gray-200 rounded-lg" />
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════
// MAIN PAGE COMPONENT
// ═══════════════════════════════════════════════════════════════════════════

export const SilentVoicePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const preselectedPatient = searchParams.get('patient');
  const patientId = preselectedPatient || PATIENT_C_ID;
  const { data, connected, error, mode } = useSilentVoiceStream(patientId);
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
            next[field] = arr.slice(-8); // keep last 8
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
    // Get the latest alert ID from the data
    try {
      // We'll acknowledge the most recent alert
      const overview = await silentVoiceService.getIcuOverview();
      // For demo, just mark as acknowledged visually
      setAcknowledged(true);
    } catch {
      setAcknowledged(true); // Still show UI change
    }
  };

  // Header color
  const alertLevel = data?.alert_level || 'clear';
  const showAlert = baselineMode === 'personal' && currentModeSignals.length > 0;

  if (!data) return <LoadingSkeleton />;

  const admissionHoursAgo = 6; // Hardcoded for demo — Patient C admitted 6h ago

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
      {/* ═══ SECTION 1: Patient Status Header ═══ */}
      <div
        className={`rounded-lg p-5 transition-all duration-500 ${
          showAlert && alertLevel === 'critical'
            ? 'bg-red-600 text-white'
            : showAlert && alertLevel === 'warning'
            ? 'bg-yellow-500 text-gray-900'
            : 'bg-green-600 text-white'
        }`}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-2xl">🔵</span>
              <h1 className="text-xl font-bold">SilentVoice Monitor</h1>
              {showAlert && (
                <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                  alertLevel === 'critical' ? 'bg-red-800 text-red-100' : 'bg-yellow-700 text-yellow-100'
                }`}>
                  {alertLevel === 'critical' ? '🔴 DISTRESS ACTIVE' : '🟡 DISTRESS ACTIVE'}
                </span>
              )}
            </div>
            <p className={`text-sm mt-1 ${showAlert ? 'opacity-90' : 'opacity-80'}`}>
              Patient: {data.patient_name} — ICU Bed 3
            </p>
            {data.distress_active && (
              <p className={`text-sm ${showAlert ? 'opacity-90' : 'opacity-80'}`}>
                Active for: {data.distress_duration_minutes} minutes | Last nurse check: {minutesSinceCheck} min ago
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className={`w-2.5 h-2.5 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
              <span className="text-sm font-medium">
                {connected ? (mode === 'websocket' ? '● LIVE' : '● POLLING') : '○ DISCONNECTED'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ═══ TOGGLE: Population vs Personal Baseline ═══ */}
      <div className="flex items-center gap-3 bg-white border rounded-lg p-4">
        <span className="text-sm text-gray-500">Comparing against:</span>
        <button
          onClick={() => setBaselineMode(m => m === 'personal' ? 'population' : 'personal')}
          className={`px-5 py-2.5 rounded-full font-semibold transition-all duration-300 text-sm ${
            baselineMode === 'personal'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-200'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          {baselineMode === 'personal' ? '👤 Personal Baseline' : '👥 Population Average'}
        </button>
        <span className="text-xs text-gray-400 ml-2">
          {baselineMode === 'personal'
            ? 'Comparing to HER first 2 hours in this bed'
            : 'Comparing to average 72-year-old woman'}
        </span>
      </div>

      {/* ═══ SECTION 2: Live Vitals Grid ═══ */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
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
        <ClinicalAlertCard
          data={data}
          onAcknowledge={handleAcknowledge}
          acknowledged={acknowledged}
        />
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
        <div className="bg-yellow-50 border border-yellow-200 rounded p-3 text-sm text-yellow-700">
          ⚠️ {error}
        </div>
      )}
    </div>
  );
};

export default SilentVoicePage;
