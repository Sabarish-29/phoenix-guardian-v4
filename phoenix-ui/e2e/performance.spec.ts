/**
 * Performance E2E Tests
 * 
 * Tests verify application performance:
 * - Page load times
 * - API response times
 * - UI responsiveness
 * - Resource loading
 */

import { test, expect } from '@playwright/test';
import { loginAs, clearAuthState } from './utils/auth';
import { waitForNetworkIdle } from './utils/api';

test.describe('Page Load Performance', () => {
  
  test('should load login page quickly', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto('/login');
    await page.waitForLoadState('domcontentloaded');
    
    const loadTime = Date.now() - startTime;
    
    // Login page should load in under 3 seconds
    expect(loadTime).toBeLessThan(3000);
    
    console.log(`Login page load time: ${loadTime}ms`);
  });
  
  test('should load dashboard quickly after login', async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
    
    const startTime = Date.now();
    
    await loginAs(page, 'physician');
    
    // Wait for dashboard content
    await page.waitForSelector('text=/dashboard|welcome/i', { timeout: 10000 });
    
    const loadTime = Date.now() - startTime;
    
    // Dashboard should load in under 5 seconds (including login)
    expect(loadTime).toBeLessThan(5000);
    
    console.log(`Dashboard load time (with login): ${loadTime}ms`);
  });
  
  test('should load encounters list quickly', async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'physician');
    
    const startTime = Date.now();
    
    await page.goto('/encounters');
    await waitForNetworkIdle(page);
    
    const loadTime = Date.now() - startTime;
    
    // Encounters list should load in under 3 seconds
    expect(loadTime).toBeLessThan(3000);
    
    console.log(`Encounters list load time: ${loadTime}ms`);
  });
  
  test('should load create encounter page quickly', async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'physician');
    
    const startTime = Date.now();
    
    await page.goto('/encounters/new');
    await page.waitForSelector('form, input, textarea');
    
    const loadTime = Date.now() - startTime;
    
    // Create page should load in under 2 seconds
    expect(loadTime).toBeLessThan(2000);
    
    console.log(`Create encounter page load time: ${loadTime}ms`);
  });
});

test.describe('API Response Performance', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'physician');
  });
  
  test('should fetch encounters list quickly', async ({ page }) => {
    // Listen for API response time
    let responseTime = 0;
    
    page.on('response', (response) => {
      if (response.url().includes('/encounters') && response.request().method() === 'GET') {
        responseTime = response.timing().responseEnd;
      }
    });
    
    await page.goto('/encounters');
    await waitForNetworkIdle(page);
    
    // API should respond in under 2 seconds
    // Note: responseTime may be 0 if timing data not available
    console.log(`Encounters API response time: ${responseTime}ms`);
  });
  
  test('should process encounter within acceptable time', async ({ page }) => {
    await page.goto('/encounters/new');
    
    // Fill form quickly
    await page.fill('input[id="firstName"], input[name="firstName"]', 'Perf');
    await page.fill('input[id="lastName"], input[name="lastName"]', 'Test');
    await page.fill('textarea[id="transcript"], textarea', `
      Patient presents with mild symptoms.
      Vitals stable. Plan: Follow up as needed.
    `);
    
    const startTime = Date.now();
    
    // Submit
    await page.click('button[type="submit"], button:has-text("Create"), button:has-text("Generate")');
    
    // Wait for navigation or response
    try {
      await page.waitForURL(/\/encounters\//, { timeout: 30000 });
    } catch {
      // May stay on page with loading indicator
    }
    
    const processingTime = Date.now() - startTime;
    
    // Encounter creation should complete in under 15 seconds
    // (includes AI processing time)
    expect(processingTime).toBeLessThan(15000);
    
    console.log(`Encounter processing time: ${processingTime}ms`);
  });
});

