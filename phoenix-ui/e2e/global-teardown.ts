/**
 * Global teardown for E2E tests.
 * 
 * Runs once after all tests to:
 * - Clean up test data
 * - Generate reports
 * - Log summary
 */

import { FullConfig } from '@playwright/test';

async function globalTeardown(config: FullConfig) {
  console.log('\n🏁 E2E tests completed!');
  console.log('📊 Run "npm run test:e2e:report" to view the HTML report');
}

export default globalTeardown;
