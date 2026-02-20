/**
 * Zebra Hunter API service — rare disease detection.
 */

import apiClient from '../client';

// ─── Types ────────────────────────────────────────────────────────────────

export interface MatchResponse {
  disease: string;
  orphacode: string;
  confidence: number;
  matching_symptoms: string[];
  total_patient_symptoms: number;
  url: string;
}

export interface TimelineEntry {
  visit_number: number;
  visit_date: string;
  diagnosis_given: string;
  was_diagnosable: boolean;
  missed_clues: string[];
  confidence: number;
  reason: string;
  is_first_diagnosable: boolean;
}

export interface GhostProtocolResult {
  activated: boolean;
  ghost_id: string | null;
  patient_count: number;
  symptom_signature: string[];
  symptom_hash: string;
  first_case_seen: string;
  message: string;
}

export interface AnalyzeResponse {
  status: string;
  patient_id: string;
  patient_name: string;
  total_visits: number;
  symptoms_found: string[];
  analysis_timestamp: string;
  top_matches: MatchResponse[];
  missed_clue_timeline: TimelineEntry[];
  years_lost: number;
  first_diagnosable_visit: TimelineEntry | null;
  recommendation: string;
  ghost_protocol: GhostProtocolResult | null;
  analysis_time_seconds: number;
}

export interface GhostCaseResponse {
  ghost_id: string;
  patient_count: number;
  symptom_signature: string[];
  status: string;
  first_seen: string;
  alert_fired_at: string | null;
  reported_to: string | null;
}

export interface GhostCasesListResponse {
  total_ghost_cases: number;
  alert_fired_count: number;
  cases: GhostCaseResponse[];
}

export interface ReportGhostResponse {
  ghost_id: string;
  status: string;
  reported_to: string;
  message: string;
}

export interface ZebraHunterHealth {
  status: string;
  orphadata_reachable: boolean;
  orphadata_authenticated: boolean;
  demo_fallback_loaded: boolean;
  redis_connected: boolean;
  patient_a_ready: boolean;
  patient_b_ready: boolean;
  ghost_seed_exists: boolean;
}

// ─── Service ──────────────────────────────────────────────────────────────

export const zebraHunterService = {
  analyzePatient: async (patientId: string): Promise<AnalyzeResponse> => {
    const response = await apiClient.post<AnalyzeResponse>(
      `/zebra-hunter/analyze/${patientId}`
    );
    return response.data;
  },

  getResult: async (patientId: string): Promise<AnalyzeResponse> => {
    const response = await apiClient.get<AnalyzeResponse>(
      `/zebra-hunter/result/${patientId}`
    );
    return response.data;
  },

  getGhostCases: async (): Promise<GhostCasesListResponse> => {
    const response = await apiClient.get<GhostCasesListResponse>(
      '/zebra-hunter/ghost-cases'
    );
    return response.data;
  },

  reportGhost: async (ghostId: string): Promise<ReportGhostResponse> => {
    const response = await apiClient.post<ReportGhostResponse>(
      `/zebra-hunter/report-ghost/${ghostId}`
    );
    return response.data;
  },

  checkHealth: async (): Promise<ZebraHunterHealth> => {
    const response = await apiClient.get<ZebraHunterHealth>(
      '/zebra-hunter/health'
    );
    return response.data;
  },
};

export default zebraHunterService;
