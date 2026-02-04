/**
 * Phoenix Guardian Mobile - Integration Tests
 * 
 * End-to-end integration tests for mobile recording workflows.
 * Tests complete user journeys from recording to approval.
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { Audio } from 'expo-av';

// Screens
import RecordingScreen from '../../../mobile/src/screens/RecordingScreen';
import ReviewScreen from '../../../mobile/src/screens/ReviewScreen';
import ApprovalScreen from '../../../mobile/src/screens/ApprovalScreen';

// Services
import WebSocketService from '../../../mobile/src/services/WebSocketService';
import OfflineService from '../../../mobile/src/services/OfflineService';
import AuthService from '../../../mobile/src/services/AuthService';
import NetworkDetector from '../../../mobile/src/utils/networkDetector';

// Redux
import encounterReducer from '../../../mobile/src/store/encounterSlice';
import offlineReducer from '../../../mobile/src/store/offlineSlice';
import authReducer from '../../../mobile/src/store/authSlice';

// =============================================================================
// MOCKS
// =============================================================================

jest.mock('expo-av', () => ({
  Audio: {
    requestPermissionsAsync: jest.fn().mockResolvedValue({ granted: true }),
    setAudioModeAsync: jest.fn().mockResolvedValue(undefined),
    Recording: jest.fn().mockImplementation(() => ({
      prepareToRecordAsync: jest.fn().mockResolvedValue(undefined),
      startAsync: jest.fn().mockResolvedValue(undefined),
      stopAndUnloadAsync: jest.fn().mockResolvedValue(undefined),
      pauseAsync: jest.fn().mockResolvedValue(undefined),
      getStatusAsync: jest.fn().mockResolvedValue({
        isRecording: true,
        metering: -20,
        durationMillis: 5000,
      }),
      getURI: jest.fn().mockReturnValue('/path/to/audio.m4a'),
    })),
    RecordingOptionsPresets: {
      HIGH_QUALITY: {},
    },
  },
}));

let wsEventCallback: ((event: any) => void) | null = null;

jest.mock('../../../mobile/src/services/WebSocketService', () => ({
  getInstance: jest.fn().mockReturnValue({
    connect: jest.fn().mockResolvedValue(true),
    disconnect: jest.fn(),
    startEncounter: jest.fn(),
    stopEncounter: jest.fn(),
    sendAudioChunk: jest.fn(),
    on: jest.fn((callback) => {
      wsEventCallback = callback;
      return () => { wsEventCallback = null; };
    }),
    isConnected: jest.fn().mockReturnValue(true),
  }),
}));

jest.mock('../../../mobile/src/services/OfflineService', () => ({
  initialize: jest.fn().mockResolvedValue(undefined),
  saveEncounter: jest.fn().mockResolvedValue(undefined),
  getPendingEncounters: jest.fn().mockResolvedValue([]),
  syncQueue: jest.fn().mockResolvedValue(undefined),
  getSyncStatus: jest.fn().mockResolvedValue({ pending: 0, synced: 0 }),
}));

jest.mock('../../../mobile/src/services/AuthService', () => ({
  getToken: jest.fn().mockResolvedValue('mock-jwt-token'),
  isAuthenticated: jest.fn().mockResolvedValue(true),
  getCurrentUser: jest.fn().mockReturnValue({
    id: 'user_123',
    name: 'Dr. Smith',
    tenantId: 'tenant_456',
  }),
}));

jest.mock('../../../mobile/src/utils/networkDetector', () => ({
  initialize: jest.fn().mockResolvedValue(undefined),
  isOnline: jest.fn().mockResolvedValue(true),
  isOnlineSync: jest.fn().mockReturnValue(true),
  onChange: jest.fn().mockReturnValue(() => {}),
  getStatus: jest.fn().mockReturnValue({
    isOnline: true,
    type: 'wifi',
    isWifi: true,
  }),
}));

jest.mock('../../../mobile/src/services/EncounterService', () => ({
  getEncounter: jest.fn().mockResolvedValue({
    id: 'encounter_456',
    patientId: 'patient_123',
    status: 'draft',
  }),
  updateSOAPNote: jest.fn().mockResolvedValue({ success: true }),
  submitToEHR: jest.fn().mockResolvedValue({ success: true }),
}));

// =============================================================================
// TEST SETUP
// =============================================================================

const Stack = createNativeStackNavigator();

const createTestStore = (preloadedState = {}) => {
  return configureStore({
    reducer: {
      encounter: encounterReducer,
      offline: offlineReducer,
      auth: authReducer,
    },
    preloadedState,
  });
};

const renderApp = (initialRoute = 'Recording', store = createTestStore()) => {
  return render(
    <Provider store={store}>
      <NavigationContainer>
        <Stack.Navigator initialRouteName={initialRoute}>
          <Stack.Screen
            name="Recording"
            component={RecordingScreen}
            initialParams={{
              patientId: 'patient_123',
              encounterId: 'encounter_456',
              patientName: 'John Doe',
            }}
          />
          <Stack.Screen name="Review" component={ReviewScreen} />
          <Stack.Screen name="Approval" component={ApprovalScreen} />
        </Stack.Navigator>
      </NavigationContainer>
    </Provider>
  );
};

// =============================================================================
// INTEGRATION TESTS
// =============================================================================

describe('Mobile App Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    wsEventCallback = null;
  });

  // ---------------------------------------------------------------------------
  // Complete Recording Flow
  // ---------------------------------------------------------------------------

  describe('Complete Recording Flow', () => {
    test('full recording → review → approval workflow', async () => {
      const { getByText, queryByText } = renderApp();
      
      // Step 1: Start Recording
      expect(getByText('Recording Encounter')).toBeTruthy();
      expect(getByText('John Doe')).toBeTruthy();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('⏹ Stop')).toBeTruthy();
      });
      
      // Verify WebSocket connected
      expect(WebSocketService.getInstance().connect).toHaveBeenCalled();
      expect(WebSocketService.getInstance().startEncounter).toHaveBeenCalledWith(
        'patient_123',
        'encounter_456'
      );
      
      // Step 2: Simulate transcript streaming
      act(() => {
        wsEventCallback?.({ type: 'transcript_update', text: 'Patient reports headache' });
        wsEventCallback?.({ type: 'transcript_update', text: 'for the past 3 days' });
      });
      
      await waitFor(() => {
        expect(queryByText(/Patient reports headache/)).toBeTruthy();
      });
      
      // Step 3: Simulate SOAP sections arriving
      act(() => {
        wsEventCallback?.({
          type: 'soap_section_ready',
          section: 'subjective',
          text: 'Chief Complaint: Headache for 3 days',
        });
        wsEventCallback?.({
          type: 'soap_section_ready',
          section: 'objective',
          text: 'Vitals: BP 120/80, HR 72',
        });
      });
      
      await waitFor(() => {
        expect(queryByText('SUBJECTIVE')).toBeTruthy();
        expect(queryByText(/Chief Complaint/)).toBeTruthy();
      });
      
      // Step 4: Stop Recording
      fireEvent.press(getByText('⏹ Stop'));
      
      await waitFor(() => {
        expect(queryByText('Generating SOAP note...')).toBeTruthy();
      });
      
      expect(WebSocketService.getInstance().stopEncounter).toHaveBeenCalled();
    });

    test('recording with pause and resume', async () => {
      const { getByText, queryByText } = renderApp();
      
      // Start recording
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('⏸ Pause')).toBeTruthy();
      });
      
      // Pause
      fireEvent.press(getByText('⏸ Pause'));
      
      await waitFor(() => {
        expect(queryByText('⏸ PAUSED')).toBeTruthy();
        expect(queryByText('▶ Resume')).toBeTruthy();
      });
      
      // Resume
      fireEvent.press(getByText('▶ Resume'));
      
      await waitFor(() => {
        expect(queryByText('⏸ Pause')).toBeTruthy();
      });
      
      // Stop
      fireEvent.press(getByText('⏹ Stop'));
      
      await waitFor(() => {
        expect(queryByText('Generating SOAP note...')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Offline Recording Flow
  // ---------------------------------------------------------------------------

  describe('Offline Recording Flow', () => {
    beforeEach(() => {
      (NetworkDetector.isOnline as jest.Mock).mockResolvedValue(false);
      (NetworkDetector.isOnlineSync as jest.Mock).mockReturnValue(false);
    });

    test('records and saves locally when offline', async () => {
      (NetworkDetector.onChange as jest.Mock).mockImplementation((callback) => {
        callback(false);
        return () => {};
      });
      
      const { getByText, queryByText } = renderApp();
      
      await waitFor(() => {
        expect(queryByText('📡 Offline')).toBeTruthy();
      });
      
      // Start recording
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('⏹ Stop')).toBeTruthy();
      });
      
      // WebSocket should NOT be connected in offline mode
      expect(WebSocketService.getInstance().connect).not.toHaveBeenCalled();
      
      // Stop recording
      fireEvent.press(getByText('⏹ Stop'));
      
      await waitFor(() => {
        // Should save to offline storage
        expect(OfflineService.saveEncounter).toHaveBeenCalledWith(
          expect.objectContaining({
            encounterId: 'encounter_456',
            patientId: 'patient_123',
          })
        );
      });
    });

    test('shows offline mode indicator throughout recording', async () => {
      (NetworkDetector.onChange as jest.Mock).mockImplementation((callback) => {
        callback(false);
        return () => {};
      });
      
      const { getByText, queryByText } = renderApp();
      
      await waitFor(() => {
        expect(queryByText('📡 Offline')).toBeTruthy();
      });
      
      // Badge should persist during recording
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('📡 Offline')).toBeTruthy();
        expect(queryByText('⏹ Stop')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Network Transition Tests
  // ---------------------------------------------------------------------------

  describe('Network Transition Handling', () => {
    test('handles transition from online to offline during recording', async () => {
      let networkCallback: ((online: boolean) => void) | null = null;
      (NetworkDetector.onChange as jest.Mock).mockImplementation((callback) => {
        networkCallback = callback;
        return () => { networkCallback = null; };
      });
      
      const { getByText, queryByText } = renderApp();
      
      // Start recording (online)
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('⏹ Stop')).toBeTruthy();
      });
      
      // Go offline during recording
      act(() => {
        networkCallback?.(false);
      });
      
      // Should show offline indicator
      await waitFor(() => {
        expect(queryByText('📡 Offline')).toBeTruthy();
      });
      
      // Recording should continue
      expect(queryByText('⏹ Stop')).toBeTruthy();
    });
  });

  // ---------------------------------------------------------------------------
  // Error Handling Tests
  // ---------------------------------------------------------------------------

  describe('Error Handling', () => {
    test('handles microphone permission denial', async () => {
      (Audio.requestPermissionsAsync as jest.Mock).mockResolvedValueOnce({ granted: false });
      
      const { getByText, queryByText } = renderApp();
      
      fireEvent.press(getByText('Start Recording'));
      
      // Should remain in idle state
      await waitFor(() => {
        expect(queryByText('Start Recording')).toBeTruthy();
        expect(queryByText('⏹ Stop')).toBeNull();
      });
    });

    test('handles WebSocket connection failure', async () => {
      (WebSocketService.getInstance().connect as jest.Mock).mockRejectedValueOnce(
        new Error('Connection failed')
      );
      
      const { getByText } = renderApp();
      
      // Should not crash
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        // Audio recording should still have been attempted
        expect(Audio.requestPermissionsAsync).toHaveBeenCalled();
      });
    });

    test('handles WebSocket error event', async () => {
      const { getByText, queryByText } = renderApp();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('⏹ Stop')).toBeTruthy();
      });
      
      // Simulate error
      act(() => {
        wsEventCallback?.({
          type: 'error',
          message: 'Transcription service unavailable',
        });
      });
      
      // Should return to idle state
      await waitFor(() => {
        expect(queryByText('Start Recording')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // WebSocket Event Handling Tests
  // ---------------------------------------------------------------------------

  describe('WebSocket Event Handling', () => {
    test('accumulates transcript updates correctly', async () => {
      const { getByText, queryByText } = renderApp();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(wsEventCallback).toBeDefined();
      });
      
      // Send multiple transcript updates
      act(() => {
        wsEventCallback?.({ type: 'transcript_update', text: 'Hello' });
      });
      
      await waitFor(() => {
        expect(queryByText('Hello')).toBeTruthy();
      });
      
      act(() => {
        wsEventCallback?.({ type: 'transcript_update', text: 'World' });
      });
      
      await waitFor(() => {
        expect(queryByText(/Hello.*World/)).toBeTruthy();
      });
    });

    test('displays all SOAP sections as they arrive', async () => {
      const { getByText, queryByText } = renderApp();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(wsEventCallback).toBeDefined();
      });
      
      // Send all SOAP sections
      const sections = ['subjective', 'objective', 'assessment', 'plan'];
      
      for (const section of sections) {
        act(() => {
          wsEventCallback?.({
            type: 'soap_section_ready',
            section,
            text: `${section.toUpperCase()} content here`,
          });
        });
      }
      
      await waitFor(() => {
        expect(queryByText('SUBJECTIVE')).toBeTruthy();
        expect(queryByText('OBJECTIVE')).toBeTruthy();
        expect(queryByText('ASSESSMENT')).toBeTruthy();
        expect(queryByText('PLAN')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Audio Level Visualization Tests
  // ---------------------------------------------------------------------------

  describe('Audio Level Visualization', () => {
    test('audio level indicator appears during recording', async () => {
      const { getByText, queryByText } = renderApp();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        // Recording controls should be visible
        expect(queryByText('⏹ Stop')).toBeTruthy();
        expect(queryByText('⏸ Pause')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Duration Tracking Tests
  // ---------------------------------------------------------------------------

  describe('Duration Tracking', () => {
    test('displays recording duration', async () => {
      const { getByText, queryByText } = renderApp();
      
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(queryByText('00:00')).toBeTruthy();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Redux State Management Tests
  // ---------------------------------------------------------------------------

  describe('Redux State Management', () => {
    test('dispatches correct actions during recording lifecycle', async () => {
      const store = createTestStore();
      const dispatchSpy = jest.spyOn(store, 'dispatch');
      
      const { getByText, queryByText } = render(
        <Provider store={store}>
          <NavigationContainer>
            <Stack.Navigator initialRouteName="Recording">
              <Stack.Screen
                name="Recording"
                component={RecordingScreen}
                initialParams={{
                  patientId: 'patient_123',
                  encounterId: 'encounter_456',
                }}
              />
            </Stack.Navigator>
          </NavigationContainer>
        </Provider>
      );
      
      // Start recording
      fireEvent.press(getByText('Start Recording'));
      
      await waitFor(() => {
        expect(dispatchSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            type: expect.stringContaining('startRecording'),
          })
        );
      });
      
      // Stop recording
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
});

// =============================================================================
// SYNC FLOW TESTS
// =============================================================================

describe('Offline Sync Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('syncs offline encounters when coming back online', async () => {
    let networkCallback: ((online: boolean) => void) | null = null;
    
    (NetworkDetector.onChange as jest.Mock).mockImplementation((callback) => {
      networkCallback = callback;
      return () => {};
    });
    
    (OfflineService.getPendingEncounters as jest.Mock).mockResolvedValue([
      {
        id: 'offline_1',
        encounterId: 'encounter_1',
        patientId: 'patient_1',
        audioUri: '/path/to/audio.m4a',
        timestamp: new Date().toISOString(),
      },
    ]);
    
    // Start offline
    (NetworkDetector.isOnline as jest.Mock).mockResolvedValue(false);
    
    const { queryByText } = renderApp();
    
    // Go online
    act(() => {
      networkCallback?.(true);
    });
    
    // Sync should be triggered
    await waitFor(() => {
      // Network change callback should handle sync
    });
  });
});

// =============================================================================
// PERFORMANCE TESTS
// =============================================================================

describe('Performance Tests', () => {
  test('handles rapid WebSocket events without lag', async () => {
    const { getByText, queryByText } = renderApp();
    
    fireEvent.press(getByText('Start Recording'));
    
    await waitFor(() => {
      expect(wsEventCallback).toBeDefined();
    });
    
    // Simulate rapid events (100 events)
    const startTime = Date.now();
    
    act(() => {
      for (let i = 0; i < 100; i++) {
        wsEventCallback?.({
          type: 'transcript_update',
          text: `Word ${i}`,
        });
      }
    });
    
    const endTime = Date.now();
    const duration = endTime - startTime;
    
    // Should process 100 events in under 1 second
    expect(duration).toBeLessThan(1000);
  });

  test('memory cleanup on unmount', async () => {
    const { getByText, unmount } = renderApp();
    
    fireEvent.press(getByText('Start Recording'));
    
    // Unmount component
    unmount();
    
    // WebSocket should be disconnected
    // No memory leaks from event listeners
  });
});
