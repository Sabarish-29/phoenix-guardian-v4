import { apiRequest } from './client';
import type { Honeytoken, HoneytokenTrigger, HoneytokenStats } from '../../types/honeytoken';

const BASE_PATH = '/dashboard/honeytokens';

export const honeytokensApi = {
  /**
   * Get all honeytokens
   */
  async getHoneytokens(): Promise<Honeytoken[]> {
    return apiRequest<Honeytoken[]>({
      method: 'GET',
      url: BASE_PATH,
    });
  },

  /**
   * Get honeytoken by ID
   */
  async getHoneytokenById(honeytokenId: string): Promise<Honeytoken> {
    return apiRequest<Honeytoken>({
      method: 'GET',
      url: `${BASE_PATH}/${honeytokenId}`,
    });
  },

  /**
   * Create a new honeytoken
   */
  async createHoneytoken(data: Partial<Honeytoken>): Promise<Honeytoken> {
    return apiRequest<Honeytoken>({
      method: 'POST',
      url: BASE_PATH,
      data,
    });
  },

  /**
   * Deactivate a honeytoken
   */
  async deactivateHoneytoken(honeytokenId: string): Promise<void> {
    return apiRequest<void>({
      method: 'POST',
      url: `${BASE_PATH}/${honeytokenId}/deactivate`,
    });
  },

  /**
   * Get trigger events for a honeytoken or all triggers
   */
  async getTriggers(honeytokenId?: string): Promise<HoneytokenTrigger[]> {
    const url = honeytokenId
      ? `${BASE_PATH}/${honeytokenId}/triggers`
      : `${BASE_PATH}/triggers`;
    return apiRequest<HoneytokenTrigger[]>({
      method: 'GET',
      url,
    });
  },

  /**
   * Get honeytoken statistics
   */
  async getStats(): Promise<HoneytokenStats> {
    return apiRequest<HoneytokenStats>({
      method: 'GET',
      url: `${BASE_PATH}/stats`,
    });
  },

  /**
   * Rotate a honeytoken (create new, deactivate old)
   */
  async rotateHoneytoken(honeytokenId: string): Promise<Honeytoken> {
    return apiRequest<Honeytoken>({
      method: 'POST',
      url: `${BASE_PATH}/${honeytokenId}/rotate`,
    });
  },
};
