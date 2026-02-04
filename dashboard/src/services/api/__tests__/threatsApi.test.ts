import { describe, it, expect, vi, beforeEach } from 'vitest';
import { threatsApi } from '../threatsApi';
import { apiClient } from '../client';

vi.mock('../client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('threatsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getThreats', () => {
    it('fetches threats list', async () => {
      const mockThreats = [{ id: '1', title: 'Test Threat' }];
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockThreats });

      const result = await threatsApi.getThreats();
      
      expect(apiClient.get).toHaveBeenCalledWith('/threats');
      expect(result).toEqual(mockThreats);
    });

    it('passes filter parameters', async () => {
      const mockThreats = [];
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockThreats });

      await threatsApi.getThreats({ severity: ['critical'], status: ['active'] });
      
      expect(apiClient.get).toHaveBeenCalledWith('/threats', {
        params: { severity: ['critical'], status: ['active'] },
      });
    });
  });

  describe('getThreat', () => {
    it('fetches single threat by id', async () => {
      const mockThreat = { id: 'threat-1', title: 'Test Threat' };
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockThreat });

      const result = await threatsApi.getThreat('threat-1');
      
      expect(apiClient.get).toHaveBeenCalledWith('/threats/threat-1');
      expect(result).toEqual(mockThreat);
    });
  });

  describe('acknowledgeThreat', () => {
    it('acknowledges a threat', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: { success: true } });

      await threatsApi.acknowledgeThreat('threat-1');
      
      expect(apiClient.post).toHaveBeenCalledWith('/threats/threat-1/acknowledge');
    });
  });

  describe('updateThreatStatus', () => {
    it('updates threat status', async () => {
      vi.mocked(apiClient.put).mockResolvedValue({ data: { id: 'threat-1', status: 'mitigated' } });

      const result = await threatsApi.updateThreatStatus('threat-1', 'mitigated');
      
      expect(apiClient.put).toHaveBeenCalledWith('/threats/threat-1/status', { status: 'mitigated' });
      expect(result.status).toBe('mitigated');
    });
  });
});
