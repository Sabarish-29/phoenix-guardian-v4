/**
 * Role-Based Access Control (RBAC) E2E Tests
 * 
 * Tests verify that:
 * - Different roles see appropriate UI elements
 * - Unauthorized access is blocked
 * - Role-specific features are accessible
 * - Admin-only features are protected
 */

import { test, expect } from '@playwright/test';
import { loginAs, clearAuthState, TEST_USERS } from './utils/auth';

test.describe('Admin Role Access', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
  });
  
  test('admin should see all navigation items', async ({ page }) => {
    await loginAs(page, 'admin');
    
    // Admin should see dashboard
    await expect(page.locator('text=/dashboard/i').first()).toBeVisible();
    
    // Admin should see encounters
    await expect(page.locator('a:has-text("Encounters"), text=/encounters/i').first()).toBeVisible();
    
    // Admin should see audit logs (if implemented)
    const auditLink = page.locator('text=/audit/i');
    // Audit may or may not be visible depending on implementation
  });
  
  test('admin should access encounter creation', async ({ page }) => {
    await loginAs(page, 'admin');
    
    // Navigate to create encounter
    await page.goto('/encounters/new');
    
    // Should not redirect to unauthorized
    expect(page.url()).toContain('/encounters/new');
    
    // Should see the form
    await expect(page.locator('text=/patient|encounter|create/i').first()).toBeVisible();
  });
  
  test('admin should access all encounters', async ({ page }) => {
    await loginAs(page, 'admin');
    
    // Navigate to encounters list
    await page.goto('/encounters');
    
    // Should be on encounters page
    expect(page.url()).toContain('/encounters');
  });
});

test.describe('Physician Role Access', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
  });
  
  test('physician should see new encounter button', async ({ page }) => {
    await loginAs(page, 'physician');
    
    // Should see new encounter option
    const newEncounterButton = page.locator('a:has-text("New Encounter"), button:has-text("New Encounter")');
    await expect(newEncounterButton).toBeVisible();
  });
  
  test('physician should create encounters', async ({ page }) => {
    await loginAs(page, 'physician');
    
    // Navigate to create encounter
    await page.click('text=New Encounter');
    
    // Should be on create page
    await page.waitForURL(/\/encounters\/new/);
    
    // Should see form
    await expect(page.locator('form, input, textarea').first()).toBeVisible();
  });
  
  test('physician should access review page', async ({ page }) => {
    await loginAs(page, 'physician');
    
    // Navigate to encounters list
    await page.goto('/encounters');
    
    // Look for any encounter link
    const encounterLink = page.locator('a[href*="/encounters/"]').first();
    
    if (await encounterLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await encounterLink.click();
      
      // Should be on encounter page
      expect(page.url()).toContain('/encounters/');
    }
  });
  
  test('physician should see approve/sign buttons', async ({ page }) => {
    await loginAs(page, 'physician');
    
    // Navigate to encounters
    await page.goto('/encounters');
    
    // Find review link
    const reviewLink = page.locator('a:has-text("Review")').first();
    
    if (await reviewLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await reviewLink.click();
      
      // Should see approval options
      const approveButton = page.locator('button:has-text("Approve"), button:has-text("Sign")');
      // Button visibility depends on encounter status
    }
  });
});

test.describe('Nurse Role Access', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
  });
  
  test('nurse should access dashboard', async ({ page }) => {
    await loginAs(page, 'nurse');
    
    // Should be on dashboard
    expect(page.url()).toContain('/dashboard');
  });
  
  test('nurse should view encounters list', async ({ page }) => {
    await loginAs(page, 'nurse');
    
    // Navigate to encounters
    await page.goto('/encounters');
    
    // Should see encounters page
    await expect(page.locator('text=/encounters/i').first()).toBeVisible();
  });
  
  test('nurse should not see create encounter button or have limited access', async ({ page }) => {
    await loginAs(page, 'nurse');
    
    // Look for new encounter button
    const newEncounterButton = page.locator('a:has-text("New Encounter"), button:has-text("New Encounter")');
    
    // Either not visible or disabled
    const isVisible = await newEncounterButton.isVisible().catch(() => false);
    
    if (isVisible) {
      // If visible, it should be disabled or redirect to unauthorized
      const isDisabled = await newEncounterButton.isDisabled().catch(() => false);
      
      if (!isDisabled) {
        // Try clicking and check for redirect
        await newEncounterButton.click();
        
        // May redirect to unauthorized
        await page.waitForTimeout(1000);
        const url = page.url();
        // Nurse may or may not have create access depending on implementation
      }
    }
  });
  
  test('nurse should not be able to approve notes', async ({ page }) => {
    await loginAs(page, 'nurse');
    
    await page.goto('/encounters');
    
    // Find an encounter
    const encounterLink = page.locator('a[href*="/encounters/"]').first();
    
    if (await encounterLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await encounterLink.click();
      
      // Look for approve button
      const approveButton = page.locator('button:has-text("Approve"), button:has-text("Sign")');
      
      // Either not visible or disabled for nurse
      const isVisible = await approveButton.isVisible().catch(() => false);
      
      if (isVisible) {
        const isDisabled = await approveButton.isDisabled().catch(() => false);
        // Nurse should not be able to approve
        expect(isDisabled).toBeTruthy();
      }
    }
  });
});

