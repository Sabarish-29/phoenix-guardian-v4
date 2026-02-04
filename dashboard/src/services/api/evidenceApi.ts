import apiClient, { apiRequest } from './client';
import type { EvidencePackage, EvidenceItem, EvidenceGenerationRequest } from '../../types/evidence';

const BASE_PATH = '/dashboard/evidence';

export const evidenceApi = {
  /**
   * Get evidence packages, optionally filtered by incident
   */
  async getPackages(incidentId?: string): Promise<EvidencePackage[]> {
    const params = incidentId ? `?incident_id=${incidentId}` : '';
    return apiRequest<EvidencePackage[]>({
      method: 'GET',
      url: `${BASE_PATH}${params}`,
    });
  },

  /**
   * Get evidence package by ID
   */
  async getPackageById(packageId: string): Promise<EvidencePackage> {
    return apiRequest<EvidencePackage>({
      method: 'GET',
      url: `${BASE_PATH}/${packageId}`,
    });
  },

  /**
   * Generate a new evidence package for an incident
   */
  async generatePackage(incidentId: string, options?: Partial<EvidenceGenerationRequest>): Promise<EvidencePackage> {
    return apiRequest<EvidencePackage>({
      method: 'POST',
      url: BASE_PATH,
      data: {
        incident_id: incidentId,
        ...options,
      },
    });
  },

  /**
   * Download evidence package with progress tracking
   */
  async downloadPackage(
    packageId: string,
    onProgress?: (progress: number) => void
  ): Promise<Blob> {
    const response = await apiClient.get(`${BASE_PATH}/${packageId}/download`, {
      responseType: 'blob',
      onDownloadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    });
    return response.data;
  },

  /**
   * Verify evidence package integrity
   */
  async verifyIntegrity(packageId: string): Promise<{ valid: boolean; details: string }> {
    return apiRequest<{ valid: boolean; details: string }>({
      method: 'POST',
      url: `${BASE_PATH}/${packageId}/verify`,
    });
  },

  /**
   * Get chain of custody for an evidence item
   */
  async getChainOfCustody(packageId: string, itemId: string): Promise<EvidenceItem['chainOfCustody']> {
    return apiRequest<EvidenceItem['chainOfCustody']>({
      method: 'GET',
      url: `${BASE_PATH}/${packageId}/items/${itemId}/custody`,
    });
  },

  /**
   * Add note to chain of custody
   */
  async addCustodyNote(packageId: string, itemId: string, note: string): Promise<void> {
    return apiRequest<void>({
      method: 'POST',
      url: `${BASE_PATH}/${packageId}/items/${itemId}/custody`,
      data: { note },
    });
  },
};
