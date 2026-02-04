/**
 * Authentication utilities for E2E tests.
 * 
 * Provides helper functions for:
 * - Logging in/out as different user types
 * - Managing auth state
 * - Token manipulation for testing
 */

import { Page, expect } from '@playwright/test';

/**
 * Test user interface
 */
export interface TestUser {
  email: string;
  password: string;
  role: 'admin' | 'physician' | 'nurse' | 'scribe' | 'auditor' | 'readonly';
  firstName: string;
  lastName: string;
}

/**
 * Test users for different roles.
 * These should match users seeded in the test database.
 */
export const TEST_USERS: Record<string, TestUser> = {
  admin: {
    email: 'admin@phoenix.local',
    password: 'Admin123!',
    role: 'admin',
    firstName: 'System',
    lastName: 'Admin',
  },
  physician: {
    email: 'dr.smith@phoenix.local',
    password: 'Doctor123!',
    role: 'physician',
    firstName: 'John',
    lastName: 'Smith',
  },
  nurse: {
    email: 'nurse.jones@phoenix.local',
    password: 'Nurse123!',
    role: 'nurse',
    firstName: 'Sarah',
    lastName: 'Jones',
  },
  scribe: {
    email: 'scribe@phoenix.local',
    password: 'Scribe123!',
    role: 'scribe',
    firstName: 'Mike',
    lastName: 'Scribe',
  },
  auditor: {
    email: 'auditor@phoenix.local',
    password: 'Auditor123!',
    role: 'auditor',
    firstName: 'Jane',
    lastName: 'Auditor',
  },
};

/**
 * Login as a specific test user.
 * 
 * @param page - Playwright page object
 * @param userType - Type of user to login as (admin, physician, nurse, etc.)
 */
export async function loginAs(page: Page, userType: keyof typeof TEST_USERS): Promise<void> {
  const user = TEST_USERS[userType];
  
  if (!user) {
    throw new Error(`Unknown user type: ${userType}`);
  }
  
  // Navigate to login page
  await page.goto('/login');
  
  // Wait for login form to be visible
  await page.waitForSelector('input[type="email"], input[name="email"]');
  
  // Fill in credentials
  await page.fill('input[type="email"], input[name="email"]', user.email);
  await page.fill('input[type="password"]', user.password);
  
  // Submit form
  await page.click('button[type="submit"]');
  
  // Wait for navigation to dashboard
  await page.waitForURL(/\/dashboard/, { timeout: 10000 });
  
  // Verify we're logged in by checking for user name in header
  await expect(page.locator(`text=${user.firstName}`)).toBeVisible({ timeout: 5000 });
}

/**
 * Logout current user.
 * 
 * @param page - Playwright page object
 */
export async function logout(page: Page): Promise<void> {
  // Look for logout button (could be icon or text)
  const logoutButton = page.locator('button[title="Sign out"], button:has-text("Logout"), button:has-text("Sign out")');
  
  if (await logoutButton.isVisible()) {
    await logoutButton.click();
  } else {
    // Try clicking user menu first
    const userMenu = page.locator('[aria-label="User menu"], button:has-text("Account")');
    if (await userMenu.isVisible()) {
      await userMenu.click();
      await page.click('text=Logout');
    }
  }
  
  // Wait for redirect to login
  await page.waitForURL(/\/login/, { timeout: 5000 });
}

/**
 * Get stored auth tokens from localStorage.
 * 
 * @param page - Playwright page object
 * @returns Auth state object or null
 */
export async function getAuthTokens(page: Page): Promise<{
  accessToken: string | null;
  refreshToken: string | null;
  user: TestUser | null;
} | null> {
  return await page.evaluate(() => {
    const authData = localStorage.getItem('phoenix-auth-storage');
    if (!authData) return null;
    
    try {
      const parsed = JSON.parse(authData);
      return {
        accessToken: parsed.state?.accessToken || null,
        refreshToken: parsed.state?.refreshToken || null,
        user: parsed.state?.user || null,
      };
    } catch {
      return null;
    }
  });
}

/**
 * Clear auth state from localStorage.
 * 
 * @param page - Playwright page object
 */
export async function clearAuthState(page: Page): Promise<void> {
  await page.evaluate(() => {
    localStorage.removeItem('phoenix-auth-storage');
    sessionStorage.clear();
  });
}

/**
 * Set a custom access token (for testing token expiry).
 * 
 * @param page - Playwright page object
 * @param token - Custom token to set
 */
export async function setAccessToken(page: Page, token: string): Promise<void> {
  await page.evaluate((newToken) => {
    const authData = localStorage.getItem('phoenix-auth-storage');
    if (authData) {
      const parsed = JSON.parse(authData);
      parsed.state.accessToken = newToken;
      localStorage.setItem('phoenix-auth-storage', JSON.stringify(parsed));
    }
  }, token);
}

/**
 * Check if user is currently authenticated.
 * 
 * @param page - Playwright page object
 * @returns True if authenticated
 */
export async function isAuthenticated(page: Page): Promise<boolean> {
  const tokens = await getAuthTokens(page);
  return !!tokens?.accessToken;
}

/**
 * Wait for auth state to be loaded from localStorage.
 * Useful after page reload.
 * 
 * @param page - Playwright page object
 */
export async function waitForAuthState(page: Page): Promise<void> {
  await page.waitForFunction(() => {
    const authData = localStorage.getItem('phoenix-auth-storage');
    if (!authData) return true; // No auth state is valid (logged out)
    
    try {
      const parsed = JSON.parse(authData);
      return parsed.state !== undefined;
    } catch {
      return false;
    }
  }, { timeout: 5000 });
}

/**
 * Get the current user from auth state.
 * 
 * @param page - Playwright page object
 * @returns Current user or null
 */
export async function getCurrentUser(page: Page): Promise<TestUser | null> {
  const auth = await getAuthTokens(page);
  return auth?.user || null;
}
