/**
 * Phoenix Guardian Mobile - Encounter Service
 * 
 * API layer for encounter operations.
 * 
 * Features:
 * - CRUD operations for encounters
 * - Patient data fetching
 * - SOAP note approval
 * - EHR integration
 * 
 * @module services/EncounterService
 */

import AuthService from './AuthService';
import OfflineService from './OfflineService';
import { AxiosInstance } from 'axios';

// ============================================================================
// Types & Interfaces
// ============================================================================

export type EncounterStatus = 
  | 'draft'
  | 'recording'
  | 'processing'
  | 'review'
  | 'approved'
  | 'submitted'
  | 'error';

export interface Patient {
  id: string;
  mrn: string;
  firstName: string;
  lastName: string;
  dateOfBirth: string;
  gender: 'male' | 'female' | 'other';
  roomNumber?: string;
  admitDate?: string;
  diagnosis?: string[];
  allergies?: string[];
  medications?: string[];
}

export interface Encounter {
  id: string;
  patientId: string;
  patient?: Patient;
  tenantId: string;
  userId: string;
  status: EncounterStatus;
  encounterType: 'routine' | 'followup' | 'emergency' | 'consultation';
  audioDuration?: number;
  transcript?: string;
  soapNote?: SOAPNote;
  createdAt: string;
  updatedAt: string;
  submittedAt?: string;
  submittedBy?: string;
}

export interface SOAPNote {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
}

export interface EncounterCreateRequest {
  patientId: string;
  encounterType?: 'routine' | 'followup' | 'emergency' | 'consultation';
}

export interface EncounterUpdateRequest {
  soapNote?: Partial<SOAPNote>;
  status?: EncounterStatus;
}

export interface EncounterListOptions {
  status?: EncounterStatus | EncounterStatus[];
  patientId?: string;
  startDate?: string;
  endDate?: string;
  limit?: number;
  offset?: number;
}

export interface EncounterListResponse {
  encounters: Encounter[];
  total: number;
  hasMore: boolean;
}

export interface ApprovalResult {
  success: boolean;
  encounterId: string;
  ehrReferenceId?: string;
  submittedAt?: string;
  error?: string;
}

// ============================================================================
// EncounterService Class
// ============================================================================

class EncounterService {
  private static instance: EncounterService;
  private apiClient: AxiosInstance;

  private constructor() {
    this.apiClient = AuthService.getApiClient();
  }

  static getInstance(): EncounterService {
    if (!EncounterService.instance) {
      EncounterService.instance = new EncounterService();
    }
    return EncounterService.instance;
  }

  // ==========================================================================
  // Encounter CRUD
  // ==========================================================================

  /**
   * Create a new encounter.
   */
  async createEncounter(request: EncounterCreateRequest): Promise<Encounter> {
    // Check if offline
    if (!OfflineService.isOnline()) {
      return this.createOfflineEncounter(request);
    }

    const response = await this.apiClient.post<Encounter>('/encounters', {
      patient_id: request.patientId,
      encounter_type: request.encounterType || 'routine',
    });

    return this.normalizeEncounter(response.data);
  }

  /**
   * Get encounter by ID.
   */
  async getEncounter(id: string): Promise<Encounter | null> {
    // Check offline storage first
    const offline = OfflineService.getEncounter(id);
    if (offline) {
      return this.offlineToEncounter(offline);
    }

    if (!OfflineService.isOnline()) {
      return null;
    }

    try {
      const response = await this.apiClient.get<Encounter>(`/encounters/${id}`);
      return this.normalizeEncounter(response.data);
    } catch (error) {
      if ((error as { response?: { status: number } }).response?.status === 404) {
        return null;
      }
      throw error;
    }
  }

  /**
   * List encounters with filters.
   */
  async listEncounters(options: EncounterListOptions = {}): Promise<EncounterListResponse> {
    // Get offline encounters
    const offlineEncounters = OfflineService.getEncounters()
      .map(e => this.offlineToEncounter(e))
      .filter(e => e !== null) as Encounter[];

    if (!OfflineService.isOnline()) {
      return {
        encounters: this.filterEncounters(offlineEncounters, options),
        total: offlineEncounters.length,
        hasMore: false,
      };
    }

    const params = new URLSearchParams();
    
    if (options.status) {
      const statuses = Array.isArray(options.status) ? options.status : [options.status];
      params.append('status', statuses.join(','));
    }
    if (options.patientId) params.append('patient_id', options.patientId);
    if (options.startDate) params.append('start_date', options.startDate);
    if (options.endDate) params.append('end_date', options.endDate);
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.offset) params.append('offset', options.offset.toString());

    const response = await this.apiClient.get<EncounterListResponse>(
      `/encounters?${params.toString()}`
    );

    // Merge with offline encounters
    const serverEncounters = response.data.encounters.map(e => this.normalizeEncounter(e));
    const merged = this.mergeEncounterLists(offlineEncounters, serverEncounters);

