/**
 * API services module exports.
 */

export { authService, transformUserResponse } from './authService';
export type {
  LoginRequest,
  LoginResponse,
  RefreshRequest,
  RefreshResponse,
  ChangePasswordRequest,
  UserApiResponse,
} from './authService';

export { encounterService, transformEncounterResponse } from './encounterService';
export { treatmentShadowService } from './treatmentShadowService';
export { silentVoiceService } from './silentVoiceService';
export { zebraHunterService } from './zebraHunterService';
export { v5DashboardService } from './v5DashboardService';
export type {
  V5StatusResponse, ActiveAlert as V5ActiveAlert, AgentStatuses,
  ImpactSummary, ShadowAgentStatus, SilentVoiceAgentStatus,
  ZebraHunterAgentStatus,
} from './v5DashboardService';
export type {
  AnalyzeResponse as ZebraAnalyzeResponse,
  MatchResponse as ZebraMatchResponse,
  TimelineEntry as ZebraTimelineEntry,
  GhostProtocolResult,
  GhostCaseResponse,
  GhostCasesListResponse,
  ReportGhostResponse,
  ZebraHunterHealth,
} from './zebraHunterService';
export type {
  ShadowTrend,
  HarmTimeline,
  ActiveShadow,
  PatientAnalysis,
  ShadowAlert,
  AlertsResponse,
  HealthResponse,
} from './treatmentShadowService';
export type {
  EncounterStatus,
  SOAPSection,
  PatientInfo,
  CreateEncounterRequest,
  EncounterApiResponse,
  Encounter,
  SafetyFlag,
  ICDCode,
  CPTCode,
  UpdateSOAPNoteRequest,
  ApproveSOAPNoteRequest,
  RejectSOAPNoteRequest,
  ProcessEncounterResponse,
  EncounterListResponse,
  ListEncountersParams,
} from './encounterService';
