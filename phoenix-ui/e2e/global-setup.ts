/**
 * Global setup for E2E tests.
 * 
 * Runs once before all tests to:
 * - Verify backend is running
 * - Seed test data if needed
 * - Configure global test state
 */

import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use?.baseURL || 'http://localhost:3000';
  const apiURL = process.env.API_BASE_URL || 'http://localhost:8000';
  
  console.log('🚀 Running global setup...');
  console.log(`   Frontend URL: ${baseURL}`);
  console.log(`   Backend URL: ${apiURL}`);
  
  // Verify frontend is accessible
  try {
    const response = await fetch(baseURL);
    if (!response.ok) {
      console.warn(`⚠️ Frontend returned status ${response.status}`);
    } else {
      console.log('✅ Frontend is accessible');
    }
  } catch (error) {
    console.error('❌ Frontend is not accessible. Make sure to run "npm start" first.');
    console.error(`   Error: ${error}`);
  }
  
  // Verify backend is accessible
  try {
    const response = await fetch(`${apiURL}/health`);
    if (!response.ok) {
      console.warn(`⚠️ Backend health check returned status ${response.status}`);
    } else {
      console.log('✅ Backend is accessible');
    }
  } catch (error) {
    console.warn('⚠️ Backend health check failed. Some tests may fail.');
    console.warn(`   Error: ${error}`);
    console.warn('   Make sure the FastAPI backend is running on port 8000');
  }
  
  console.log('🎬 Starting E2E tests...\n');
}

export default globalSetup;
