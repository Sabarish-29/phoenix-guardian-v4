import { apiRequest } from './client';
import type { Incident, IncidentStatus, IncidentTimeline, IncidentMetrics } from '../../types/incident';

const BASE_PATH = '/dashboard/incidents';

export const incidentsApi = {
  /**
   * Get all incidents, optionally filtered by status
   */
  async getIncidents(status?: IncidentStatus): Promise<Incident[]> {
    const params = status ? `?status=${status}` : '';
    return apiRequest<Incident[]>({
      method: 'GET',
      url: `${BASE_PATH}${params}`,
    });
  },

  /**
   * Get incident by ID
   */
  async getIncidentById(incidentId: string): Promise<Incident> {
    return apiRequest<Incident>({
      method: 'GET',
      url: `${BASE_PATH}/${incidentId}`,
    });
  },

  /**
   * Create a new incident
   */
  async createIncident(data: Partial<Incident>): Promise<Incident> {
    return apiRequest<Incident>({
      method: 'POST',
      url: BASE_PATH,
      data,
    });
  },

  /**
   * Update incident status
   */
  async updateStatus(incidentId: string, status: IncidentStatus, notes?: string): Promise<Incident> {
    return apiRequest<Incident>({
      method: 'PATCH',
      url: `${BASE_PATH}/${incidentId}/status`,
      data: { status, notes },
    });
  },

  /**
   * Assign incident to a user
   */
  async assignIncident(incidentId: string, assigneeId: string): Promise<Incident> {
    return apiRequest<Incident>({
      method: 'PATCH',
      url: `${BASE_PATH}/${incidentId}/assign`,
      data: { assignee_id: assigneeId },
    });
  },

  /**
   * Get incident timeline
   */
  async getIncidentTimeline(incidentId: string): Promise<IncidentTimeline[]> {
    return apiRequest<IncidentTimeline[]>({
      method: 'GET',
      url: `${BASE_PATH}/${incidentId}/timeline`,
    });
  },

  /**
   * Add note to incident
   */
  async addNote(incidentId: string, note: string): Promise<IncidentTimeline> {
    return apiRequest<IncidentTimeline>({
      method: 'POST',
      url: `${BASE_PATH}/${incidentId}/notes`,
      data: { content: note },
    });
  },

  /**
   * Add containment action
   */
  async addContainmentAction(incidentId: string, action: string): Promise<Incident> {
    return apiRequest<Incident>({
      method: 'POST',
      url: `${BASE_PATH}/${incidentId}/containment`,
      data: { action },
    });
  },

  /**
   * Add remediation action
   */
  async addRemediationAction(incidentId: string, action: string): Promise<Incident> {
    return apiRequest<Incident>({
      method: 'POST',
      url: `${BASE_PATH}/${incidentId}/remediation`,
      data: { action },
    });
  },

  /**
   * Get incident metrics
   */
  async getMetrics(): Promise<IncidentMetrics> {
    return apiRequest<IncidentMetrics>({
      method: 'GET',
      url: `${BASE_PATH}/metrics`,
    });
  },

  /**
   * Close incident with lessons learned
   */
  async closeIncident(incidentId: string, lessonsLearned: string): Promise<Incident> {
    return apiRequest<Incident>({
      method: 'POST',
      url: `${BASE_PATH}/${incidentId}/close`,
      data: { lessons_learned: lessonsLearned },
    });
  },
};
