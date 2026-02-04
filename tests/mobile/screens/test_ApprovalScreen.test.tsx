/**
 * Phoenix Guardian Mobile - ApprovalScreen Tests
 * 
 * Unit and integration tests for the SOAP note approval screen.
 * Tests cover attestation, one-tap submission, EHR integration,
 * confirmation modals, and offline handling.
 */

import React from 'react';
import { render, fireEvent, waitFor, act, Alert } from '@testing-library/react-native';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import ApprovalScreen from '../../../mobile/src/screens/ApprovalScreen';
import OfflineService from '../../../mobile/src/services/OfflineService';
import EncounterService from '../../../mobile/src/services/EncounterService';
import NetworkDetector from '../../../mobile/src/utils/networkDetector';
import encounterReducer from '../../../mobile/src/store/encounterSlice';
import offlineReducer from '../../../mobile/src/store/offlineSlice';

// =============================================================================
// MOCKS
// =============================================================================

jest.mock('../../../mobile/src/services/OfflineService', () => ({
  queueForSync: jest.fn().mockResolvedValue(undefined),
  getPendingSubmissions: jest.fn().mockResolvedValue([]),
}));

jest.mock('../../../mobile/src/services/EncounterService', () => ({
  getEncounter: jest.fn().mockResolvedValue({
    id: 'encounter_456',
    patientId: 'patient_123',
    soapNote: {
      subjective: 'Patient reports severe headache for 3 days',
      objective: 'BP 120/80, Temp 98.6F, alert and oriented',
      assessment: 'Tension headache, likely stress-related',
      plan: 'Recommend OTC pain relief, follow up in 1 week',
    },
    status: 'pending_approval',
  }),
  submitToEHR: jest.fn().mockResolvedValue({ 
    success: true, 
    ehrId: 'EHR_123456',
    timestamp: '2026-02-01T12:00:00Z',
  }),
  finalizeEncounter: jest.fn().mockResolvedValue({ success: true }),
}));

jest.mock('../../../mobile/src/utils/networkDetector', () => ({
  isOnline: jest.fn().mockResolvedValue(true),
  isOnlineSync: jest.fn().mockReturnValue(true),
  onChange: jest.fn().mockReturnValue(() => {}),
}));

jest.spyOn(Alert, 'alert');

// =============================================================================
// TEST UTILITIES
// =============================================================================

const createTestStore = (initialState = {}) => {
  return configureStore({
    reducer: {
      encounter: encounterReducer,
      offline: offlineReducer,
    },
    preloadedState: {
      encounter: {
        currentEncounter: {
          id: 'encounter_456',
          patientId: 'patient_123',
          patientName: 'John Doe',
          soapNote: {
            subjective: 'Patient reports severe headache for 3 days',
            objective: 'BP 120/80, Temp 98.6F, alert and oriented',
            assessment: 'Tension headache, likely stress-related',
            plan: 'Recommend OTC pain relief, follow up in 1 week',
          },
          status: 'pending_approval',
        },
        isLoading: false,
        error: null,
        isSubmitting: false,
      },
      offline: {
        isOnline: true,
        pendingSync: [],
        syncInProgress: false,
      },
      ...initialState,
    },
  });
};

const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
  reset: jest.fn(),
};

const mockRoute = {
  params: {
    encounterId: 'encounter_456',
    patientName: 'John Doe',
  },
};

const renderApprovalScreen = (store = createTestStore()) => {
  return render(
    <Provider store={store}>
      <ApprovalScreen navigation={mockNavigation} route={mockRoute} />
    </Provider>
  );
};

// =============================================================================
// TESTS
// =============================================================================

