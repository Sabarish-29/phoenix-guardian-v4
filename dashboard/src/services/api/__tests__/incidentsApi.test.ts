import { describe, it, expect, vi, beforeEach } from 'vitest';
import { incidentsApi } from '../incidentsApi';
import { apiClient } from '../client';

vi.mock('../client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('incidentsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getIncidents', () => {
    it('fetches incidents list', async () => {
      const mockData = [{ id: 'inc-1', title: 'Test Incident' }];
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockData });

      const result = await incidentsApi.getIncidents();
      
      expect(apiClient.get).toHaveBeenCalledWith('/incidents');
      expect(result).toEqual(mockData);
    });

    it('passes status filter', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: [] });

      await incidentsApi.getIncidents({ status: ['open', 'investigating'] });
      
      expect(apiClient.get).toHaveBeenCalledWith('/incidents', {
        params: { status: ['open', 'investigating'] },
      });
    });
  });

  describe('getIncident', () => {
    it('fetches single incident', async () => {
      const mockData = { id: 'inc-1', title: 'Test' };
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockData });

      const result = await incidentsApi.getIncident('inc-1');
      
      expect(apiClient.get).toHaveBeenCalledWith('/incidents/inc-1');
    });
  });

  describe('createIncident', () => {
    it('creates a new incident', async () => {
      const newIncident = { title: 'New Incident', priority: 'P1' };
      vi.mocked(apiClient.post).mockResolvedValue({ data: { id: 'inc-1', ...newIncident } });

      const result = await incidentsApi.createIncident(newIncident);
      
      expect(apiClient.post).toHaveBeenCalledWith('/incidents', newIncident);
    });
  });

  describe('updateIncidentStatus', () => {
    it('updates incident status', async () => {
      vi.mocked(apiClient.put).mockResolvedValue({ data: { id: 'inc-1', status: 'contained' } });

      const result = await incidentsApi.updateIncidentStatus('inc-1', 'contained');
      
      expect(apiClient.put).toHaveBeenCalledWith('/incidents/inc-1/status', { status: 'contained' });
    });
  });

  describe('assignIncident', () => {
    it('assigns incident to user', async () => {
      vi.mocked(apiClient.put).mockResolvedValue({ data: { id: 'inc-1', assignee: { id: 'user-1' } } });

      const result = await incidentsApi.assignIncident('inc-1', 'user-1');
      
      expect(apiClient.put).toHaveBeenCalledWith('/incidents/inc-1/assign', { userId: 'user-1' });
    });
  });
});
