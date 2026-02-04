import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import { apiClient } from '../client';

vi.mock('axios');

describe('apiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('creates axios instance with correct base URL', () => {
    expect(apiClient.defaults.baseURL).toBeDefined();
  });

  it('has correct timeout configuration', () => {
    expect(apiClient.defaults.timeout).toBe(30000);
  });

  it('includes content-type header', () => {
    expect(apiClient.defaults.headers['Content-Type']).toBe('application/json');
  });
});
