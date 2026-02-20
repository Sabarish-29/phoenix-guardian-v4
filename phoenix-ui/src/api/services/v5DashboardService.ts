/**
 * V5 Dashboard API service.
 * Single endpoint that returns unified status for the dashboard.
 */

import apiClient from '../client';

// ── Types ────────────────────────────────────────────────────────────────

export interface TopAlert {
  patient_id: string;
  patient_name: string;
  summary: string;
  severity: string;
  agent: string;
  link: string;
}

export interface ShadowAgentStatus {
  status: string;
  fired_count: number;
  watching_count: number;
  top_alert: TopAlert | null;
  b12_pct_change: number;
  days_to_harm: number;
}

export interface SilentVoiceAgentStatus {
  status: string;
  active_alerts: number;
  distress_duration_minutes: number;
  top_alert: TopAlert | null;
  signals_detected: number;
  last_analgesic_hours: number;
}

export interface ZebraHunterAgentStatus {
  status: string;
  zebra_count: number;
  ghost_count: number;
  top_alert: TopAlert | null;
  years_lost: number;
  top_disease: string;
  top_confidence: number;
}

export interface AgentStatuses {
  treatment_shadow: ShadowAgentStatus;
  silent_voice: SilentVoiceAgentStatus;
  zebra_hunter: ZebraHunterAgentStatus;
}

export interface ImpactSummary {
  rare_diseases_detected: number;
  silent_distress_caught: number;
  treatment_harms_prevented: number;
  ghost_cases_created: number;
  years_suffering_prevented: number;
}

export interface ExistingAgents {
  all_operational: boolean;
  count: number;
  security_block_rate: string;
}

export interface ActiveAlert {
  agent: string;
  agent_icon: string;
  patient_name: string;
  patient_id: string;
  location: string;
  summary: string;
  detail: string;
  severity: string;
  link: string;
}

export interface V5StatusResponse {
  timestamp: string;
  demo_patients_loaded: number;
  all_agents_healthy: boolean;
  active_alerts: ActiveAlert[];
  agents: AgentStatuses;
  impact: ImpactSummary;
  existing_agents: ExistingAgents;
}

// ── Service ──────────────────────────────────────────────────────────────

export const v5DashboardService = {
  getStatus: async (): Promise<V5StatusResponse> => {
    const response = await apiClient.get('/v5/status');
    return response.data;
  },
};
