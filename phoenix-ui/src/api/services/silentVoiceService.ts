/**
 * Silent Voice API service.
 *
 * Handles all Silent Voice Agent API calls:
 * - Patient monitoring (real-time distress detection)
 * - Baseline establishment / recalculation
 * - Alert acknowledgment
 * - ICU-wide overview
 * - Health check
 */

import apiClient from '../client';

// ─── Types ────────────────────────────────────────────────────────────────

export interface SignalData {
  vital: string;
  label: string;
  current: number;
  baseline_mean: number;
  baseline_std: number;
  z_score: number;
  deviation_pct: number;
  direction: 'elevated' | 'depressed';
}

export interface BaselineVital {
  mean: number;
  std: number;
}

export interface BaselineData {
  patient_id: string;
  established_at: string;
  vitals_count: number;
  baseline_window_minutes: number;
  baselines: Record<string, BaselineVital>;
}

export interface LatestVitals {
  hr: number | null;
  bp_sys: number | null;
  bp_dia: number | null;
  spo2: number | null;
  rr: number | null;
  hrv: number | null;
  recorded_at: string;
}

export interface MonitorResult {
  patient_id: string;
  patient_name: string;
  alert_level: 'critical' | 'warning' | 'clear';
  distress_active: boolean;
  distress_duration_minutes: number;
  signals_detected: SignalData[];
  latest_vitals: LatestVitals;
  baseline: BaselineData;
  last_analgesic_hours: number | null;
  clinical_output: string;
  recommended_action: string;
  timestamp: string;
}

export interface ICUOverview {
  total_patients: number;
  patients_with_alerts: number;
  results: MonitorResult[];
}

export interface SilentVoiceHealth {
  status: string;
  baseline_algorithm: string;
  zscore_threshold: number;
  demo_patient_ready: boolean;
  demo_patient_has_baseline: boolean;
}

// ─── API Functions ────────────────────────────────────────────────────────

export const silentVoiceService = {
  /** Monitor a patient for non-verbal distress */
  monitor: (patientId: string, language: string = 'en') =>
    apiClient.get<MonitorResult>(`/silent-voice/monitor/${patientId}`, { params: { language } }),

  /** Force baseline recalculation */
  establishBaseline: (patientId: string) =>
    apiClient.post<BaselineData>(`/silent-voice/baseline/${patientId}`),

  /** Acknowledge a distress alert */
  acknowledgeAlert: (alertId: string) =>
    apiClient.post<{ success: boolean; acknowledged_by: string; at: string }>(
      `/silent-voice/acknowledge/${alertId}`
    ),

  /** Get ICU-wide overview of all patients with alerts */
  getIcuOverview: () =>
    apiClient.get<ICUOverview>('/silent-voice/icu-overview'),

  /** Health check (no auth required) */
  checkHealth: () =>
    apiClient.get<SilentVoiceHealth>('/silent-voice/health'),
};

export default silentVoiceService;