describe('ApprovalScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ---------------------------------------------------------------------------
  // Rendering Tests
  // ---------------------------------------------------------------------------

  describe('Initial Rendering', () => {
    test('renders screen title correctly', () => {
      const { getByText } = renderApprovalScreen();
      expect(getByText('Approve & Submit')).toBeTruthy();
    });

    test('renders patient name', () => {
      const { getByText } = renderApprovalScreen();
      expect(getByText('John Doe')).toBeTruthy();
    });

    test('renders SOAP note preview', () => {
      const { getByText } = renderApprovalScreen();
      expect(getByText(/Patient reports severe headache/)).toBeTruthy();
      expect(getByText(/BP 120\/80/)).toBeTruthy();
      expect(getByText(/Tension headache/)).toBeTruthy();
      expect(getByText(/Recommend OTC pain relief/)).toBeTruthy();
    });

    test('renders all SOAP section headers', () => {
      const { getByText } = renderApprovalScreen();
      expect(getByText('Subjective')).toBeTruthy();
      expect(getByText('Objective')).toBeTruthy();
      expect(getByText('Assessment')).toBeTruthy();
      expect(getByText('Plan')).toBeTruthy();
    });

    test('renders attestation checkbox unchecked by default', () => {
      const { getByTestId } = renderApprovalScreen();
      const checkbox = getByTestId('attestation-checkbox');
      expect(checkbox.props.accessibilityState.checked).toBe(false);
    });

    test('renders attestation text', () => {
      const { getByText } = renderApprovalScreen();
      expect(getByText(/I attest that I have reviewed/)).toBeTruthy();
    });

    test('renders submit button', () => {
      const { getByText } = renderApprovalScreen();
      expect(getByText('Submit to EHR')).toBeTruthy();
    });

    test('renders back button', () => {
      const { getByText } = renderApprovalScreen();
      expect(getByText('← Back to Review')).toBeTruthy();
    });
  });

  // ---------------------------------------------------------------------------
  // Attestation Tests
  // ---------------------------------------------------------------------------

  describe('Attestation Checkbox', () => {
    test('toggles attestation checkbox when pressed', async () => {
      const { getByTestId } = renderApprovalScreen();
      const checkbox = getByTestId('attestation-checkbox');
      
      fireEvent.press(checkbox);
      
      await waitFor(() => {
        expect(checkbox.props.accessibilityState.checked).toBe(true);
      });
    });

    test('submit button disabled when attestation not checked', () => {
      const { getByTestId } = renderApprovalScreen();
      const submitButton = getByTestId('submit-button');
      expect(submitButton.props.accessibilityState.disabled).toBe(true);
    });

    test('submit button enabled when attestation checked', async () => {
      const { getByTestId } = renderApprovalScreen();
      const checkbox = getByTestId('attestation-checkbox');
      const submitButton = getByTestId('submit-button');
      
      fireEvent.press(checkbox);
      
      await waitFor(() => {
        expect(submitButton.props.accessibilityState.disabled).toBe(false);
      });
    });

    test('shows attestation reminder when trying to submit unchecked', async () => {
      const { getByTestId, queryByText } = renderApprovalScreen();
      const submitButton = getByTestId('submit-button');
      
      fireEvent.press(submitButton);
      
      await waitFor(() => {
        expect(queryByText('Please attest before submitting')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Confirmation Modal Tests
  // ---------------------------------------------------------------------------

  describe('Confirmation Modal', () => {
    test('shows confirmation modal when submit pressed', async () => {
      const { getByTestId, getByText, queryByText } = renderApprovalScreen();
      
      // Check attestation
      fireEvent.press(getByTestId('attestation-checkbox'));
      
      // Press submit
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        expect(queryByText('Confirm Submission')).toBeTruthy();
        expect(queryByText('This will submit the SOAP note to the EHR')).toBeTruthy();
      });
    });

    test('modal shows patient name and encounter ID', async () => {
      const { getByTestId, getByText, queryByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        expect(queryByText('John Doe')).toBeTruthy();
        expect(queryByText(/encounter_456/)).toBeTruthy();
      });
    });

    test('modal has confirm and cancel buttons', async () => {
      const { getByTestId, getByText, queryByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        expect(queryByText('Confirm')).toBeTruthy();
        expect(queryByText('Cancel')).toBeTruthy();
      });
    });

    test('closes modal when cancel pressed', async () => {
      const { getByTestId, getByText, queryByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        expect(queryByText('Confirm Submission')).toBeTruthy();
      });
      
      fireEvent.press(getByText('Cancel'));
      
      await waitFor(() => {
        expect(queryByText('Confirm Submission')).toBeNull();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Submission Tests
  // ---------------------------------------------------------------------------

  describe('EHR Submission', () => {
    test('submits to EHR when confirmed', async () => {
      const { getByTestId, getByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        expect(EncounterService.submitToEHR).toHaveBeenCalledWith(
          'encounter_456',
          expect.any(Object)
        );
      });
    });

    test('shows loading state during submission', async () => {
      (EncounterService.submitToEHR as jest.Mock).mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 100))
      );
      
      const { getByTestId, getByText, queryByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      expect(queryByText('Submitting...')).toBeTruthy();
    });

    test('shows success message after submission', async () => {
      const { getByTestId, getByText, queryByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        expect(queryByText('Successfully submitted to EHR')).toBeTruthy();
      });
    });

    test('displays EHR confirmation ID after success', async () => {
      const { getByTestId, getByText, queryByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        expect(queryByText(/EHR_123456/)).toBeTruthy();
      });
    });

    test('navigates to home after successful submission', async () => {
      const { getByTestId, getByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        expect(mockNavigation.reset).toHaveBeenCalledWith({
          index: 0,
          routes: [{ name: 'Home' }],
        });
      });
    });
  });

  // ---------------------------------------------------------------------------
  // One-Tap Submission Tests
  // ---------------------------------------------------------------------------

  describe('One-Tap Submission', () => {
    test('enables one-tap submit for trusted encounters', async () => {
      const store = createTestStore({
        encounter: {
          currentEncounter: {
            id: 'encounter_456',
            patientId: 'patient_123',
            soapNote: { subjective: 'Content', objective: 'Content', assessment: 'Content', plan: 'Content' },
            status: 'pending_approval',
            aiConfidence: { overall: 0.98 },
            trusted: true,
          },
          isLoading: false,
          error: null,
        },
      });
      
      const { getByText } = renderApprovalScreen(store);
      expect(getByText('Quick Submit ✓')).toBeTruthy();
    });

    test('one-tap submit skips confirmation for trusted encounters', async () => {
      const store = createTestStore({
        encounter: {
          currentEncounter: {
            id: 'encounter_456',
            patientId: 'patient_123',
            soapNote: { subjective: 'Content', objective: 'Content', assessment: 'Content', plan: 'Content' },
            status: 'pending_approval',
            aiConfidence: { overall: 0.98 },
            trusted: true,
          },
          isLoading: false,
          error: null,
        },
      });
      
      const { getByTestId, getByText, queryByText } = renderApprovalScreen(store);
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Quick Submit ✓'));
      
      await waitFor(() => {
        // Should not show confirmation modal
        expect(queryByText('Confirm Submission')).toBeNull();
        expect(EncounterService.submitToEHR).toHaveBeenCalled();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Offline Mode Tests
  // ---------------------------------------------------------------------------

  describe('Offline Mode', () => {
    test('shows offline indicator when offline', () => {
      const store = createTestStore({
        offline: {
          isOnline: false,
          pendingSync: [],
          syncInProgress: false,
        },
      });
      
      const { getByText } = renderApprovalScreen(store);
      expect(getByText('Offline Mode')).toBeTruthy();
    });

    test('queues submission for sync when offline', async () => {
      const store = createTestStore({
        offline: {
          isOnline: false,
          pendingSync: [],
          syncInProgress: false,
        },
      });
      
      const { getByTestId, getByText, queryByText } = renderApprovalScreen(store);
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        expect(OfflineService.queueForSync).toHaveBeenCalledWith({
          type: 'submit_encounter',
          encounterId: 'encounter_456',
          data: expect.any(Object),
        });
      });
    });

    test('shows queued confirmation when offline submission', async () => {
      const store = createTestStore({
        offline: {
          isOnline: false,
          pendingSync: [],
          syncInProgress: false,
        },
      });
      
      const { getByTestId, getByText, queryByText } = renderApprovalScreen(store);
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        expect(queryByText('Queued for submission')).toBeTruthy();
        expect(queryByText('Will submit when online')).toBeTruthy();
      });
    });

    test('shows pending count in offline mode', async () => {
      (OfflineService.getPendingSubmissions as jest.Mock).mockResolvedValue([
        { id: 'enc_1' },
        { id: 'enc_2' },
      ]);
      
      const store = createTestStore({
        offline: {
          isOnline: false,
          pendingSync: ['enc_1', 'enc_2'],
          syncInProgress: false,
        },
      });
      
      const { getByText } = renderApprovalScreen(store);
      
      await waitFor(() => {
        expect(getByText('2 pending submissions')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Error Handling Tests
  // ---------------------------------------------------------------------------

  describe('Error Handling', () => {
    test('shows error message when submission fails', async () => {
      (EncounterService.submitToEHR as jest.Mock).mockRejectedValueOnce(
        new Error('EHR connection failed')
      );
      
      const { getByTestId, getByText, queryByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        expect(queryByText('Failed to submit to EHR')).toBeTruthy();
      });
    });

    test('shows retry button on failure', async () => {
      (EncounterService.submitToEHR as jest.Mock).mockRejectedValueOnce(
        new Error('EHR connection failed')
      );
      
      const { getByTestId, getByText, queryByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        expect(queryByText('Retry')).toBeTruthy();
      });
    });

    test('offers offline queue option on failure', async () => {
      (EncounterService.submitToEHR as jest.Mock).mockRejectedValueOnce(
        new Error('EHR connection failed')
      );
      
      const { getByTestId, getByText, queryByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        expect(queryByText('Save & Submit Later')).toBeTruthy();
      });
    });

    test('queues for sync when save for later pressed', async () => {
      (EncounterService.submitToEHR as jest.Mock).mockRejectedValueOnce(
        new Error('EHR connection failed')
      );
      
      const { getByTestId, getByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        fireEvent.press(getByText('Save & Submit Later'));
      });
      
      await waitFor(() => {
        expect(OfflineService.queueForSync).toHaveBeenCalled();
      });
    });

    test('retries submission when retry pressed', async () => {
      (EncounterService.submitToEHR as jest.Mock)
        .mockRejectedValueOnce(new Error('EHR connection failed'))
        .mockResolvedValueOnce({ success: true, ehrId: 'EHR_123456' });
      
      const { getByTestId, getByText, queryByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        expect(queryByText('Retry')).toBeTruthy();
      });
      
      fireEvent.press(getByText('Retry'));
      
      await waitFor(() => {
        expect(EncounterService.submitToEHR).toHaveBeenCalledTimes(2);
        expect(queryByText('Successfully submitted to EHR')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Navigation Tests
  // ---------------------------------------------------------------------------

  describe('Navigation', () => {
    test('goes back to review when back button pressed', () => {
      const { getByText } = renderApprovalScreen();
      
      fireEvent.press(getByText('← Back to Review'));
      
      expect(mockNavigation.goBack).toHaveBeenCalled();
    });

    test('warns before leaving with attestation checked', async () => {
      const { getByTestId, getByText, queryByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('← Back to Review'));
      
      await waitFor(() => {
        expect(queryByText('Discard attestation and go back?')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Accessibility Tests
  // ---------------------------------------------------------------------------

  describe('Accessibility', () => {
    test('submit button has proper accessibility label', () => {
      const { getByTestId } = renderApprovalScreen();
      const button = getByTestId('submit-button');
      expect(button.props.accessibilityLabel).toBe('Submit SOAP note to EHR');
    });

    test('attestation checkbox has proper accessibility role', () => {
      const { getByTestId } = renderApprovalScreen();
      const checkbox = getByTestId('attestation-checkbox');
      expect(checkbox.props.accessibilityRole).toBe('checkbox');
    });

    test('screen reader announces submission status', async () => {
      const { getByTestId, getByText, queryByLabelText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        const successElement = queryByLabelText('Submission successful');
        expect(successElement).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Security Tests
  // ---------------------------------------------------------------------------

  describe('Security', () => {
    test('logs attestation event with timestamp', async () => {
      const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation();
      const { getByTestId } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      
      await waitFor(() => {
        expect(consoleLogSpy).toHaveBeenCalledWith(
          expect.stringContaining('Attestation recorded'),
          expect.any(Object)
        );
      });
      
      consoleLogSpy.mockRestore();
    });

    test('includes physician attestation in submission payload', async () => {
      const { getByTestId, getByText } = renderApprovalScreen();
      
      fireEvent.press(getByTestId('attestation-checkbox'));
      fireEvent.press(getByText('Submit to EHR'));
      
      await waitFor(() => {
        fireEvent.press(getByText('Confirm'));
      });
      
      await waitFor(() => {
        expect(EncounterService.submitToEHR).toHaveBeenCalledWith(
          'encounter_456',
          expect.objectContaining({
            attestation: true,
            attestationTimestamp: expect.any(String),
          })
        );
      });
    });
  });
});
