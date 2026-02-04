/**
 * API utilities for E2E tests.
 * 
 * Provides helper functions for:
 * - Waiting for API calls
 * - Mocking API responses
 * - Intercepting requests
 */

import { Page, Route, Request, Response } from '@playwright/test';

/**
 * Backend API base URL
 */
export const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

/**
 * Wait for an API call to complete.
 * 
 * @param page - Playwright page object
 * @param urlPattern - URL pattern to match (string or regex)
 * @param method - HTTP method to match
 * @returns The response object
 */
export async function waitForAPI(
  page: Page,
  urlPattern: string | RegExp,
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' = 'GET'
): Promise<Response> {
  return await page.waitForResponse(
    (response) => {
      const url = response.url();
      const matches = typeof urlPattern === 'string'
        ? url.includes(urlPattern)
        : urlPattern.test(url);
      
      return matches && response.request().method() === method;
    },
    { timeout: 15000 }
  );
}

/**
 * Wait for multiple API calls to complete.
 * 
 * @param page - Playwright page object
 * @param calls - Array of [urlPattern, method] tuples
 * @returns Array of response objects
 */
export async function waitForMultipleAPIs(
  page: Page,
  calls: Array<[string | RegExp, 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE']>
): Promise<Response[]> {
  const promises = calls.map(([urlPattern, method]) => 
    waitForAPI(page, urlPattern, method)
  );
  return await Promise.all(promises);
}

/**
 * Mock an API endpoint with a custom response.
 * 
 * @param page - Playwright page object
 * @param urlPattern - URL pattern to intercept
 * @param responseBody - Response body to return
 * @param status - HTTP status code
 * @param method - HTTP method to match (optional)
 */
export async function mockAPI(
  page: Page,
  urlPattern: string | RegExp,
  responseBody: unknown,
  status: number = 200,
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
): Promise<void> {
  await page.route(urlPattern, async (route: Route) => {
    const request = route.request();
    
    // Check method if specified
    if (method && request.method() !== method) {
      await route.continue();
      return;
    }
    
    await route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(responseBody),
    });
  });
}

/**
 * Mock an API error response.
 * 
 * @param page - Playwright page object
 * @param urlPattern - URL pattern to intercept
 * @param errorMessage - Error message
 * @param status - HTTP status code (default 400)
 */
export async function mockAPIError(
  page: Page,
  urlPattern: string | RegExp,
  errorMessage: string,
  status: number = 400
): Promise<void> {
  await mockAPI(
    page,
    urlPattern,
    { detail: errorMessage },
    status
  );
}

/**
 * Intercept and log API requests.
 * Useful for debugging.
 * 
 * @param page - Playwright page object
 * @param urlPattern - URL pattern to intercept (optional, matches all if not provided)
 */
export async function logAPIRequests(
  page: Page,
  urlPattern?: string | RegExp
): Promise<void> {
  page.on('request', (request: Request) => {
    const url = request.url();
    
    if (urlPattern) {
      const matches = typeof urlPattern === 'string'
        ? url.includes(urlPattern)
        : urlPattern.test(url);
      
      if (!matches) return;
    }
    
    if (url.includes('/api') || url.includes(':8000')) {
      console.log(`[API Request] ${request.method()} ${url}`);
    }
  });
  
  page.on('response', (response: Response) => {
    const url = response.url();
    
    if (urlPattern) {
      const matches = typeof urlPattern === 'string'
        ? url.includes(urlPattern)
        : urlPattern.test(url);
      
      if (!matches) return;
    }
    
    if (url.includes('/api') || url.includes(':8000')) {
      console.log(`[API Response] ${response.status()} ${url}`);
    }
  });
}

/**
 * Create an API request counter.
 * 
 * @param page - Playwright page object
 * @param urlPattern - URL pattern to count
 * @returns Object with count getter and reset method
 */
export function createAPICounter(
  page: Page,
  urlPattern: string | RegExp
): { getCount: () => number; reset: () => void } {
  let count = 0;
  
  page.on('request', (request: Request) => {
    const url = request.url();
    const matches = typeof urlPattern === 'string'
      ? url.includes(urlPattern)
      : urlPattern.test(url);
    
    if (matches) {
      count++;
    }
  });
  
  return {
    getCount: () => count,
    reset: () => { count = 0; },
  };
}

/**
 * Delay API response for testing loading states.
 * 
 * @param page - Playwright page object
 * @param urlPattern - URL pattern to delay
 * @param delayMs - Delay in milliseconds
 */
export async function delayAPI(
  page: Page,
  urlPattern: string | RegExp,
  delayMs: number
): Promise<void> {
  await page.route(urlPattern, async (route: Route) => {
    await new Promise(resolve => setTimeout(resolve, delayMs));
    await route.continue();
  });
}

/**
 * Make a direct API call (bypassing the UI).
 * Useful for test setup.
 * 
 * @param page - Playwright page object
 * @param endpoint - API endpoint path
 * @param options - Fetch options
 * @returns Response data
 */
export async function directAPICall<T>(
  page: Page,
  endpoint: string,
  options: {
    method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    body?: unknown;
    token?: string;
  } = {}
): Promise<T> {
  const { method = 'GET', body, token } = options;
  
  return await page.evaluate(
    async ({ baseUrl, endpoint, method, body, token }) => {
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      } else {
        // Try to get token from localStorage
        const authData = localStorage.getItem('phoenix-auth-storage');
        if (authData) {
          const parsed = JSON.parse(authData);
          if (parsed.state?.accessToken) {
            headers['Authorization'] = `Bearer ${parsed.state.accessToken}`;
          }
        }
      }
      
      const response = await fetch(`${baseUrl}${endpoint}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });
      
      return await response.json();
    },
    { baseUrl: API_BASE_URL, endpoint, method, body, token }
  );
}

/**
 * Wait for network to be idle (no pending requests).
 * 
 * @param page - Playwright page object
 * @param timeout - Maximum time to wait
 */
export async function waitForNetworkIdle(
  page: Page,
  timeout: number = 5000
): Promise<void> {
  await page.waitForLoadState('networkidle', { timeout });
}