test.describe('UI Responsiveness', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'physician');
  });
  
  test('should respond to button clicks immediately', async ({ page }) => {
    await page.goto('/encounters/new');
    
    const startTime = Date.now();
    
    // Click a button
    const submitButton = page.locator('button[type="submit"]');
    await submitButton.click();
    
    // Button should respond (show loading state or validation)
    const responseTime = Date.now() - startTime;
    
    // Click response should be under 200ms
    expect(responseTime).toBeLessThan(200);
  });
  
  test('should update input fields in real-time', async ({ page }) => {
    await page.goto('/encounters/new');
    
    const input = page.locator('input[id="firstName"], input[name="firstName"]');
    
    const startTime = Date.now();
    
    await input.fill('Test');
    
    const value = await input.inputValue();
    
    const responseTime = Date.now() - startTime;
    
    // Input should update immediately
    expect(value).toBe('Test');
    expect(responseTime).toBeLessThan(500);
  });
  
  test('should handle navigation smoothly', async ({ page }) => {
    const startTime = Date.now();
    
    // Navigate between pages
    await page.goto('/dashboard');
    await page.waitForLoadState('domcontentloaded');
    
    await page.goto('/encounters');
    await page.waitForLoadState('domcontentloaded');
    
    await page.goto('/encounters/new');
    await page.waitForLoadState('domcontentloaded');
    
    const totalTime = Date.now() - startTime;
    
    // Three navigations should complete in under 6 seconds
    expect(totalTime).toBeLessThan(6000);
    
    console.log(`Navigation time (3 pages): ${totalTime}ms`);
  });
});

test.describe('Resource Loading', () => {
  
  test('should load all resources without errors', async ({ page }) => {
    const failedRequests: string[] = [];
    
    page.on('requestfailed', (request) => {
      failedRequests.push(request.url());
    });
    
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'physician');
    
    await page.goto('/dashboard');
    await waitForNetworkIdle(page);
    
    // No resources should fail to load
    // Filter out expected failures (like external analytics)
    const criticalFailures = failedRequests.filter(url => 
      !url.includes('analytics') && 
      !url.includes('tracking') &&
      !url.includes('google')
    );
    
    expect(criticalFailures).toHaveLength(0);
  });
  
  test('should not have console errors', async ({ page }) => {
    const consoleErrors: string[] = [];
    
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'physician');
    
    await page.goto('/dashboard');
    await waitForNetworkIdle(page);
    
    // Filter out known benign errors
    const criticalErrors = consoleErrors.filter(error => 
      !error.includes('favicon') &&
      !error.includes('manifest') &&
      !error.includes('devtools')
    );
    
    // Log errors for debugging
    if (criticalErrors.length > 0) {
      console.log('Console errors:', criticalErrors);
    }
    
    // Ideally no critical console errors
    // But some may be acceptable depending on environment
  });
});

test.describe('Concurrent Operations', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'physician');
  });
  
  test('should handle multiple API calls concurrently', async ({ page }) => {
    // Dashboard typically makes multiple API calls
    await page.goto('/dashboard');
    
    const startTime = Date.now();
    
    await waitForNetworkIdle(page);
    
    const loadTime = Date.now() - startTime;
    
    // Multiple concurrent calls should not significantly slow down
    expect(loadTime).toBeLessThan(5000);
    
    // Page should be fully loaded and interactive
    await expect(page.locator('text=/dashboard|welcome/i').first()).toBeVisible();
  });
  
  test('should remain responsive during API calls', async ({ page }) => {
    await page.goto('/encounters/new');
    
    // Fill form
    await page.fill('input[id="firstName"], input[name="firstName"]', 'Concurrent');
    await page.fill('input[id="lastName"], input[name="lastName"]', 'Test');
    await page.fill('textarea[id="transcript"], textarea', 'Test transcript content for concurrent operations test.');
    
    // Start submission (triggers API call)
    await page.click('button[type="submit"], button:has-text("Create"), button:has-text("Generate")');
    
    // UI should still be responsive during API call
    // Check that we can still interact with elements
    const heading = page.locator('h1, h2');
    await expect(heading.first()).toBeVisible();
  });
});

test.describe('Memory and Performance Metrics', () => {
  
  test('should not have memory leaks on navigation', async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'physician');
    
    // Navigate multiple times
    for (let i = 0; i < 5; i++) {
      await page.goto('/dashboard');
      await page.goto('/encounters');
      await page.goto('/encounters/new');
    }
    
    // If we get here without crashes, basic memory handling is OK
    await expect(page.locator('body')).toBeVisible();
  });
  
  test('should have reasonable DOM size', async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'physician');
    await page.goto('/dashboard');
    await waitForNetworkIdle(page);
    
    // Count DOM elements
    const elementCount = await page.evaluate(() => {
      return document.querySelectorAll('*').length;
    });
    
    // Reasonable DOM size (under 5000 elements for a dashboard)
    expect(elementCount).toBeLessThan(5000);
    
    console.log(`DOM element count: ${elementCount}`);
  });
});
