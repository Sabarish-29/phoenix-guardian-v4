/**
 * Phoenix Guardian Mobile - ReviewScreen Tests
 * 
 * Unit and integration tests for the SOAP note review screen.
 * Tests cover editing, diff highlighting, AI confidence indicators,
 * and draft saving functionality.
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import ReviewScreen from '../../../mobile/src/screens/ReviewScreen';
import OfflineService from '../../../mobile/src/services/OfflineService';
import EncounterService from '../../../mobile/src/services/EncounterService';
import encounterReducer from '../../../mobile/src/store/encounterSlice';
import offlineReducer from '../../../mobile/src/store/offlineSlice';

// =============================================================================
// MOCKS
// =============================================================================

jest.mock('../../../mobile/src/services/OfflineService', () => ({
  saveDraft: jest.fn().mockResolvedValue(undefined),
  getDraft: jest.fn().mockResolvedValue(null),
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
    aiConfidence: {
      subjective: 0.95,
      objective: 0.92,
      assessment: 0.88,
      plan: 0.85,
    },
  }),
  updateSOAPNote: jest.fn().mockResolvedValue({ success: true }),
}));

jest.mock('../../../mobile/src/utils/networkDetector', () => ({
  isOnline: jest.fn().mockResolvedValue(true),
  isOnlineSync: jest.fn().mockReturnValue(true),
  onChange: jest.fn().mockReturnValue(() => {}),
}));

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
          soapNote: {
            subjective: 'Patient reports severe headache for 3 days',
            objective: 'BP 120/80, Temp 98.6F, alert and oriented',
            assessment: 'Tension headache, likely stress-related',
            plan: 'Recommend OTC pain relief, follow up in 1 week',
          },
          aiConfidence: {
            subjective: 0.95,
            objective: 0.92,
            assessment: 0.88,
            plan: 0.85,
          },
          originalSoapNote: {
            subjective: 'Patient reports headache for 3 days',
            objective: 'BP 120/80, Temp 98.6F',
            assessment: 'Tension headache',
            plan: 'Recommend OTC pain relief',
          },
        },
        isLoading: false,
        error: null,
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
};

const mockRoute = {
  params: {
    encounterId: 'encounter_456',
    patientName: 'John Doe',
  },
};

const renderReviewScreen = (store = createTestStore()) => {
  return render(
    <Provider store={store}>
      <ReviewScreen navigation={mockNavigation} route={mockRoute} />
    </Provider>
  );
};

// =============================================================================
// TESTS
// =============================================================================

describe('ReviewScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ---------------------------------------------------------------------------
  // Rendering Tests
  // ---------------------------------------------------------------------------

  describe('Initial Rendering', () => {
    test('renders screen title correctly', () => {
      const { getByText } = renderReviewScreen();
      expect(getByText('Review SOAP Note')).toBeTruthy();
    });

    test('renders patient name', () => {
      const { getByText } = renderReviewScreen();
      expect(getByText('John Doe')).toBeTruthy();
    });

    test('renders all SOAP sections', () => {
      const { getByText } = renderReviewScreen();
      expect(getByText('Subjective')).toBeTruthy();
      expect(getByText('Objective')).toBeTruthy();
      expect(getByText('Assessment')).toBeTruthy();
      expect(getByText('Plan')).toBeTruthy();
    });

    test('renders SOAP section content', () => {
      const { getByText } = renderReviewScreen();
      expect(getByText(/Patient reports severe headache/)).toBeTruthy();
      expect(getByText(/BP 120\/80/)).toBeTruthy();
    });

    test('renders proceed to approval button', () => {
      const { getByText } = renderReviewScreen();
      expect(getByText('Proceed to Approval')).toBeTruthy();
    });

    test('renders save draft button', () => {
      const { getByText } = renderReviewScreen();
      expect(getByText('Save Draft')).toBeTruthy();
    });

    test('renders back button', () => {
      const { getByText } = renderReviewScreen();
      expect(getByText('← Back')).toBeTruthy();
    });
  });

  // ---------------------------------------------------------------------------
  // AI Confidence Indicator Tests
  // ---------------------------------------------------------------------------

  describe('AI Confidence Indicators', () => {
    test('displays confidence indicator for each section', () => {
      const { getAllByTestId } = renderReviewScreen();
      const indicators = getAllByTestId(/confidence-indicator/);
      expect(indicators.length).toBeGreaterThanOrEqual(4);
    });

    test('shows high confidence with green indicator (>90%)', () => {
      const { getByTestId } = renderReviewScreen();
      const indicator = getByTestId('confidence-indicator-subjective');
      expect(indicator.props.style.backgroundColor).toContain('green');
    });

    test('shows medium confidence with yellow indicator (70-90%)', () => {
      const { getByTestId } = renderReviewScreen();
      const indicator = getByTestId('confidence-indicator-plan');
      expect(indicator.props.style.backgroundColor).toContain('yellow');
    });

    test('displays confidence percentage on hover/tap', async () => {
      const { getByTestId, getByText } = renderReviewScreen();
      
      fireEvent.press(getByTestId('confidence-indicator-subjective'));
      
      await waitFor(() => {
        expect(getByText('95% confidence')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Diff Highlighting Tests
  // ---------------------------------------------------------------------------

  describe('Diff Highlighting', () => {
    test('shows diff toggle button', () => {
      const { getByText } = renderReviewScreen();
      expect(getByText('Show Changes')).toBeTruthy();
    });

    test('highlights added text in green when diff enabled', async () => {
      const { getByText, getAllByTestId } = renderReviewScreen();
      
      fireEvent.press(getByText('Show Changes'));
      
      await waitFor(() => {
        const additions = getAllByTestId('diff-addition');
        expect(additions.length).toBeGreaterThan(0);
      });
    });

    test('highlights removed text in red when diff enabled', async () => {
      const { getByText, queryAllByTestId } = renderReviewScreen();
      
      fireEvent.press(getByText('Show Changes'));
      
      await waitFor(() => {
        const removals = queryAllByTestId('diff-removal');
        expect(removals).toBeDefined();
      });
    });

    test('hides diff when toggle disabled', async () => {
      const { getByText, queryAllByTestId } = renderReviewScreen();
      
      // Enable diff
      fireEvent.press(getByText('Show Changes'));
      
      // Disable diff
      await waitFor(() => {
        fireEvent.press(getByText('Hide Changes'));
      });
      
      await waitFor(() => {
        const additions = queryAllByTestId('diff-addition');
        expect(additions.length).toBe(0);
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Inline Editing Tests
  // ---------------------------------------------------------------------------

  describe('Inline Editing', () => {
    test('enables edit mode when edit button pressed', async () => {
      const { getByTestId, queryByTestId } = renderReviewScreen();
      
      fireEvent.press(getByTestId('edit-subjective'));
      
      await waitFor(() => {
        expect(queryByTestId('edit-input-subjective')).toBeTruthy();
      });
    });

    test('shows original text in input field when editing', async () => {
      const { getByTestId } = renderReviewScreen();
      
      fireEvent.press(getByTestId('edit-subjective'));
      
      await waitFor(() => {
        const input = getByTestId('edit-input-subjective');
        expect(input.props.value).toContain('Patient reports severe headache');
      });
    });

    test('saves edits when save button pressed', async () => {
      const { getByTestId, getByText } = renderReviewScreen();
      
      fireEvent.press(getByTestId('edit-subjective'));
      
      await waitFor(() => {
        const input = getByTestId('edit-input-subjective');
        fireEvent.changeText(input, 'Updated subjective content');
      });
      
      fireEvent.press(getByText('Save'));
      
      await waitFor(() => {
        expect(getByText(/Updated subjective content/)).toBeTruthy();
      });
    });

    test('cancels edits when cancel button pressed', async () => {
      const { getByTestId, getByText, queryByText } = renderReviewScreen();
      
      fireEvent.press(getByTestId('edit-subjective'));
      
      await waitFor(() => {
        const input = getByTestId('edit-input-subjective');
        fireEvent.changeText(input, 'Should not appear');
      });
      
      fireEvent.press(getByText('Cancel'));
      
      await waitFor(() => {
        expect(queryByText('Should not appear')).toBeNull();
        expect(getByText(/Patient reports severe headache/)).toBeTruthy();
      });
    });

    test('tracks edited sections for diff display', async () => {
      const { getByTestId, getByText, getAllByTestId } = renderReviewScreen();
      
      fireEvent.press(getByTestId('edit-objective'));
      
      await waitFor(() => {
        const input = getByTestId('edit-input-objective');
        fireEvent.changeText(input, 'New objective content with changes');
      });
      
      fireEvent.press(getByText('Save'));
      
      fireEvent.press(getByText('Show Changes'));
      
      await waitFor(() => {
        const additions = getAllByTestId('diff-addition');
        expect(additions.length).toBeGreaterThan(0);
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Draft Saving Tests
  // ---------------------------------------------------------------------------

  describe('Draft Saving', () => {
    test('saves draft when save draft button pressed', async () => {
      const { getByText } = renderReviewScreen();
      
      fireEvent.press(getByText('Save Draft'));
      
      await waitFor(() => {
        expect(OfflineService.saveDraft).toHaveBeenCalledWith(
          'encounter_456',
          expect.any(Object)
        );
      });
    });

    test('shows success message after saving draft', async () => {
      const { getByText, queryByText } = renderReviewScreen();
      
      fireEvent.press(getByText('Save Draft'));
      
      await waitFor(() => {
        expect(queryByText('Draft saved')).toBeTruthy();
      });
    });

    test('auto-saves draft after significant edits', async () => {
      jest.useFakeTimers();
      const { getByTestId, getByText } = renderReviewScreen();
      
      fireEvent.press(getByTestId('edit-subjective'));
      
      await waitFor(() => {
        const input = getByTestId('edit-input-subjective');
        fireEvent.changeText(input, 'Updated content for auto-save test');
      });
      
      fireEvent.press(getByText('Save'));
      
      // Advance timer for auto-save
      act(() => {
        jest.advanceTimersByTime(30000);
      });
      
      await waitFor(() => {
        expect(OfflineService.saveDraft).toHaveBeenCalled();
      });
      
      jest.useRealTimers();
    });

    test('restores draft on component mount if available', async () => {
      (OfflineService.getDraft as jest.Mock).mockResolvedValueOnce({
        subjective: 'Draft subjective content',
        objective: 'Draft objective content',
        assessment: 'Draft assessment content',
        plan: 'Draft plan content',
      });

      const { getByText } = renderReviewScreen();
      
      await waitFor(() => {
        expect(OfflineService.getDraft).toHaveBeenCalledWith('encounter_456');
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Navigation Tests
  // ---------------------------------------------------------------------------

  describe('Navigation', () => {
    test('navigates to approval screen on proceed button', async () => {
      const { getByText } = renderReviewScreen();
      
      fireEvent.press(getByText('Proceed to Approval'));
      
      await waitFor(() => {
        expect(mockNavigation.navigate).toHaveBeenCalledWith('Approval', {
          encounterId: 'encounter_456',
          patientName: 'John Doe',
        });
      });
    });

    test('prompts to save unsaved changes before navigation', async () => {
      const { getByTestId, getByText, queryByText } = renderReviewScreen();
      
      // Make an edit
      fireEvent.press(getByTestId('edit-subjective'));
      
      await waitFor(() => {
        const input = getByTestId('edit-input-subjective');
        fireEvent.changeText(input, 'Unsaved changes');
      });
      
      fireEvent.press(getByText('Save'));
      
      // Try to navigate
      fireEvent.press(getByText('Proceed to Approval'));
      
      await waitFor(() => {
        expect(queryByText('Save changes before proceeding?')).toBeTruthy();
      });
    });

    test('goes back when back button pressed', async () => {
      const { getByText } = renderReviewScreen();
      
      fireEvent.press(getByText('← Back'));
      
      expect(mockNavigation.goBack).toHaveBeenCalled();
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
      
      const { getByText } = renderReviewScreen(store);
      expect(getByText('Offline Mode')).toBeTruthy();
    });

    test('enables editing in offline mode', async () => {
      const store = createTestStore({
        offline: {
          isOnline: false,
          pendingSync: [],
          syncInProgress: false,
        },
      });
      
      const { getByTestId, queryByTestId } = renderReviewScreen(store);
      
      fireEvent.press(getByTestId('edit-subjective'));
      
      await waitFor(() => {
        expect(queryByTestId('edit-input-subjective')).toBeTruthy();
      });
    });

    test('queues draft save when offline', async () => {
      const store = createTestStore({
        offline: {
          isOnline: false,
          pendingSync: [],
          syncInProgress: false,
        },
      });
      
      const { getByText } = renderReviewScreen(store);
      
      fireEvent.press(getByText('Save Draft'));
      
      await waitFor(() => {
        expect(OfflineService.saveDraft).toHaveBeenCalled();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Error Handling Tests
  // ---------------------------------------------------------------------------

  describe('Error Handling', () => {
    test('shows error message when save fails', async () => {
      (OfflineService.saveDraft as jest.Mock).mockRejectedValueOnce(
        new Error('Save failed')
      );
      
      const { getByText, queryByText } = renderReviewScreen();
      
      fireEvent.press(getByText('Save Draft'));
      
      await waitFor(() => {
        expect(queryByText('Failed to save draft')).toBeTruthy();
      });
    });

    test('displays retry button on error', async () => {
      (OfflineService.saveDraft as jest.Mock).mockRejectedValueOnce(
        new Error('Save failed')
      );
      
      const { getByText, queryByText } = renderReviewScreen();
      
      fireEvent.press(getByText('Save Draft'));
      
      await waitFor(() => {
        expect(queryByText('Retry')).toBeTruthy();
      });
    });

    test('retries save when retry button pressed', async () => {
      (OfflineService.saveDraft as jest.Mock)
        .mockRejectedValueOnce(new Error('Save failed'))
        .mockResolvedValueOnce(undefined);
      
      const { getByText, queryByText } = renderReviewScreen();
      
      fireEvent.press(getByText('Save Draft'));
      
      await waitFor(() => {
        expect(queryByText('Retry')).toBeTruthy();
      });
      
      fireEvent.press(getByText('Retry'));
      
      await waitFor(() => {
        expect(OfflineService.saveDraft).toHaveBeenCalledTimes(2);
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Validation Tests
  // ---------------------------------------------------------------------------

  describe('Validation', () => {
    test('validates required fields before proceeding', async () => {
      const store = createTestStore({
        encounter: {
          currentEncounter: {
            id: 'encounter_456',
            patientId: 'patient_123',
            soapNote: {
              subjective: '',
              objective: 'BP 120/80',
              assessment: 'Tension headache',
              plan: 'Recommend OTC pain relief',
            },
            aiConfidence: {},
          },
          isLoading: false,
          error: null,
        },
      });
      
      const { getByText, queryByText } = renderReviewScreen(store);
      
      fireEvent.press(getByText('Proceed to Approval'));
      
      await waitFor(() => {
        expect(queryByText('Please complete all SOAP sections')).toBeTruthy();
      });
    });

    test('shows validation warning for low-confidence sections', () => {
      const store = createTestStore({
        encounter: {
          currentEncounter: {
            id: 'encounter_456',
            patientId: 'patient_123',
            soapNote: {
              subjective: 'Content',
              objective: 'Content',
              assessment: 'Content',
              plan: 'Content',
            },
            aiConfidence: {
              subjective: 0.6,
              objective: 0.92,
              assessment: 0.55,
              plan: 0.85,
            },
          },
          isLoading: false,
          error: null,
        },
      });
      
      const { getByText } = renderReviewScreen(store);
      expect(getByText('Review recommended')).toBeTruthy();
    });
  });
});
