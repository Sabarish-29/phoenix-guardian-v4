import { apiRequest } from './client';
import type { Threat, ThreatFilters, ThreatStats } from '../../types/threat';

const BASE_PATH = '/dashboard/threats';

export const threatsApi = {
  /**
   * Get list of threats with optional filters
   */
  async getThreats(filters?: ThreatFilters): Promise<Threat[]> {
    const params = new URLSearchParams();
    
    if (filters) {
      if (filters.severity.length > 0) {
        params.append('severity', filters.severity.join(','));
      }
      if (filters.attackType.length > 0) {
        params.append('attack_type', filters.attackType.join(','));
      }
      if (filters.timeRange) {
        params.append('time_range', filters.timeRange);
      }
      if (filters.searchQuery) {
        params.append('search', filters.searchQuery);
      }
      if (filters.acknowledged !== undefined) {
        params.append('acknowledged', String(filters.acknowledged));
      }
    }
    
    return apiRequest<Threat[]>({
      method: 'GET',
      url: `${BASE_PATH}?${params.toString()}`,
    });
  },

  /**
   * Get threat by ID
   */
  async getThreatById(threatId: string): Promise<Threat> {
    return apiRequest<Threat>({
      method: 'GET',
      url: `${BASE_PATH}/${threatId}`,
    });
  },

  /**
   * Acknowledge a threat
   */
  async acknowledgeThreat(threatId: string): Promise<void> {
    return apiRequest<void>({
      method: 'POST',
      url: `${BASE_PATH}/${threatId}/acknowledge`,
    });
  },

  /**
   * Get threat statistics
   */
  async getThreatStats(timeRange?: string): Promise<ThreatStats> {
    const params = timeRange ? `?time_range=${timeRange}` : '';
    return apiRequest<ThreatStats>({
      method: 'GET',
      url: `${BASE_PATH}/stats${params}`,
    });
  },

  /**
   * Get threat timeline data for charts
   */
  async getThreatTimeline(timeRange: string): Promise<{ hour: string; count: number; severity: string }[]> {
    return apiRequest<{ hour: string; count: number; severity: string }[]>({
      method: 'GET',
      url: `${BASE_PATH}/timeline?time_range=${timeRange}`,
    });
  },

  /**
   * Get geographic distribution of threats
   */
  async getThreatGeoData(): Promise<{ latitude: number; longitude: number; count: number; severity: string }[]> {
    return apiRequest<{ latitude: number; longitude: number; count: number; severity: string }[]>({
      method: 'GET',
      url: `${BASE_PATH}/geo`,
    });
  },

  /**
   * Create incident from threat
   */
  async createIncidentFromThreat(threatId: string): Promise<{ incidentId: string }> {
    return apiRequest<{ incidentId: string }>({
      method: 'POST',
      url: `${BASE_PATH}/${threatId}/create-incident`,
    });
  },
};
