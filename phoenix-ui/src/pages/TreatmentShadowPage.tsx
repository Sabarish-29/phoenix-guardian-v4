/**
 * Treatment Shadow Monitor page.
 *
 * Displays treatment side-effect shadow monitoring:
 * - Patient selector with analysis trigger
 * - Shadow overview stats
 * - Shadow detail cards with trend charts
 * - Harm projection timeline
 */

import React, { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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

const severityColor = (severity: string): string => {
  switch (severity) {
    case 'critical':
      return 'border-red-500 bg-red-50';
    case 'moderate':
      return 'border-red-400 bg-red-50';
    case 'mild':
      return 'border-yellow-400 bg-yellow-50';
    case 'watching':
      return 'border-yellow-300 bg-yellow-50';
    default:
      return 'border-green-400 bg-green-50';
  }
};

const severityBadge = (severity: string): { label: string; className: string } => {
  switch (severity) {
    case 'critical':
      return { label: 'CRITICAL', className: 'bg-red-100 text-red-800' };
    case 'moderate':
      return { label: 'MODERATE', className: 'bg-red-100 text-red-700' };
    case 'mild':
      return { label: 'MILD', className: 'bg-yellow-100 text-yellow-800' };
    case 'watching':
      return { label: 'WATCHING', className: 'bg-yellow-100 text-yellow-700' };
    default:
      return { label: 'STABLE', className: 'bg-green-100 text-green-700' };
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
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
      <div className="card text-center">
        <p className="text-3xl font-bold text-gray-900">{analysis.total_shadows}</p>
        <p className="text-sm text-gray-500 mt-1">Shadows Active</p>
      </div>
      <div className="card text-center border-l-4 border-red-500">
        <p className="text-3xl font-bold text-red-600">{analysis.fired_count}</p>
        <p className="text-sm text-gray-500 mt-1">🔴 Need Action</p>
      </div>
      <div className="card text-center border-l-4 border-yellow-400">
        <p className="text-3xl font-bold text-yellow-600">{watching}</p>
        <p className="text-sm text-gray-500 mt-1">🟡 Monitoring</p>
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
      <div className="text-center py-8 text-gray-400 text-sm">
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
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip />
        <Legend />
        {threshold && (
          <ReferenceLine
            y={threshold.value}
            stroke="#ef4444"
            strokeDasharray="6 4"
            label={{
              value: threshold.label,
              position: 'insideTopRight',
              fill: '#ef4444',
              fontSize: 11,
            }}
          />
        )}
        <Line
          type="monotone"
          dataKey="value"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={{ fill: '#3b82f6', r: 5 }}
          name="Actual"
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="projected"
          stroke="#ef4444"
          strokeWidth={2}
          strokeDasharray="8 4"
          dot={{ fill: '#ef4444', r: 5 }}
          name="Projected"
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

/**
 * Single shadow detail card
 */
const ShadowCard: React.FC<{
  shadow: ActiveShadow;
  onDismiss?: (drug: string) => void;
}> = ({ shadow, onDismiss }) => {
  const badge = severityBadge(shadow.severity);
  const icon = severityIcon(shadow.severity);
  const borderClass = severityColor(shadow.severity);

  return (
    <div className={`card border-l-4 ${borderClass} mb-6`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {icon} {shadow.drug} → {shadow.shadow_type}
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Prescribed since: {shadow.prescribed_since || 'Unknown'}
          </p>
        </div>
        <span
          className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold ${badge.className}`}
        >
          {badge.label}
        </span>
      </div>

      {/* Trend Chart */}
      <div className="mb-4">
        <h4 className="text-sm font-medium text-gray-700 mb-2">
          {shadow.watch_lab.toUpperCase().replace('_', ' ')} Trend
          {shadow.trend && shadow.trend.direction !== 'insufficient_data' && (
            <span className="ml-2 text-gray-400 font-normal">
              ({shadow.trend.pct_change > 0 ? '+' : ''}
              {shadow.trend.pct_change?.toFixed(1)}% total change, R²=
              {shadow.trend.r_squared?.toFixed(2)})
            </span>
          )}
        </h4>
        <TrendChart shadow={shadow} />
      </div>

      {/* Harm Timeline */}
      {shadow.harm_timeline && (
        <div className="bg-gray-50 rounded-lg p-4 mb-4 space-y-2">
          <div className="flex items-start">
            <span className="text-xs font-medium text-gray-500 w-32 shrink-0">
              Harm started:
            </span>
            <span className="text-sm text-gray-900">
              {shadow.harm_timeline.harm_started_estimate}
            </span>
          </div>
          <div className="flex items-start">
            <span className="text-xs font-medium text-gray-500 w-32 shrink-0">
              Current stage:
            </span>
            <span className="text-sm font-semibold text-amber-700">
              {shadow.harm_timeline.current_stage}
            </span>
          </div>
          <div className="flex items-start">
            <span className="text-xs font-medium text-gray-500 w-32 shrink-0">
              In 90 days:
            </span>
            <span className="text-sm text-red-700">
              {shadow.harm_timeline.projection_90_days}
            </span>
          </div>
        </div>
      )}

      {/* Clinical Output */}
      {shadow.clinical_output && (
        <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 mb-4">
          <p className="text-sm text-blue-900 italic leading-relaxed">
            "{shadow.clinical_output}"
          </p>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3 pt-2">
        {shadow.recommended_action && (
          <button className="btn-primary text-sm px-4 py-2">
            ✅ {shadow.recommended_action.split('.')[0]}
          </button>
        )}
        <button className="bg-blue-50 text-blue-700 hover:bg-blue-100 text-sm px-4 py-2 rounded-lg font-medium transition-colors">
          📋 Order Lab Test
        </button>
        <button className="bg-gray-50 text-gray-700 hover:bg-gray-100 text-sm px-4 py-2 rounded-lg font-medium transition-colors">
          ↗ Refer to Specialist
        </button>
        <button
          onClick={() => onDismiss?.(shadow.drug)}
          className="bg-gray-50 text-gray-500 hover:bg-gray-100 text-sm px-4 py-2 rounded-lg font-medium transition-colors"
        >
          ✖ Dismiss Shadow
        </button>
      </div>
    </div>
  );
};

/**
 * Skeleton loader shown during analysis
 */
const AnalysisSkeleton: React.FC = () => (
  <div className="space-y-6 mt-8 animate-pulse">
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="card">
          <div className="h-8 bg-gray-200 rounded w-16 mx-auto mb-2" />
          <div className="h-4 bg-gray-200 rounded w-24 mx-auto" />
        </div>
      ))}
    </div>
    {[1, 2].map((i) => (
      <div key={i} className="card border-l-4 border-gray-200">
        <div className="h-6 bg-gray-200 rounded w-64 mb-4" />
        <div className="h-40 bg-gray-100 rounded mb-4" />
        <div className="space-y-2">
          <div className="h-4 bg-gray-200 rounded w-full" />
          <div className="h-4 bg-gray-200 rounded w-3/4" />
        </div>
      </div>
    ))}
  </div>
);

// ─── Main Page ────────────────────────────────────────────────────────────

export const TreatmentShadowPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedPatientId, setSelectedPatientId] = useState<string>(DEMO_PATIENTS[0].id);
  const [analysisTriggered, setAnalysisTriggered] = useState(false);

  // Fetch patient analysis (only when triggered)
  const {
    data: analysis,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ['treatment-shadow', selectedPatientId],
    queryFn: () => treatmentShadowService.getPatientAnalysis(selectedPatientId),
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
    // If already triggered, refetch
    if (analysisTriggered) {
      refetch();
    }
  }, [analysisTriggered, refetch]);

  const handlePatientChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setSelectedPatientId(e.target.value);
      setAnalysisTriggered(false);
    },
    []
  );

  const handleDismiss = useCallback(
    (drug: string) => {
      // Find shadow ID for this drug (for a real app this would come from the API)
      alert(`Shadow for ${drug} dismissed. (Demo — would call dismiss API)`);
    },
    []
  );

  const selectedName =
    DEMO_PATIENTS.find((p) => p.id === selectedPatientId)?.name ?? 'Unknown';

  const isAnalyzing = isLoading || isFetching;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          💊 Treatment Shadow Monitor
        </h1>
        <p className="text-gray-500 mt-1">
          Watching the harm that correct treatments cast
        </p>
      </div>

      {/* Health status pill */}
      {health && (
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span
            className={`h-2 w-2 rounded-full ${
              health.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          Agent {health.status}
          {health.openfda_reachable && ' · OpenFDA online'}
          {health.demo_patient_ready && ' · Demo patient ready'}
        </div>
      )}

      {/* Patient Selector */}
      <div className="card">
        <div className="flex flex-col sm:flex-row items-start sm:items-end gap-4">
          <div className="flex-1 w-full sm:w-auto">
            <label
              htmlFor="patient-select"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Select Patient
            </label>
            <select
              id="patient-select"
              value={selectedPatientId}
              onChange={handlePatientChange}
              className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm py-2 px-3 border"
            >
              {DEMO_PATIENTS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={handleAnalyze}
            disabled={isAnalyzing}
            className="btn-primary px-6 py-2 flex items-center gap-2"
          >
            {isAnalyzing ? (
              <>
                <LoadingSpinner size="sm" />
                Analyzing treatment history…
              </>
            ) : (
              <>🔍 Analyze Patient</>
            )}
          </button>
        </div>
      </div>

      {/* Loading skeleton */}
      {isAnalyzing && <AnalysisSkeleton />}

      {/* Error state */}
      {error && !isAnalyzing && (
        <div className="card border-l-4 border-red-500 bg-red-50">
          <p className="text-red-700 text-sm">
            Failed to analyze patient. {(error as Error).message || 'Please try again.'}
          </p>
        </div>
      )}

      {/* Results */}
      {analysis && !isAnalyzing && (
        <>
          {/* Overview Bar */}
          <OverviewBar analysis={analysis} />

          {/* Shadow Cards */}
          <div className="mt-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Active Shadows — {selectedName}
            </h2>
            {analysis.active_shadows.length === 0 ? (
              <div className="card text-center py-12">
                <p className="text-gray-400 text-lg">
                  ✅ No treatment shadows detected for this patient.
                </p>
              </div>
            ) : (
              analysis.active_shadows.map((shadow, idx) => (
                <ShadowCard
                  key={`${shadow.drug}-${idx}`}
                  shadow={shadow}
                  onDismiss={handleDismiss}
                />
              ))
            )}
          </div>
        </>
      )}

      {/* Empty state before analysis */}
      {!analysisTriggered && !isAnalyzing && (
        <div className="card text-center py-16">
          <p className="text-5xl mb-4">💊</p>
          <h3 className="text-lg font-semibold text-gray-700">
            Select a patient and click Analyze
          </h3>
          <p className="text-gray-400 mt-2 max-w-md mx-auto">
            The Treatment Shadow Agent will scan all active prescriptions for
            hidden side-effect patterns that standard monitoring misses.
          </p>
        </div>
      )}
    </div>
  );
};

export default TreatmentShadowPage;
