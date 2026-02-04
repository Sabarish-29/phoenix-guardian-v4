/**
 * Playwright E2E Test Configuration
 * 
 * Configuration for end-to-end testing of the Phoenix Guardian application.
 * Tests cover authentication, encounter workflows, RBAC, security, and performance.
 */

import { defineConfig, devices } from '@playwright/test';

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// import dotenv from 'dotenv';
// dotenv.config({ path: '.env.test' });

export default defineConfig({
  // Directory containing test files
  testDir: './e2e',
  
  // Maximum time one test can run for (30 seconds)
  timeout: 30 * 1000,
  
  // Maximum time to wait for expect() assertions
  expect: {
    timeout: 5000,
  },
  
  // Run tests in files in parallel
  fullyParallel: true,
  
  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,
  
  // Retry on CI only
  retries: process.env.CI ? 2 : 0,
  
  // Opt out of parallel tests on CI
  workers: process.env.CI ? 1 : undefined,
  
  // Reporter to use
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'playwright-report/test-results.json' }],
    ['list'],
  ],
  
  // Shared settings for all the projects below
  use: {
    // Base URL to use in actions like `await page.goto('/')`
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    
    // API base URL for backend calls
    extraHTTPHeaders: {
      'Accept': 'application/json',
    },
    
    // Collect trace when retrying the failed test
    trace: 'on-first-retry',
    
    // Screenshot on failure
    screenshot: 'only-on-failure',
    
    // Record video on failure
    video: 'on-first-retry',
    
    // Browser viewport
    viewport: { width: 1280, height: 720 },
    
    // Emulate user actions at realistic speed
    actionTimeout: 10000,
    navigationTimeout: 15000,
  },
  
  // Configure projects for major browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    // Mobile viewports for responsive testing
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },
  ],
  
  // Run your local dev server before starting the tests
  webServer: [
    // Frontend development server
    {
      command: 'npm start',
      url: 'http://localhost:3000',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
      cwd: '.',
    },
    // Backend API server (optional - assumes already running in CI)
    // {
    //   command: 'cd .. && python -m uvicorn phoenix_guardian.api.main:app --host 0.0.0.0 --port 8000',
    //   url: 'http://localhost:8000/health',
    //   reuseExistingServer: !process.env.CI,
    //   timeout: 60 * 1000,
    // },
  ],
  
  // Global setup/teardown
  // globalSetup: require.resolve('./e2e/global-setup.ts'),
  // globalTeardown: require.resolve('./e2e/global-teardown.ts'),
  
  // Output folder for test artifacts
  outputDir: 'test-results/',
  
  // Global setup/teardown
  globalSetup: require.resolve('./e2e/global-setup.ts'),
  globalTeardown: require.resolve('./e2e/global-teardown.ts'),
});
