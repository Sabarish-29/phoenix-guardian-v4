/**
 * Encounter API service.
 * 
 * Handles all encounter-related API calls:
 * - Create encounter
 * - Get encounter details
 * - Update SOAP note
 * - Approve/reject SOAP note
 * - Process encounter through AI pipeline
 */

import apiClient from '../client';

/**
 * Encounter status types
 */
export type EncounterStatus = 
  | 'pending'
  | 'processing'
  | 'transcription_complete'
  | 'scribe_processing'
  | 'awaiting_review'
  | 'approved'
  | 'rejected'
  | 'signed'
  | 'error';

/**
 * SOAP note section
 */
export interface SOAPSection {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
}

/**
 * Patient information
 */
export interface PatientInfo {
  patient_id?: string;
  first_name?: string;
  last_name?: string;
  date_of_birth?: string;
  gender?: string;
  mrn?: string;
}

/**
 * Create encounter request
 */
export interface CreateEncounterRequest {
  patient_info?: PatientInfo;
  encounter_type?: string;
  chief_complaint?: string;
  audio_file_path?: string;
  transcript_text?: string;
  additional_context?: Record<string, unknown>;
}

/**
 * Encounter API response (snake_case)
 */
export interface EncounterApiResponse {
  id: number;
  uuid: string;
  status: EncounterStatus;
  patient_first_name: string | null;
  patient_last_name: string | null;
  patient_dob: string | null;
  patient_mrn: string | null;
  encounter_type: string | null;
  chief_complaint: string | null;
  transcript_text: string | null;
  soap_note: SOAPSection | null;
  ai_confidence_score: number | null;
  safety_flags: SafetyFlag[] | null;
  icd_codes: ICDCode[] | null;
  cpt_codes: CPTCode[] | null;
  physician_edits: string | null;
  physician_signature: string | null;
  signed_at: string | null;
  created_at: string;
  updated_at: string | null;
  created_by_id: number;
  assigned_physician_id: number | null;
}

/**
 * Frontend encounter model (camelCase)
 */
export interface Encounter {
  id: number;
  uuid: string;
  status: EncounterStatus;
  patientFirstName: string | null;
  patientLastName: string | null;
  patientDob: string | null;
  patientMrn: string | null;
  encounterType: string | null;
  chiefComplaint: string | null;
  transcriptText: string | null;
  soapNote: SOAPSection | null;
  aiConfidenceScore: number | null;
  safetyFlags: SafetyFlag[] | null;
  icdCodes: ICDCode[] | null;
  cptCodes: CPTCode[] | null;
  physicianEdits: string | null;
  physicianSignature: string | null;
  signedAt: string | null;
  createdAt: string;
  updatedAt: string | null;
  createdById: number;
  assignedPhysicianId: number | null;
}

/**
 * Safety flag from SafetyAgent
 */
export interface SafetyFlag {
  code: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  category: string;
  recommendation?: string;
}

/**
 * ICD-10 code from NavigatorAgent
 */
export interface ICDCode {
  code: string;
  description: string;
  confidence: number;
  primary?: boolean;
}

/**
 * CPT code from NavigatorAgent
 */
export interface CPTCode {
  code: string;
  description: string;
  confidence: number;
  modifiers?: string[];
}

/**
 * Update SOAP note request
 */
export interface UpdateSOAPNoteRequest {
  soap_note: SOAPSection;
  physician_edits?: string;
}

/**
 * Approve SOAP note request
 */
export interface ApproveSOAPNoteRequest {
  signature: string;
  attestation?: string;
}

/**
 * Reject SOAP note request
 */
export interface RejectSOAPNoteRequest {
  reason: string;
  notes?: string;
}

/**
 * Process encounter response
 */
export interface ProcessEncounterResponse {
  encounter_id: number;
  uuid: string;
  status: EncounterStatus;
  soap_note: SOAPSection | null;
  safety_flags: SafetyFlag[] | null;
  icd_codes: ICDCode[] | null;
  cpt_codes: CPTCode[] | null;
  confidence_score: number | null;
  processing_time_ms: number;
}

/**
 * Encounter list response
 */
