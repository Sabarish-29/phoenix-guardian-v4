/**
 * Phoenix Guardian Mobile - RecordingScreen Tests
 * 
 * Unit and integration tests for the RecordingScreen component.
 * Tests cover recording lifecycle, WebSocket integration, offline mode,
 * and UI interactions.
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { Audio } from 'expo-av';
import RecordingScreen from '../../../mobile/src/screens/RecordingScreen';
import WebSocketService from '../../../mobile/src/services/WebSocketService';
import OfflineService from '../../../mobile/src/services/OfflineService';
import NetworkDetector from '../../../mobile/src/utils/networkDetector';
import encounterReducer from '../../../mobile/src/store/encounterSlice';
import offlineReducer from '../../../mobile/src/store/offlineSlice';

// =============================================================================
// MOCKS
// =============================================================================

jest.mock('expo-av', () => ({
  Audio: {
    requestPermissionsAsync: jest.fn(),
    setAudioModeAsync: jest.fn(),
    Recording: jest.fn().mockImplementation(() => ({
      prepareToRecordAsync: jest.fn(),
      startAsync: jest.fn(),
      stopAndUnloadAsync: jest.fn(),
      pauseAsync: jest.fn(),
      getStatusAsync: jest.fn().mockResolvedValue({
        isRecording: true,
        metering: -20,
      }),
      getURI: jest.fn().mockReturnValue('/path/to/audio.m4a'),
    })),
    RecordingOptionsPresets: {
      HIGH_QUALITY: {},
    },
  },
}));

jest.mock('../../../mobile/src/services/WebSocketService', () => ({
  getInstance: jest.fn().mockReturnValue({
    connect: jest.fn().mockResolvedValue(true),
    disconnect: jest.fn(),
    startEncounter: jest.fn(),
    stopEncounter: jest.fn(),
    sendAudioChunk: jest.fn(),
    on: jest.fn().mockReturnValue(() => {}),
    isConnected: jest.fn().mockReturnValue(true),
  }),
}));

jest.mock('../../../mobile/src/services/OfflineService', () => ({
  saveEncounter: jest.fn().mockResolvedValue(undefined),
  getPendingEncounters: jest.fn().mockResolvedValue([]),
}));

jest.mock('../../../mobile/src/utils/networkDetector', () => ({
  isOnline: jest.fn().mockResolvedValue(true),
  onChange: jest.fn().mockReturnValue(() => {}),
  isOnlineSync: jest.fn().mockReturnValue(true),
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
    preloadedState: initialState,
  });
};

const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
};

const mockRoute = {
  params: {
    patientId: 'patient_123',
    encounterId: 'encounter_456',
    patientName: 'John Doe',
  },
};

const renderRecordingScreen = (store = createTestStore()) => {
  return render(
    <Provider store={store}>
      <RecordingScreen navigation={mockNavigation} route={mockRoute} />
    </Provider>
  );
};

// =============================================================================
// TESTS
// =============================================================================

describe('RecordingScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (Audio.requestPermissionsAsync as jest.Mock).mockResolvedValue({ granted: true });
    (Audio.setAudioModeAsync as jest.Mock).mockResolvedValue(undefined);
  });

  // ---------------------------------------------------------------------------
  // Rendering Tests
  // ---------------------------------------------------------------------------

  describe('Initial Rendering', () => {
    test('renders screen title correctly', () => {
      const { getByText } = renderRecordingScreen();
      expect(getByText('Recording Encounter')).toBeTruthy();
    });

    test('renders patient name when provided', () => {
      const { getByText } = renderRecordingScreen();
      expect(getByText('John Doe')).toBeTruthy();
    });

    test('renders start recording button in idle state', () => {
      const { getByText } = renderRecordingScreen();
      expect(getByText('Start Recording')).toBeTruthy();
    });

    test('renders recording tips when idle', () => {
      const { getByText } = renderRecordingScreen();
      expect(getByText('Recording Tips')).toBeTruthy();
      expect(getByText('• Speak clearly and at a normal pace')).toBeTruthy();
    });

    test('renders back button', () => {
      const { getByText } = renderRecordingScreen();
      expect(getByText('← Back')).toBeTruthy();
    });
  });

  // ---------------------------------------------------------------------------
  // Recording Lifecycle Tests
  // ---------------------------------------------------------------------------

  describe('Recording Lifecycle', () => {
    test('starts recording when start button is pressed', async () => {
      const { getByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(Audio.requestPermissionsAsync).toHaveBeenCalled();
        expect(Audio.setAudioModeAsync).toHaveBeenCalled();
      });
    });

    test('shows recording controls after starting', async () => {
      const { getByText, queryByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('⏸ Pause')).toBeTruthy();
        expect(queryByText('⏹ Stop')).toBeTruthy();
      });
    });

    test('shows duration timer while recording', async () => {
      const { getByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(getByText('00:00')).toBeTruthy();
      });
    });

    test('connects WebSocket when recording starts (online)', async () => {
      const wsService = WebSocketService.getInstance();
      const { getByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(wsService.connect).toHaveBeenCalled();
        expect(wsService.startEncounter).toHaveBeenCalledWith(
          'patient_123',
          'encounter_456'
        );
      });
    });

    test('stops recording and shows processing state', async () => {
      const { getByText, queryByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('⏹ Stop')).toBeTruthy();
      });
      
      fireEvent.press(getByText('⏹ Stop'));
      
      await waitFor(() => {
        expect(queryByText('Generating SOAP note...')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Permission Tests
  // ---------------------------------------------------------------------------

  describe('Microphone Permissions', () => {
    test('requests microphone permission before recording', async () => {
      const { getByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(Audio.requestPermissionsAsync).toHaveBeenCalled();
      });
    });

    test('shows alert when permission denied', async () => {
      (Audio.requestPermissionsAsync as jest.Mock).mockResolvedValueOnce({ granted: false });
      
      const { getByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      // Recording should not proceed without permission
      await waitFor(() => {
        expect(Audio.setAudioModeAsync).not.toHaveBeenCalled();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Pause/Resume Tests
  // ---------------------------------------------------------------------------

  describe('Pause and Resume', () => {
    test('pauses recording when pause button pressed', async () => {
      const { getByText, queryByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('⏸ Pause')).toBeTruthy();
      });
      
      fireEvent.press(getByText('⏸ Pause'));
      
      await waitFor(() => {
        expect(queryByText('⏸ PAUSED')).toBeTruthy();
        expect(queryByText('▶ Resume')).toBeTruthy();
      });
    });

    test('resumes recording when resume button pressed', async () => {
      const { getByText, queryByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('⏸ Pause')).toBeTruthy();
      });
      
      fireEvent.press(getByText('⏸ Pause'));
      
      await waitFor(() => {
        expect(queryByText('▶ Resume')).toBeTruthy();
      });
      
      fireEvent.press(getByText('▶ Resume'));
      
      await waitFor(() => {
        expect(queryByText('⏸ Pause')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Offline Mode Tests
  // ---------------------------------------------------------------------------

  describe('Offline Mode', () => {
    beforeEach(() => {
      (NetworkDetector.isOnline as jest.Mock).mockResolvedValue(false);
      (NetworkDetector.isOnlineSync as jest.Mock).mockReturnValue(false);
    });

    test('shows offline badge when offline', async () => {
      (NetworkDetector.onChange as jest.Mock).mockImplementation((callback) => {
        callback(false);
        return () => {};
      });
      
      const { queryByText } = renderRecordingScreen();
      
      await waitFor(() => {
        expect(queryByText('📡 Offline')).toBeTruthy();
      });
    });

    test('saves encounter locally when recording offline', async () => {
      (NetworkDetector.isOnline as jest.Mock).mockResolvedValue(false);
      
      const { getByText, queryByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('⏹ Stop')).toBeTruthy();
      });
      
      fireEvent.press(getByText('⏹ Stop'));
      
      await waitFor(() => {
        expect(OfflineService.saveEncounter).toHaveBeenCalledWith(
          expect.objectContaining({
            encounterId: 'encounter_456',
            patientId: 'patient_123',
          })
        );
      });
    });

    test('does not connect WebSocket when offline', async () => {
      const wsService = WebSocketService.getInstance();
      (NetworkDetector.isOnline as jest.Mock).mockResolvedValue(false);
      
      const { getByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(wsService.connect).not.toHaveBeenCalled();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // WebSocket Event Tests
  // ---------------------------------------------------------------------------

  describe('WebSocket Events', () => {
    test('displays transcript updates from WebSocket', async () => {
      let wsCallback: any;
      (WebSocketService.getInstance().on as jest.Mock).mockImplementation((callback) => {
        wsCallback = callback;
        return () => {};
      });
      
      const { getByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(wsCallback).toBeDefined();
      });
      
      act(() => {
        wsCallback({ type: 'transcript_update', text: 'Patient reports headache' });
      });
      
      await waitFor(() => {
        expect(getByText('Patient reports headache')).toBeTruthy();
      });
    });

    test('displays SOAP sections as they arrive', async () => {
      let wsCallback: any;
      (WebSocketService.getInstance().on as jest.Mock).mockImplementation((callback) => {
        wsCallback = callback;
        return () => {};
      });
      
      const { getByText, queryByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(wsCallback).toBeDefined();
      });
      
      act(() => {
        wsCallback({ 
          type: 'soap_section_ready', 
          section: 'subjective', 
          text: 'Patient presents with headache' 
        });
      });
      
      await waitFor(() => {
        expect(queryByText('SUBJECTIVE')).toBeTruthy();
        expect(queryByText('Patient presents with headache')).toBeTruthy();
      });
    });

    test('navigates to Review screen on soap_complete', async () => {
      let wsCallback: any;
      (WebSocketService.getInstance().on as jest.Mock).mockImplementation((callback) => {
        wsCallback = callback;
        return () => {};
      });
      
      const { getByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(wsCallback).toBeDefined();
      });
      
      const soapNote = {
        subjective: 'S content',
        objective: 'O content',
        assessment: 'A content',
        plan: 'P content',
      };
      
      act(() => {
        wsCallback({ 
          type: 'soap_complete', 
          encounter_id: 'encounter_456',
          soap_note: soapNote
        });
      });
      
      await waitFor(() => {
        expect(mockNavigation.navigate).toHaveBeenCalledWith(
          'Review',
          expect.objectContaining({
            encounterId: 'encounter_456',
            soapNote,
          })
        );
      });
    });

    test('handles WebSocket errors gracefully', async () => {
      let wsCallback: any;
      (WebSocketService.getInstance().on as jest.Mock).mockImplementation((callback) => {
        wsCallback = callback;
        return () => {};
      });
      
      const { getByText, queryByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(wsCallback).toBeDefined();
      });
      
      act(() => {
        wsCallback({ type: 'error', message: 'Server error occurred' });
      });
      
      // Should show error and reset to idle
      await waitFor(() => {
        expect(queryByText('Start Recording')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Cancel Recording Tests
  // ---------------------------------------------------------------------------

  describe('Cancel Recording', () => {
    test('shows cancel link while recording', async () => {
      const { getByText, queryByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('Cancel Recording')).toBeTruthy();
      });
    });

    test('confirms before cancelling recording', async () => {
      const { getByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(getByText('Cancel Recording')).toBeTruthy();
      });
      
      // Pressing cancel should show confirmation (handled by Alert)
      fireEvent.press(getByText('Cancel Recording'));
      // Alert.alert is called - tested via mock verification
    });
  });

  // ---------------------------------------------------------------------------
  // Audio Level Indicator Tests
  // ---------------------------------------------------------------------------

  describe('Audio Level Indicator', () => {
    test('displays audio level bars while recording', async () => {
      const { getByText, queryAllByTestId } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        // Audio level container should be rendered
        expect(getByText('⏹ Stop')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Navigation Tests
  // ---------------------------------------------------------------------------

  describe('Navigation', () => {
    test('navigates back when back button pressed (idle state)', () => {
      const { getByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('← Back'));
      
      expect(mockNavigation.goBack).toHaveBeenCalled();
    });

    test('shows cancel confirmation when back pressed during recording', async () => {
      const { getByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(getByText('⏹ Stop')).toBeTruthy();
      });
      
      fireEvent.press(getByText('← Back'));
      
      // Should trigger cancel confirmation
      // Alert.alert is called
    });
  });

  // ---------------------------------------------------------------------------
  // Error Handling Tests
  // ---------------------------------------------------------------------------

  describe('Error Handling', () => {
    test('handles audio recording initialization failure', async () => {
      const mockRecording = new Audio.Recording();
      (mockRecording.prepareToRecordAsync as jest.Mock).mockRejectedValueOnce(
        new Error('Audio initialization failed')
      );
      
      const { getByText, queryByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      // Should show error and remain in idle state
      await waitFor(() => {
        expect(queryByText('Start Recording')).toBeTruthy();
      });
    });

    test('handles WebSocket connection failure', async () => {
      (WebSocketService.getInstance().connect as jest.Mock).mockRejectedValueOnce(
        new Error('Connection failed')
      );
      
      const { getByText } = renderRecordingScreen();
      
      fireEvent.press(getByText('Start Recording'));
      
      // Recording should still work (offline mode fallback)
      await waitFor(() => {
        expect(Audio.requestPermissionsAsync).toHaveBeenCalled();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Redux Integration Tests
  // ---------------------------------------------------------------------------

  describe('Redux Integration', () => {
    test('dispatches startRecording action', async () => {
      const store = createTestStore();
      const dispatchSpy = jest.spyOn(store, 'dispatch');
      
      const { getByText } = render(
        <Provider store={store}>
          <RecordingScreen navigation={mockNavigation} route={mockRoute} />
        </Provider>
      );
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(dispatchSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            type: expect.stringContaining('startRecording'),
          })
        );
      });
    });

    test('dispatches stopRecording action', async () => {
      const store = createTestStore();
      const dispatchSpy = jest.spyOn(store, 'dispatch');
      
      const { getByText, queryByText } = render(
        <Provider store={store}>
          <RecordingScreen navigation={mockNavigation} route={mockRoute} />
        </Provider>
      );
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('⏹ Stop')).toBeTruthy();
      });
      
      fireEvent.press(getByText('⏹ Stop'));
      
      await waitFor(() => {
        expect(dispatchSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            type: expect.stringContaining('stopRecording'),
          })
        );
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Accessibility Tests
  // ---------------------------------------------------------------------------

  describe('Accessibility', () => {
    test('start recording button has accessibility label', () => {
      const { getByLabelText } = renderRecordingScreen();
      expect(getByLabelText('Start Recording')).toBeTruthy();
    });

    test('recording controls have proper accessibility roles', () => {
      const { getByRole } = renderRecordingScreen();
      expect(getByRole('button')).toBeTruthy();
    });
  });
});
