/**
 * Treatment Shadow API service.
 *
 * Handles all Treatment Shadow Agent API calls:
 * - Patient analysis (run shadow detection)
 * - List all fired alerts
 * - Dismiss a shadow
 * - Health check
 */

import apiClient from '../client';

// ─── Types ────────────────────────────────────────────────────────────────

export interface ShadowTrend {
  slope: number;
  pct_change: number;
  direction: 'declining' | 'rising' | 'stable' | 'insufficient_data';
  r_squared: number;
  trend_summary: string;
}

export interface HarmTimeline {
  harm_started_estimate: string;
  current_stage: string;
  projection_90_days: string;
  days_until_irreversible: number;
}

export interface ActiveShadow {
  drug: string;
  prescribed_since: string;
  shadow_type: string;
  watch_lab: string;
  alert_fired: boolean;
  severity: 'watching' | 'mild' | 'moderate' | 'critical' | 'resolved';
  trend: ShadowTrend;
  lab_values: number[];
  lab_dates: string[];
  harm_timeline: HarmTimeline | null;
  clinical_output: string;
  recommended_action: string;
}

export interface PatientAnalysis {
  patient_id: string;
  patient_name: string;
  analysis_timestamp: string;
  total_shadows: number;
  fired_count: number;
  active_shadows: ActiveShadow[];
}

export interface ShadowAlert {
  patient_id: string;
  patient_name: string;
  drug: string;
  shadow_type: string;
  severity: string;
  fired_at: string;
}

export interface AlertsResponse {
  total_alerts: number;
  alerts: ShadowAlert[];
}

export interface HealthResponse {
  status: string;
  openfda_reachable: boolean;
  shadow_library_loaded: boolean;
  demo_patient_ready: boolean;
}

// ─── Service ──────────────────────────────────────────────────────────────

export const treatmentShadowService = {
  /**
   * Analyze a patient for treatment shadows.
   */
  getPatientAnalysis: async (patientId: string): Promise<PatientAnalysis> => {
    const response = await apiClient.get<PatientAnalysis>(
      `/treatment-shadow/patient/${patientId}`
    );
    return response.data;
  },

  /**
   * Get all fired alerts across patients.
   */
  getAllAlerts: async (): Promise<AlertsResponse> => {
    const response = await apiClient.get<AlertsResponse>(
      '/treatment-shadow/alerts'
    );
    return response.data;
  },

  /**
   * Dismiss a specific shadow alert.
   */
  dismissShadow: async (shadowId: string): Promise<{ message: string }> => {
    const response = await apiClient.post<{ message: string }>(
      `/treatment-shadow/dismiss/${shadowId}`
    );
    return response.data;
  },

  /**
   * Check Treatment Shadow Agent health (no auth required).
   */
  checkHealth: async (): Promise<HealthResponse> => {
    const response = await apiClient.get<HealthResponse>(
      '/treatment-shadow/health'
    );
    return response.data;
  },
};

export default treatmentShadowService;
