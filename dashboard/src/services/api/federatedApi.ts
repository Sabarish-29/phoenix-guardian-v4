import { apiRequest } from './client';
import type { FederatedModel, ThreatSignature, PrivacyMetrics, HospitalContribution } from '../../types/federated';

const BASE_PATH = '/dashboard/federated';

export const federatedApi = {
  /**
   * Get global federated model info
   */
  async getGlobalModel(): Promise<FederatedModel> {
    return apiRequest<FederatedModel>({
      method: 'GET',
      url: `${BASE_PATH}/model`,
    });
  },

  /**
   * Get threat signatures from federated network
   */
  async getSignatures(params?: { limit?: number; attackType?: string }): Promise<ThreatSignature[]> {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', String(params.limit));
    if (params?.attackType) searchParams.append('attack_type', params.attackType);
    
    const queryString = searchParams.toString();
    return apiRequest<ThreatSignature[]>({
      method: 'GET',
      url: `${BASE_PATH}/signatures${queryString ? `?${queryString}` : ''}`,
    });
  },

  /**
   * Get privacy metrics for the organization
   */
  async getPrivacyMetrics(): Promise<PrivacyMetrics> {
    return apiRequest<PrivacyMetrics>({
      method: 'GET',
      url: `${BASE_PATH}/privacy`,
    });
  },

  /**
   * Get hospital contributions to federated network
   */
  async getContributions(): Promise<HospitalContribution[]> {
    return apiRequest<HospitalContribution[]>({
      method: 'GET',
      url: `${BASE_PATH}/contributions`,
    });
  },

  /**
   * Trigger model sync
   */
  async triggerSync(): Promise<FederatedModel> {
    return apiRequest<FederatedModel>({
      method: 'POST',
      url: `${BASE_PATH}/sync`,
    });
  },

  /**
   * Get signature effectiveness stats
   */
  async getSignatureEffectiveness(): Promise<{ signatureId: string; detections: number; falsePositives: number }[]> {
    return apiRequest<{ signatureId: string; detections: number; falsePositives: number }[]>({
      method: 'GET',
      url: `${BASE_PATH}/signatures/effectiveness`,
    });
  },

  /**
   * Contribute local threat signature
   */
  async contributeSignature(signatureData: Partial<ThreatSignature>): Promise<{ success: boolean; signatureId: string }> {
    return apiRequest<{ success: boolean; signatureId: string }>({
      method: 'POST',
      url: `${BASE_PATH}/signatures/contribute`,
      data: signatureData,
    });
  },
};