    return {
      encounters: this.filterEncounters(merged, options),
      total: response.data.total + offlineEncounters.length,
      hasMore: response.data.hasMore,
    };
  }

  /**
   * Update an encounter.
   */
  async updateEncounter(id: string, updates: EncounterUpdateRequest): Promise<Encounter | null> {
    // Check if this is an offline encounter
    const offline = OfflineService.getEncounter(id);
    if (offline) {
      const updated = await OfflineService.updateEncounter(id, {
        soapNote: updates.soapNote ? {
          subjective: updates.soapNote.subjective || offline.soapNote?.subjective || '',
          objective: updates.soapNote.objective || offline.soapNote?.objective || '',
          assessment: updates.soapNote.assessment || offline.soapNote?.assessment || '',
          plan: updates.soapNote.plan || offline.soapNote?.plan || '',
        } : offline.soapNote,
      });
      return updated ? this.offlineToEncounter(updated) : null;
    }

    if (!OfflineService.isOnline()) {
      throw new Error('Cannot update server encounter while offline');
    }

    const response = await this.apiClient.patch<Encounter>(`/encounters/${id}`, {
      soap_note: updates.soapNote,
      status: updates.status,
    });

    return this.normalizeEncounter(response.data);
  }

  /**
   * Delete an encounter.
   */
  async deleteEncounter(id: string): Promise<boolean> {
    // Check if this is an offline encounter
    const offline = OfflineService.getEncounter(id);
    if (offline) {
      return OfflineService.deleteEncounter(id);
    }

    if (!OfflineService.isOnline()) {
      throw new Error('Cannot delete server encounter while offline');
    }

    await this.apiClient.delete(`/encounters/${id}`);
    return true;
  }

  // ==========================================================================
  // SOAP Note Operations
  // ==========================================================================

  /**
   * Update a specific SOAP section.
   */
  async updateSOAPSection(
    encounterId: string,
    section: keyof SOAPNote,
    text: string
  ): Promise<Encounter | null> {
    // Check if offline encounter
    const offline = OfflineService.getEncounter(encounterId);
    if (offline) {
      const updated = await OfflineService.updateSOAPNote(encounterId, section, text);
      return updated ? this.offlineToEncounter(updated) : null;
    }

    return this.updateEncounter(encounterId, {
      soapNote: { [section]: text },
    });
  }

  /**
   * Regenerate a SOAP section using AI.
   */
  async regenerateSOAPSection(
    encounterId: string,
    section: keyof SOAPNote,
    context?: string
  ): Promise<string> {
    if (!OfflineService.isOnline()) {
      throw new Error('Cannot regenerate while offline');
    }

    const response = await this.apiClient.post<{ text: string }>(
      `/encounters/${encounterId}/regenerate`,
      { section, context }
    );

    return response.data.text;
  }

  // ==========================================================================
  // Approval & Submission
  // ==========================================================================

  /**
   * Approve and submit encounter to EHR.
   */
  async approveEncounter(encounterId: string): Promise<ApprovalResult> {
    // Check if offline encounter
    const offline = OfflineService.getEncounter(encounterId);
    if (offline) {
      // Queue for submission when online
      await OfflineService.updateEncounter(encounterId, {
        status: 'pending',
      });
      
      return {
        success: true,
        encounterId,
        submittedAt: new Date().toISOString(),
      };
    }

    if (!OfflineService.isOnline()) {
      throw new Error('Cannot approve while offline');
    }

    try {
      const response = await this.apiClient.post<ApprovalResult>(
        `/encounters/${encounterId}/approve`
      );

      return response.data;
    } catch (error: unknown) {
      return {
        success: false,
        encounterId,
        error: error instanceof Error ? error.message : 'Approval failed',
      };
    }
  }

  /**
   * Batch approve multiple encounters.
   */
  async batchApprove(encounterIds: string[]): Promise<ApprovalResult[]> {
    if (!OfflineService.isOnline()) {
      throw new Error('Cannot batch approve while offline');
    }

    const response = await this.apiClient.post<{ results: ApprovalResult[] }>(
      '/encounters/batch-approve',
      { encounter_ids: encounterIds }
    );

    return response.data.results;
  }

  // ==========================================================================
  // Patient Operations
  // ==========================================================================

  /**
   * Search for patients.
   */
  async searchPatients(query: string): Promise<Patient[]> {
    if (!OfflineService.isOnline()) {
      // Return cached patients if available
      return [];
    }

    const response = await this.apiClient.get<Patient[]>(
      `/patients/search?q=${encodeURIComponent(query)}`
    );

    return response.data;
  }

  /**
   * Get patient by ID.
   */
  async getPatient(id: string): Promise<Patient | null> {
    if (!OfflineService.isOnline()) {
      return null;
    }

    try {
      const response = await this.apiClient.get<Patient>(`/patients/${id}`);
      return response.data;
    } catch (error) {
      if ((error as { response?: { status: number } }).response?.status === 404) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Get patients for current unit/location.
   */
  async getPatientList(): Promise<Patient[]> {
    if (!OfflineService.isOnline()) {
      return [];
    }

    const response = await this.apiClient.get<Patient[]>('/patients');
    return response.data;
  }

  // ==========================================================================
  // Statistics
  // ==========================================================================

  /**
   * Get encounter statistics.
   */
  async getStatistics(startDate?: string, endDate?: string): Promise<{
    total: number;
    byStatus: Record<EncounterStatus, number>;
    byType: Record<string, number>;
    averageProcessingTime: number;
  }> {
    if (!OfflineService.isOnline()) {
      // Return offline statistics
      const encounters = OfflineService.getEncounters();
      return {
        total: encounters.length,
        byStatus: { 
          draft: 0, 
          recording: 0, 
          processing: 0, 
          review: encounters.length, 
          approved: 0, 
          submitted: 0, 
          error: 0 
        },
        byType: {},
        averageProcessingTime: 0,
      };
    }

    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);

    const response = await this.apiClient.get(`/encounters/statistics?${params.toString()}`);
    return response.data;
  }

  // ==========================================================================
  // Private Helpers
  // ==========================================================================

  private createOfflineEncounter(request: EncounterCreateRequest): Encounter {
    const id = `offline_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const now = new Date().toISOString();
    
    return {
      id,
      patientId: request.patientId,
      tenantId: AuthService.getTenantId() || '',
      userId: AuthService.getUserInfo()?.userId || '',
      status: 'draft',
      encounterType: request.encounterType || 'routine',
      createdAt: now,
      updatedAt: now,
    };
  }

  private offlineToEncounter(offline: { 
    id: string; 
    patientId: string; 
    tenantId: string;
    soapNote?: SOAPNote;
    createdAt: string;
    updatedAt: string;
    audioDuration?: number;
    transcript?: string;
  }): Encounter {
    return {
      id: offline.id,
      patientId: offline.patientId,
      tenantId: offline.tenantId,
      userId: AuthService.getUserInfo()?.userId || '',
      status: 'review',
      encounterType: 'routine',
      audioDuration: offline.audioDuration,
      transcript: offline.transcript,
      soapNote: offline.soapNote,
      createdAt: offline.createdAt,
      updatedAt: offline.updatedAt,
    };
  }

  private normalizeEncounter(data: Encounter & {
    patient_id?: string;
    tenant_id?: string;
    user_id?: string;
    encounter_type?: string;
    audio_duration?: number;
    soap_note?: SOAPNote;
    created_at?: string;
    updated_at?: string;
    submitted_at?: string;
    submitted_by?: string;
  }): Encounter {
    return {
      id: data.id,
      patientId: data.patient_id || data.patientId,
      patient: data.patient,
      tenantId: data.tenant_id || data.tenantId,
      userId: data.user_id || data.userId,
      status: data.status,
      encounterType: (data.encounter_type || data.encounterType) as Encounter['encounterType'],
      audioDuration: data.audio_duration || data.audioDuration,
      transcript: data.transcript,
      soapNote: data.soap_note || data.soapNote,
      createdAt: data.created_at || data.createdAt,
      updatedAt: data.updated_at || data.updatedAt,
      submittedAt: data.submitted_at || data.submittedAt,
      submittedBy: data.submitted_by || data.submittedBy,
    };
  }

  private mergeEncounterLists(offline: Encounter[], server: Encounter[]): Encounter[] {
    const serverIds = new Set(server.map(e => e.id));
    const uniqueOffline = offline.filter(e => !serverIds.has(e.id));
    return [...uniqueOffline, ...server];
  }

  private filterEncounters(encounters: Encounter[], options: EncounterListOptions): Encounter[] {
    let filtered = encounters;

    if (options.status) {
      const statuses = Array.isArray(options.status) ? options.status : [options.status];
      filtered = filtered.filter(e => statuses.includes(e.status));
    }

    if (options.patientId) {
      filtered = filtered.filter(e => e.patientId === options.patientId);
    }

    if (options.startDate) {
      const start = new Date(options.startDate);
      filtered = filtered.filter(e => new Date(e.createdAt) >= start);
    }

    if (options.endDate) {
      const end = new Date(options.endDate);
      filtered = filtered.filter(e => new Date(e.createdAt) <= end);
    }

    // Sort by createdAt descending
    filtered.sort((a, b) => 
      new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );

    // Apply pagination
    if (options.offset) {
      filtered = filtered.slice(options.offset);
    }
    if (options.limit) {
      filtered = filtered.slice(0, options.limit);
    }

    return filtered;
  }
}

// Export singleton instance
export default EncounterService.getInstance();