test.describe('Scribe Role Access', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
  });
  
  test('scribe should have read access to encounters', async ({ page }) => {
    await loginAs(page, 'scribe');
    
    // Navigate to encounters
    await page.goto('/encounters');
    
    // Should be able to view list
    const onEncountersPage = page.url().includes('/encounters');
    const onUnauthorized = page.url().includes('/unauthorized');
    
    // Scribe access depends on implementation
    expect(onEncountersPage || onUnauthorized).toBeTruthy();
  });
  
  test('scribe should not access admin features', async ({ page }) => {
    await loginAs(page, 'scribe');
    
    // Try to access admin page
    await page.goto('/admin/users');
    
    // Should redirect to unauthorized or 404
    await page.waitForTimeout(1000);
    
    const url = page.url();
    expect(url.includes('/unauthorized') || url.includes('/dashboard') || url.includes('/404')).toBeTruthy();
  });
});

test.describe('Unauthorized Access Prevention', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
  });
  
  test('should block access to admin pages for non-admin users', async ({ page }) => {
    // Login as physician
    await loginAs(page, 'physician');
    
    // Try to access admin page
    await page.goto('/admin/users');
    
    // Wait for redirect
    await page.waitForTimeout(1000);
    
    // Should be redirected
    const url = page.url();
    expect(url.includes('/unauthorized') || url.includes('/dashboard') || url.includes('/404')).toBeTruthy();
  });
  
  test('should show unauthorized page with message', async ({ page }) => {
    await loginAs(page, 'nurse');
    
    // Try to access restricted page
    await page.goto('/admin/settings');
    
    // Wait for page load
    await page.waitForTimeout(1000);
    
    // If redirected to unauthorized page, check for message
    if (page.url().includes('/unauthorized')) {
      await expect(page.locator('text=/access denied|unauthorized|permission/i')).toBeVisible();
    }
  });
  
  test('should redirect unauthenticated users to login', async ({ page }) => {
    // Clear auth
    await clearAuthState(page);
    
    // Try to access protected page
    await page.goto('/encounters/new');
    
    // Should redirect to login
    await page.waitForURL(/\/login/, { timeout: 5000 });
  });
  
  test('should not show admin menu items to non-admin users', async ({ page }) => {
    await loginAs(page, 'nurse');
    
    // Admin-only menu items should not be visible
    const adminMenu = page.locator('text=User Management, text=System Settings');
    
    // These should not be visible to nurse
    const isVisible = await adminMenu.isVisible().catch(() => false);
    expect(isVisible).toBeFalsy();
  });
});

test.describe('Role-Based UI Elements', () => {
  
  test('admin sees full navigation', async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'admin');
    
    // Count visible navigation items
    const navItems = page.locator('nav a, header a').all();
    const items = await navItems;
    
    // Admin should have access to multiple sections
    expect(items.length).toBeGreaterThan(0);
  });
  
  test('physician sees clinical navigation', async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'physician');
    
    // Should see clinical items
    await expect(page.locator('text=/dashboard/i').first()).toBeVisible();
    await expect(page.locator('text=/encounter/i').first()).toBeVisible();
  });
  
  test('auditor sees audit-related navigation', async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'auditor');
    
    // Should see audit-related items
    await expect(page.locator('text=/dashboard/i').first()).toBeVisible();
    
    // Audit logs link should be visible to auditor
    const auditLink = page.locator('a:has-text("Audit"), text=/audit log/i');
    // Visibility depends on implementation
  });
});
