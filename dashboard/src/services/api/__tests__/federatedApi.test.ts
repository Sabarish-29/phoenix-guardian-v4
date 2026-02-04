import { describe, it, expect, vi, beforeEach } from 'vitest';
import { federatedApi } from '../federatedApi';
import { apiClient } from '../client';

vi.mock('../client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

describe('federatedApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getModelStatus', () => {
    it('fetches federated model status', async () => {
      const mockStatus = { modelVersion: '1.0', lastUpdate: '2024-01-15' };
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockStatus });

      const result = await federatedApi.getModelStatus();
      
      expect(apiClient.get).toHaveBeenCalledWith('/federated/model/status');
      expect(result).toEqual(mockStatus);
    });
  });

  describe('getSignatures', () => {
    it('fetches threat signatures', async () => {
      const mockSignatures = [{ id: 'sig-1', attackType: 'ransomware' }];
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockSignatures });

      const result = await federatedApi.getSignatures();
      
      expect(apiClient.get).toHaveBeenCalledWith('/federated/signatures');
      expect(result).toEqual(mockSignatures);
    });
  });

  describe('getPrivacyMetrics', () => {
    it('fetches privacy budget metrics', async () => {
      const mockMetrics = { epsilon: 1.0, budgetUsed: 0.5 };
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockMetrics });

      const result = await federatedApi.getPrivacyMetrics();
      
      expect(apiClient.get).toHaveBeenCalledWith('/federated/privacy/metrics');
      expect(result).toEqual(mockMetrics);
    });
  });

  describe('getContributions', () => {
    it('fetches hospital contributions', async () => {
      const mockData = [{ hospitalId: 'h-1', contributionCount: 100 }];
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockData });

      const result = await federatedApi.getContributions();
      
      expect(apiClient.get).toHaveBeenCalledWith('/federated/contributions');
      expect(result).toEqual(mockData);
    });
  });

  describe('submitContribution', () => {
    it('submits a new contribution', async () => {
      const contribution = { signatures: [], privacyLevel: 'high' };
      vi.mocked(apiClient.post).mockResolvedValue({ data: { success: true } });

      await federatedApi.submitContribution(contribution);
      
      expect(apiClient.post).toHaveBeenCalledWith('/federated/contributions', contribution);
    });
  });
});
