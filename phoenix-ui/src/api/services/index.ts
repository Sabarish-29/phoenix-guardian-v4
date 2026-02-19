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
