/**
 * AI Agents API Client
 * 
 * Provides type-safe API calls to all Phoenix Guardian AI agents:
 * - ScribeAgent: SOAP note generation
 * - SafetyAgent: Drug interaction checking
 * - NavigatorAgent: Workflow suggestions
 * - CodingAgent: ICD-10/CPT code suggestions
 * - SentinelAgent: Security threat detection
 */

import apiClient from './client';

// ============================================================================
// Type Definitions
// ============================================================================

export interface SOAPRequest {
  chief_complaint: string;
  vitals: Record<string, string>;
  symptoms: string[];
  exam_findings: string;
}

export interface SOAPResponse {
  soap_note: string;
  icd_codes: string[];
  agent: string;
  model: string;
}

export interface SafetyCheckRequest {
  medications: string[];
}

export interface Interaction {
  medications?: string[];
  severity: string;
  description?: string;
  source: string;
  finding?: string;
}

export interface SafetyCheckResponse {
  interactions: Interaction[];
  severity: string;
  checked_medications: string[];
  agent: string;
}

export interface WorkflowRequest {
  current_status: string;
  encounter_type: string;
  pending_items?: string[];
}

export interface WorkflowResponse {
  next_steps: string[];
  priority: string;
  agent: string;
}

export interface CodingRequest {
  clinical_note: string;
  procedures?: string[];
}

export interface CodeSuggestion {
  code: string;
  description: string;
  confidence: string;
}

export interface CodingResponse {
  icd10_codes: CodeSuggestion[];
  cpt_codes: CodeSuggestion[];
  agent: string;
}

export interface SecurityAnalysisRequest {
  user_input: string;
  context?: string;
}

export interface SecurityAnalysisResponse {
  threat_detected: boolean;
  threat_type: string;
  confidence: number;
  details: string;
  method: string;
  agent: string;
}

export interface ReadmissionRequest {
  age: number;
  has_heart_failure: boolean;
  has_diabetes: boolean;
  has_copd: boolean;
  comorbidity_count: number;
  length_of_stay: number;
  visits_30d: number;
  visits_90d: number;
  discharge_disposition: 'home' | 'snf' | 'rehab';
}

export interface ReadmissionResponse {
  risk_score: number;
  probability: number;
  risk_level: 'LOW' | 'MODERATE' | 'HIGH';
  alert: boolean;
  model_auc: number;
  factors: string[];
  recommendations: string[];
  agent: string;
}

// ============================================================================
// API Functions
// ============================================================================

export const agentsAPI = {
  /**
   * Generate SOAP note from encounter data.
   * 
   * @param data - Encounter data including chief complaint, vitals, symptoms
   * @returns SOAP note with extracted ICD-10 codes
   */
  generateSOAP: async (data: SOAPRequest): Promise<SOAPResponse> => {
    const response = await apiClient.post('/agents/scribe/generate-soap', data);
    return response.data;
  },

  /**
   * Check medications for drug interactions.
   * 
   * @param medications - List of medication names
   * @returns Interaction report with severity assessment
   */
  checkDrugInteractions: async (medications: string[]): Promise<SafetyCheckResponse> => {
    const response = await apiClient.post('/agents/safety/check-interactions', {
      medications
    });
    return response.data;
  },

  /**
   * Get workflow suggestions for clinical encounter.
   * 
   * @param data - Current status, encounter type, and pending items
   * @returns Prioritized list of next steps
   */
  suggestWorkflow: async (data: WorkflowRequest): Promise<WorkflowResponse> => {
    const response = await apiClient.post('/agents/navigator/suggest-workflow', data);
    return response.data;
  },

  /**
   * Suggest ICD-10 and CPT codes from clinical documentation.
   * 
   * @param data - Clinical note and optional procedures list
   * @returns Suggested diagnosis and procedure codes
   */
  suggestCodes: async (data: CodingRequest): Promise<CodingResponse> => {
    const response = await apiClient.post('/agents/coding/suggest-codes', data);
    return response.data;
  },

  /**
   * Analyze user input for security threats.
   * 
   * @param userInput - Text to analyze for threats
   * @param context - Optional context information
   * @returns Threat detection result
   */
  analyzeSecurity: async (userInput: string, context?: string): Promise<SecurityAnalysisResponse> => {
    const response = await apiClient.post('/agents/sentinel/analyze-input', {
      user_input: userInput,
      context: context || ''
    });
    return response.data;
  },

  /**
   * Predict 30-day readmission risk for a patient.
   * 
   * Uses trained XGBoost model to predict readmission risk
   * based on patient demographics, comorbidities, and encounter data.
   * 
   * @param data - Patient data including age, comorbidities, LOS
   * @returns Risk score, level, factors, and recommendations
   */
  predictReadmission: async (data: ReadmissionRequest): Promise<ReadmissionResponse> => {
    const response = await apiClient.post('/agents/readmission/predict-risk', data);
    return response.data;
  }
};

export default agentsAPI;
