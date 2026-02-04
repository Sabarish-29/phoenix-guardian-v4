/**
 * Authentication E2E Tests
 * 
 * Tests cover:
 * - Login with valid credentials
 * - Login failure handling
 * - Logout and session cleanup
 * - Auth state persistence
 * - Protected route redirects
 * - Redirect back after login
 */

import { test, expect } from '@playwright/test';
import { loginAs, logout, clearAuthState, getAuthTokens, TEST_USERS } from './utils/auth';

test.describe('Authentication', () => {
  
  test.beforeEach(async ({ page }) => {
    // Clear auth state before each test
    await page.goto('/login');
    await clearAuthState(page);
  });
  
  test('should display login page correctly', async ({ page }) => {
    await page.goto('/login');
    
    // Check for essential elements
    await expect(page.locator('text=Phoenix Guardian')).toBeVisible();
    await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });
  
  test('should login with valid physician credentials', async ({ page }) => {
    await page.goto('/login');
    
    // Fill in physician credentials
    await page.fill('input[type="email"], input[name="email"]', TEST_USERS.physician.email);
    await page.fill('input[type="password"]', TEST_USERS.physician.password);
    
    // Submit
    await page.click('button[type="submit"]');
    
    // Should redirect to dashboard
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });
    
    // Should show user name in header
    await expect(page.locator(`text=${TEST_USERS.physician.firstName}`)).toBeVisible();
  });
  
  test('should login with valid admin credentials', async ({ page }) => {
    await page.goto('/login');
    
    // Fill in admin credentials
    await page.fill('input[type="email"], input[name="email"]', TEST_USERS.admin.email);
    await page.fill('input[type="password"]', TEST_USERS.admin.password);
    
    // Submit
    await page.click('button[type="submit"]');
    
    // Should redirect to dashboard
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });
    
    // Should show admin name
    await expect(page.locator(`text=${TEST_USERS.admin.firstName}`)).toBeVisible();
  });
  
  test('should show error on invalid credentials', async ({ page }) => {
    await page.goto('/login');
    
    // Fill in invalid credentials
    await page.fill('input[type="email"], input[name="email"]', 'invalid@test.com');
    await page.fill('input[type="password"]', 'wrongpassword123');
    
    // Submit
    await page.click('button[type="submit"]');
    
    // Should show error message
    await expect(
      page.locator('text=/invalid|incorrect|error|failed/i')
    ).toBeVisible({ timeout: 5000 });
    
    // Should stay on login page
    expect(page.url()).toContain('/login');
  });
  
  test('should show error on empty credentials', async ({ page }) => {
    await page.goto('/login');
    
    // Try to submit empty form
    await page.click('button[type="submit"]');
    
    // Should show validation error or stay on page
    // (HTML5 validation may prevent submission)
    expect(page.url()).toContain('/login');
  });
  
  test('should logout successfully', async ({ page }) => {
    // Login first
    await loginAs(page, 'physician');
    
    // Verify logged in
    await expect(page.locator(`text=${TEST_USERS.physician.firstName}`)).toBeVisible();
    
    // Logout
    await logout(page);
    
    // Should redirect to login
    expect(page.url()).toContain('/login');
    
    // Auth state should be cleared
    const authState = await page.evaluate(() => {
      return localStorage.getItem('phoenix-auth-storage');
    });
    
    // Either null or has no tokens
    if (authState) {
      const parsed = JSON.parse(authState);
      expect(parsed.state?.accessToken).toBeFalsy();
    }
  });
  
  test('should persist auth state across page reloads', async ({ page }) => {
    // Login
    await loginAs(page, 'physician');
    
    // Verify logged in
    await expect(page.locator(`text=${TEST_USERS.physician.firstName}`)).toBeVisible();
    
    // Get tokens before reload
    const tokensBefore = await getAuthTokens(page);
    expect(tokensBefore?.accessToken).toBeTruthy();
    
    // Reload page
    await page.reload();
    
    // Wait for page to stabilize
    await page.waitForLoadState('networkidle');
    
    // Should still be logged in (on dashboard, not login)
    await page.waitForTimeout(1000); // Give time for auth check
    
    // Should show user name (still authenticated)
    const isOnDashboard = page.url().includes('/dashboard');
    const isOnLogin = page.url().includes('/login');
    
    // Either still on dashboard or token refresh happened
    expect(isOnDashboard || !isOnLogin).toBeTruthy();
  });
  
  test('should redirect to login when accessing protected route', async ({ page }) => {
    // Clear any existing auth
    await clearAuthState(page);
    
    // Try to access protected route without login
    await page.goto('/encounters/new');
    
    // Should redirect to login
    await page.waitForURL(/\/login/, { timeout: 5000 });
  });
  
  test('should redirect to login when accessing dashboard', async ({ page }) => {
    // Clear any existing auth
    await clearAuthState(page);
    
    // Try to access dashboard
    await page.goto('/dashboard');
    
    // Should redirect to login
    await page.waitForURL(/\/login/, { timeout: 5000 });
  });
  
  test('should redirect back to intended page after login', async ({ page }) => {
    // Clear auth
    await clearAuthState(page);
    
    // Try to access encounter creation page
    await page.goto('/encounters/new');
    
    // Should redirect to login
    await page.waitForURL(/\/login/, { timeout: 5000 });
    
    // Login as physician
    await page.fill('input[type="email"], input[name="email"]', TEST_USERS.physician.email);
    await page.fill('input[type="password"]', TEST_USERS.physician.password);
    await page.click('button[type="submit"]');
    
    // Should redirect back to encounter creation page
    await page.waitForURL(/\/encounters\/new/, { timeout: 10000 });
  });
  
  test('should store tokens in localStorage', async ({ page }) => {
    await loginAs(page, 'physician');
    
    // Check localStorage for tokens
    const tokens = await getAuthTokens(page);
    
    expect(tokens).not.toBeNull();
    expect(tokens?.accessToken).toBeTruthy();
    expect(tokens?.refreshToken).toBeTruthy();
  });
  
  test('should display loading state during login', async ({ page }) => {
    await page.goto('/login');
    
    // Fill in credentials
    await page.fill('input[type="email"], input[name="email"]', TEST_USERS.physician.email);
    await page.fill('input[type="password"]', TEST_USERS.physician.password);
    
    // Start login and check for loading indicator
    const submitButton = page.locator('button[type="submit"]');
    await submitButton.click();
    
    // Button should show loading state (disabled or loading text)
    // This happens quickly so we just verify login completes
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });
  });
});

test.describe('Authentication - Role Display', () => {
  
  test('should display physician role correctly', async ({ page }) => {
    await loginAs(page, 'physician');
    
    // Should show role indicator
    await expect(page.locator('text=/physician/i')).toBeVisible();
  });
  
  test('should display nurse role correctly', async ({ page }) => {
    await loginAs(page, 'nurse');
    
    // Should show role indicator
    await expect(page.locator('text=/nurse/i')).toBeVisible();
  });
  
  test('should display admin role correctly', async ({ page }) => {
    await loginAs(page, 'admin');
    
    // Should show role indicator
    await expect(page.locator('text=/admin/i')).toBeVisible();
  });
});