export interface EncounterListResponse {
  items: EncounterApiResponse[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/**
 * List encounters query parameters
 */
export interface ListEncountersParams {
  page?: number;
  page_size?: number;
  status?: EncounterStatus;
  assigned_physician_id?: number;
  search?: string;
  date_from?: string;
  date_to?: string;
}

/**
 * Transform API encounter response to frontend model
 */
export const transformEncounterResponse = (apiEncounter: EncounterApiResponse): Encounter => ({
  id: apiEncounter.id,
  uuid: apiEncounter.uuid,
  status: apiEncounter.status,
  patientFirstName: apiEncounter.patient_first_name,
  patientLastName: apiEncounter.patient_last_name,
  patientDob: apiEncounter.patient_dob,
  patientMrn: apiEncounter.patient_mrn,
  encounterType: apiEncounter.encounter_type,
  chiefComplaint: apiEncounter.chief_complaint,
  transcriptText: apiEncounter.transcript_text,
  soapNote: apiEncounter.soap_note,
  aiConfidenceScore: apiEncounter.ai_confidence_score,
  safetyFlags: apiEncounter.safety_flags,
  icdCodes: apiEncounter.icd_codes,
  cptCodes: apiEncounter.cpt_codes,
  physicianEdits: apiEncounter.physician_edits,
  physicianSignature: apiEncounter.physician_signature,
  signedAt: apiEncounter.signed_at,
  createdAt: apiEncounter.created_at,
  updatedAt: apiEncounter.updated_at,
  createdById: apiEncounter.created_by_id,
  assignedPhysicianId: apiEncounter.assigned_physician_id,
});

/**
 * Encounter service
 */
export const encounterService = {
  /**
   * Create a new encounter.
   */
  async createEncounter(data: CreateEncounterRequest): Promise<Encounter> {
    const response = await apiClient.post<EncounterApiResponse>('/encounters/', data);
    return transformEncounterResponse(response.data);
  },
  
  /**
   * Get encounter by ID or UUID.
   */
  async getEncounter(idOrUuid: number | string): Promise<Encounter> {
    const response = await apiClient.get<EncounterApiResponse>(`/encounters/${idOrUuid}`);
    return transformEncounterResponse(response.data);
  },
  
  /**
   * List encounters with optional filters.
   */
  async listEncounters(params?: ListEncountersParams): Promise<{
    items: Encounter[];
    total: number;
    page: number;
    pageSize: number;
    pages: number;
  }> {
    const response = await apiClient.get<EncounterListResponse>('/encounters/', { params });
    return {
      items: response.data.items.map(transformEncounterResponse),
      total: response.data.total,
      page: response.data.page,
      pageSize: response.data.page_size,
      pages: response.data.pages,
    };
  },
  
  /**
   * Process encounter through AI pipeline (ScribeAgent, NavigatorAgent, SafetyAgent).
   */
  async processEncounter(encounterId: number): Promise<ProcessEncounterResponse> {
    const response = await apiClient.post<ProcessEncounterResponse>(
      `/encounters/${encounterId}/process`
    );
    return response.data;
  },
  
  /**
   * Update SOAP note for an encounter.
   */
  async updateSOAPNote(encounterId: number, data: UpdateSOAPNoteRequest): Promise<Encounter> {
    const response = await apiClient.put<EncounterApiResponse>(
      `/encounters/${encounterId}/soap-note`,
      data
    );
    return transformEncounterResponse(response.data);
  },
  
  /**
   * Approve SOAP note with physician signature.
   */
  async approveSOAPNote(encounterId: number, data: ApproveSOAPNoteRequest): Promise<Encounter> {
    const response = await apiClient.post<EncounterApiResponse>(
      `/encounters/${encounterId}/approve`,
      data
    );
    return transformEncounterResponse(response.data);
  },
  
  /**
   * Reject SOAP note with reason.
   */
  async rejectSOAPNote(encounterId: number, data: RejectSOAPNoteRequest): Promise<Encounter> {
    const response = await apiClient.post<EncounterApiResponse>(
      `/encounters/${encounterId}/reject`,
      data
    );
    return transformEncounterResponse(response.data);
  },
  
  /**
   * Get encounters awaiting review (for physicians).
   */
  async getAwaitingReview(page = 1, pageSize = 10): Promise<{
    items: Encounter[];
    total: number;
  }> {
    return this.listEncounters({
      page,
      page_size: pageSize,
      status: 'awaiting_review',
    });
  },
  
  /**
   * Get patient's encounter history.
   */
  async getPatientEncounters(patientMrn: string): Promise<Encounter[]> {
    const result = await this.listEncounters({ search: patientMrn });
    return result.items;
  },
  
  /**
   * Upload audio file for encounter.
   */
  async uploadAudio(encounterId: number, file: File): Promise<{ audio_url: string }> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await apiClient.post<{ audio_url: string }>(
      `/encounters/${encounterId}/upload-audio`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    
    return response.data;
  },
};

export default encounterService;
