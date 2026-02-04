import { describe, it, expect, vi, beforeEach } from 'vitest';
import { honeytokensApi } from '../honeytokensApi';
import { apiClient } from '../client';

vi.mock('../client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('honeytokensApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getHoneytokens', () => {
    it('fetches honeytokens list', async () => {
      const mockData = [{ id: '1', name: 'Test Token' }];
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockData });

      const result = await honeytokensApi.getHoneytokens();
      
      expect(apiClient.get).toHaveBeenCalledWith('/honeytokens');
      expect(result).toEqual(mockData);
    });
  });

  describe('createHoneytoken', () => {
    it('creates a new honeytoken', async () => {
      const newToken = { name: 'New Token', type: 'patient_record' };
      const mockResponse = { id: 'ht-1', ...newToken };
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse });

      const result = await honeytokensApi.createHoneytoken(newToken);
      
      expect(apiClient.post).toHaveBeenCalledWith('/honeytokens', newToken);
      expect(result).toEqual(mockResponse);
    });
  });

  describe('getTriggers', () => {
    it('fetches triggers for a honeytoken', async () => {
      const mockTriggers = [{ id: 't1', honeytokenId: 'ht-1' }];
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockTriggers });

      const result = await honeytokensApi.getTriggers('ht-1');
      
      expect(apiClient.get).toHaveBeenCalledWith('/honeytokens/ht-1/triggers');
      expect(result).toEqual(mockTriggers);
    });
  });

  describe('updateHoneytoken', () => {
    it('updates an existing honeytoken', async () => {
      const updates = { status: 'inactive' };
      vi.mocked(apiClient.put).mockResolvedValue({ data: { id: 'ht-1', status: 'inactive' } });

      const result = await honeytokensApi.updateHoneytoken('ht-1', updates);
      
      expect(apiClient.put).toHaveBeenCalledWith('/honeytokens/ht-1', updates);
      expect(result.status).toBe('inactive');
    });
  });

  describe('deleteHoneytoken', () => {
    it('deletes a honeytoken', async () => {
      vi.mocked(apiClient.delete).mockResolvedValue({ data: { success: true } });

      await honeytokensApi.deleteHoneytoken('ht-1');
      
      expect(apiClient.delete).toHaveBeenCalledWith('/honeytokens/ht-1');
    });
  });
});
