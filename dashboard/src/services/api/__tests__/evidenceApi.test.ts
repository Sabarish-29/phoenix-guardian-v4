import { describe, it, expect, vi, beforeEach } from 'vitest';
import { evidenceApi } from '../evidenceApi';
import { apiClient } from '../client';

vi.mock('../client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('evidenceApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getPackages', () => {
    it('fetches evidence packages list', async () => {
      const mockData = [{ id: 'pkg-1', incidentTitle: 'Test' }];
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockData });

      const result = await evidenceApi.getPackages();
      
      expect(apiClient.get).toHaveBeenCalledWith('/evidence/packages');
      expect(result).toEqual(mockData);
    });
  });

  describe('getPackage', () => {
    it('fetches single package', async () => {
      const mockData = { id: 'pkg-1', incidentTitle: 'Test' };
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockData });

      const result = await evidenceApi.getPackage('pkg-1');
      
      expect(apiClient.get).toHaveBeenCalledWith('/evidence/packages/pkg-1');
      expect(result).toEqual(mockData);
    });
  });

  describe('createPackage', () => {
    it('creates a new evidence package', async () => {
      const newPackage = { incidentId: 'inc-1', items: [] };
      vi.mocked(apiClient.post).mockResolvedValue({ data: { id: 'pkg-1', ...newPackage } });

      const result = await evidenceApi.createPackage(newPackage);
      
      expect(apiClient.post).toHaveBeenCalledWith('/evidence/packages', newPackage);
    });
  });

  describe('verifyIntegrity', () => {
    it('verifies package integrity', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: { verified: true } });

      const result = await evidenceApi.verifyIntegrity('pkg-1');
      
      expect(apiClient.post).toHaveBeenCalledWith('/evidence/packages/pkg-1/verify');
      expect(result.verified).toBe(true);
    });
  });

  describe('downloadPackage', () => {
    it('initiates package download', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: new Blob() });

      await evidenceApi.downloadPackage('pkg-1');
      
      expect(apiClient.get).toHaveBeenCalledWith('/evidence/packages/pkg-1/download', {
        responseType: 'blob',
      });
    });
  });
});
