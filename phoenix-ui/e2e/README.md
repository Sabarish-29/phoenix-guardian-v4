# Phoenix Guardian E2E Tests

End-to-end tests using Playwright for complete user workflow validation.

## Prerequisites

1. **Backend running**: FastAPI server on port 8000
2. **Frontend running**: React dev server on port 3000
3. **Test users seeded**: Run the seed script

## Setup

### 1. Install dependencies

```bash
cd phoenix-ui
npm install
npx playwright install
```

### 2. Seed test users

```bash
cd ..
python scripts/seed_test_users.py
```

### 3. Start the servers

**Terminal 1 - Backend:**
```bash
uvicorn phoenix_guardian.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd phoenix-ui
npm start
```

## Running Tests

### Run all tests
```bash
npm run test:e2e
```

### Run with UI mode (interactive)
```bash
npm run test:e2e:ui
```

### Run in headed mode (see browser)
```bash
npm run test:e2e:headed
```

### Run specific test file
```bash
npx playwright test e2e/auth.spec.ts
```

### Run specific browser
```bash
npm run test:e2e:chromium
npm run test:e2e:firefox
npm run test:e2e:webkit
```

### Debug tests
```bash
npm run test:e2e:debug
```

### View test report
```bash
npm run test:e2e:report
```

## Test Structure

```
e2e/
├── utils/
│   ├── auth.ts          # Authentication helpers
│   ├── api.ts           # API helpers
│   └── index.ts         # Exports
├── auth.spec.ts         # Authentication tests (12 scenarios)
├── encounter-workflow.spec.ts  # Encounter workflow tests (14 scenarios)
├── rbac.spec.ts         # Role-based access tests (15 scenarios)
├── security.spec.ts     # Security tests (14 scenarios)
├── performance.spec.ts  # Performance tests (12 scenarios)
├── global-setup.ts      # Pre-test setup
└── global-teardown.ts   # Post-test cleanup
```

## Test Users

| Role      | Email                      | Password     |
|-----------|----------------------------|--------------|
| Admin     | admin@phoenix.local        | Admin123!    |
| Physician | dr.smith@phoenix.local     | Doctor123!   |
| Nurse     | nurse.jones@phoenix.local  | Nurse123!    |
| Scribe    | scribe@phoenix.local       | Scribe123!   |
| Auditor   | auditor@phoenix.local      | Auditor123!  |

## Test Coverage

### Authentication Tests (auth.spec.ts)
- ✅ Display login page correctly
- ✅ Login with valid credentials (physician, admin)
- ✅ Show error on invalid credentials
- ✅ Show error on empty credentials
- ✅ Logout successfully
- ✅ Persist auth state across reloads
- ✅ Redirect to login for protected routes
- ✅ Redirect back after login
- ✅ Store tokens in localStorage
- ✅ Display loading state during login
- ✅ Display role correctly

### Encounter Workflow Tests (encounter-workflow.spec.ts)
- ✅ Navigate to create encounter page
- ✅ Fill in patient information
- ✅ Fill in transcript and submit
- ✅ Validate required fields
- ✅ Create encounter and navigate to review
- ✅ Display SOAP note sections
- ✅ Display patient information
- ✅ Allow editing SOAP sections
- ✅ Display safety flags
- ✅ Display coding suggestions
- ✅ Show approve/reject buttons
- ✅ Require signature for approval
- ✅ Show rejection reason modal
- ✅ Display and filter encounters list

### RBAC Tests (rbac.spec.ts)
- ✅ Admin sees all navigation items
- ✅ Admin accesses encounter creation
- ✅ Physician sees new encounter button
- ✅ Physician can create encounters
- ✅ Physician can access review page
- ✅ Nurse can view encounters
- ✅ Nurse cannot create encounters
- ✅ Nurse cannot approve notes
- ✅ Scribe has limited access
- ✅ Block unauthorized admin access
- ✅ Show unauthorized page with message
- ✅ Redirect unauthenticated to login
- ✅ Hide admin menu from non-admins

### Security Tests (security.spec.ts)
- ✅ Block prompt injection in transcript
- ✅ Block prompt injection in patient name
- ✅ Block SQL injection in MRN field
- ✅ Block SQL injection in search
- ✅ Sanitize XSS in transcript
- ✅ Escape HTML in displayed content
- ✅ Handle expired access token
- ✅ Clear tokens on logout
- ✅ Not expose tokens in URL
- ✅ Validate email format
- ✅ Limit input length
- ✅ Handle rapid login attempts
- ✅ Not leak sensitive info in errors

### Performance Tests (performance.spec.ts)
- ✅ Load login page quickly (<3s)
- ✅ Load dashboard quickly (<5s)
- ✅ Load encounters list quickly (<3s)
- ✅ Load create encounter page quickly (<2s)
- ✅ Process encounter within limits (<15s)
- ✅ Respond to clicks immediately (<200ms)
- ✅ Update input fields in real-time
- ✅ Handle navigation smoothly
- ✅ Load resources without errors
- ✅ No critical console errors
- ✅ Handle concurrent API calls
- ✅ Reasonable DOM size (<5000 elements)

## CI/CD Integration

The E2E tests run automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main`

See `.github/workflows/e2e-tests.yml` for the workflow configuration.

## Troubleshooting

### Tests fail with "page not found"
- Make sure both frontend and backend servers are running
- Check that test users are seeded

### Tests fail with "timeout"
- Increase timeout in playwright.config.ts
- Check network connectivity
- Verify API endpoints are responding

### Tests fail intermittently
- Add `await page.waitForLoadState('networkidle')` before assertions
- Use more specific selectors
- Add retry logic for flaky network requests

### Cannot find test users
- Run `python scripts/seed_test_users.py` to create them
- Check database connection string

## Adding New Tests

1. Create a new spec file in `e2e/`
2. Import utilities from `./utils`
3. Use `loginAs()` for authenticated tests
4. Use `waitForAPI()` when testing API interactions
5. Follow existing patterns for consistency

Example:
```typescript
import { test, expect } from '@playwright/test';
import { loginAs, clearAuthState } from './utils/auth';

test.describe('My Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await clearAuthState(page);
    await loginAs(page, 'physician');
  });
  
  test('should do something', async ({ page }) => {
    await page.goto('/my-feature');
    await expect(page.locator('text=Expected')).toBeVisible();
  });
});
```
