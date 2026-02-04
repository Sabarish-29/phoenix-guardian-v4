/**
 * Phoenix Guardian Mobile - Offline Sync Integration Tests
 * 
 * End-to-end integration tests for offline-first functionality.
 * Tests complete offline workflows, sync queue management,
 * conflict resolution, and data persistence.
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import NetInfo from '@react-native-community/netinfo';

// Services
import OfflineService from '../../../mobile/src/services/OfflineService';
import WebSocketService from '../../../mobile/src/services/WebSocketService';
import EncounterService from '../../../mobile/src/services/EncounterService';
import NetworkDetector from '../../../mobile/src/utils/networkDetector';

// Redux
import encounterReducer from '../../../mobile/src/store/encounterSlice';
import offlineReducer from '../../../mobile/src/store/offlineSlice';
import authReducer from '../../../mobile/src/store/authSlice';

// =============================================================================
// MOCKS
// =============================================================================

jest.mock('@react-native-community/netinfo', () => ({
  addEventListener: jest.fn(),
  fetch: jest.fn().mockResolvedValue({
    isConnected: true,
    isInternetReachable: true,
    type: 'wifi',
  }),
}));

jest.mock('react-native-mmkv', () => ({
  MMKV: jest.fn().mockImplementation(() => ({
    set: jest.fn(),
    getString: jest.fn(),
    getBoolean: jest.fn(),
    delete: jest.fn(),
    getAllKeys: jest.fn().mockReturnValue([]),
  })),
}));

// SQLite mock
const mockDatabase = {
  encounters: new Map(),
  syncQueue: new Map(),
};

jest.mock('expo-sqlite', () => ({
  openDatabase: jest.fn().mockReturnValue({
    transaction: jest.fn((callback) => {
      const tx = {
        executeSql: jest.fn((sql, params, successCallback) => {
          if (sql.includes('INSERT')) {
            const id = params[0];
            mockDatabase.encounters.set(id, { id, ...params });
            successCallback?.(tx, { insertId: 1, rows: { _array: [] } });
          } else if (sql.includes('SELECT')) {
            const rows = Array.from(mockDatabase.encounters.values());
            successCallback?.(tx, { rows: { _array: rows, length: rows.length } });
          } else if (sql.includes('DELETE')) {
            mockDatabase.encounters.delete(params[0]);
            successCallback?.(tx, { rowsAffected: 1 });
          }
          return Promise.resolve();
        }),
      };
      callback(tx);
    }),
  }),
}));

let networkCallback: ((state: any) => void) | null = null;

const mockNetInfo = {
  addEventListener: jest.fn((callback) => {
    networkCallback = callback;
    return () => { networkCallback = null; };
  }),
  fetch: jest.fn().mockResolvedValue({
    isConnected: true,
    isInternetReachable: true,
    type: 'wifi',
  }),
};

(NetInfo.addEventListener as jest.Mock).mockImplementation(mockNetInfo.addEventListener);
(NetInfo.fetch as jest.Mock).mockImplementation(mockNetInfo.fetch);

// =============================================================================
// TEST UTILITIES
// =============================================================================

const createTestStore = (preloadedState = {}) => {
  return configureStore({
    reducer: {
      encounter: encounterReducer,
      offline: offlineReducer,
      auth: authReducer,
    },
    preloadedState: {
      auth: {
        isAuthenticated: true,
        user: { id: 'user_123', name: 'Dr. Smith', tenantId: 'tenant_456' },
        token: 'mock-jwt-token',
      },
      encounter: {
        currentEncounter: null,
        encounters: [],
        isLoading: false,
        error: null,
      },
      offline: {
        isOnline: true,
        pendingSync: [],
        syncInProgress: false,
        lastSyncTime: null,
      },
      ...preloadedState,
    },
  });
};

const simulateOffline = () => {
  act(() => {
    networkCallback?.({
      isConnected: false,
      isInternetReachable: false,
      type: 'none',
    });
  });
};

const simulateOnline = () => {
  act(() => {
    networkCallback?.({
      isConnected: true,
      isInternetReachable: true,
      type: 'wifi',
    });
  });
};

// =============================================================================
// TESTS
// =============================================================================

describe('Offline Sync Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockDatabase.encounters.clear();
    mockDatabase.syncQueue.clear();
  });

  // ---------------------------------------------------------------------------
  // Offline Detection Tests
  // ---------------------------------------------------------------------------

  describe('Offline Detection', () => {
    test('detects network state change to offline', async () => {
      const store = createTestStore();
      
      await act(async () => {
        await NetworkDetector.initialize?.();
      });
      
      simulateOffline();
      
      await waitFor(() => {
        expect(NetworkDetector.isOnlineSync()).toBe(false);
      });
    });

    test('detects network state change to online', async () => {
      const store = createTestStore({
        offline: { isOnline: false, pendingSync: [], syncInProgress: false },
      });
      
      simulateOnline();
      
      await waitFor(() => {
        expect(NetworkDetector.isOnlineSync()).toBe(true);
      });
    });

    test('handles intermittent connectivity', async () => {
      let connectionChanges = 0;
      
      const unsubscribe = NetworkDetector.onChange?.((isOnline) => {
        connectionChanges++;
      });
      
      simulateOffline();
      simulateOnline();
      simulateOffline();
      simulateOnline();
      
      expect(connectionChanges).toBeGreaterThanOrEqual(4);
      unsubscribe?.();
    });
  });

  // ---------------------------------------------------------------------------
  // Offline Data Persistence Tests
  // ---------------------------------------------------------------------------

  describe('Offline Data Persistence', () => {
    test('saves encounter to local storage when offline', async () => {
      const encounter = {
        id: 'encounter_offline_1',
        patientId: 'patient_123',
        soapNote: {
          subjective: 'Offline subjective',
          objective: 'Offline objective',
          assessment: 'Offline assessment',
          plan: 'Offline plan',
        },
        audioUri: '/path/to/audio.m4a',
        createdAt: new Date().toISOString(),
      };
      
      await OfflineService.saveEncounter(encounter);
      
      const savedEncounters = await OfflineService.getPendingEncounters();
      expect(savedEncounters).toContainEqual(expect.objectContaining({
        id: 'encounter_offline_1',
      }));
    });

    test('preserves audio file reference offline', async () => {
      const encounter = {
        id: 'encounter_audio_1',
        patientId: 'patient_123',
        audioUri: 'file:///data/audio/recording.m4a',
        soapNote: null,
        status: 'recording_complete',
      };
      
      await OfflineService.saveEncounter(encounter);
      
      const savedEncounters = await OfflineService.getPendingEncounters();
      const saved = savedEncounters.find(e => e.id === 'encounter_audio_1');
      expect(saved?.audioUri).toBe('file:///data/audio/recording.m4a');
    });

    test('handles large audio files offline', async () => {
      const largeEncounter = {
        id: 'encounter_large_audio',
        patientId: 'patient_123',
        audioUri: 'file:///data/audio/large_recording.m4a',
        audioSize: 50 * 1024 * 1024, // 50MB
        duration: 3600, // 1 hour
        soapNote: null,
      };
      
      await OfflineService.saveEncounter(largeEncounter);
      
      const saved = await OfflineService.getEncounter('encounter_large_audio');
      expect(saved).toBeTruthy();
    });

    test('retrieves encounters in creation order', async () => {
      await OfflineService.saveEncounter({ id: 'enc_1', createdAt: '2026-01-01T10:00:00Z' });
      await OfflineService.saveEncounter({ id: 'enc_2', createdAt: '2026-01-01T11:00:00Z' });
      await OfflineService.saveEncounter({ id: 'enc_3', createdAt: '2026-01-01T09:00:00Z' });
      
      const encounters = await OfflineService.getPendingEncounters();
      // Should be ordered by creation time
      expect(encounters.map(e => e.id)).toEqual(['enc_3', 'enc_1', 'enc_2']);
    });
  });

  // ---------------------------------------------------------------------------
  // Sync Queue Management Tests
  // ---------------------------------------------------------------------------

  describe('Sync Queue Management', () => {
    test('adds encounter to sync queue when created offline', async () => {
      simulateOffline();
      
      const encounter = {
        id: 'encounter_queued_1',
        patientId: 'patient_123',
        soapNote: { subjective: 'Test' },
      };
      
      await OfflineService.saveEncounter(encounter);
      
      const queue = await OfflineService.getSyncQueue();
      expect(queue).toContainEqual(expect.objectContaining({
        type: 'create_encounter',
        encounterId: 'encounter_queued_1',
      }));
    });

    test('queues updates separately from creates', async () => {
      // First create
      await OfflineService.saveEncounter({
        id: 'encounter_update_test',
        soapNote: { subjective: 'Original' },
      });
      
      simulateOffline();
      
      // Then update
      await OfflineService.updateEncounter('encounter_update_test', {
        soapNote: { subjective: 'Updated' },
      });
      
      const queue = await OfflineService.getSyncQueue();
      const updateItem = queue.find(
        q => q.type === 'update_encounter' && q.encounterId === 'encounter_update_test'
      );
      expect(updateItem).toBeTruthy();
    });

    test('merges multiple updates to same encounter', async () => {
      simulateOffline();
      
      await OfflineService.updateEncounter('enc_merge', { subjective: 'Update 1' });
      await OfflineService.updateEncounter('enc_merge', { objective: 'Update 2' });
      await OfflineService.updateEncounter('enc_merge', { assessment: 'Update 3' });
      
      const queue = await OfflineService.getSyncQueue();
      const updates = queue.filter(
        q => q.type === 'update_encounter' && q.encounterId === 'enc_merge'
      );
      
      // Should merge into single update
      expect(updates.length).toBe(1);
      expect(updates[0].data).toEqual({
        subjective: 'Update 1',
        objective: 'Update 2',
        assessment: 'Update 3',
      });
    });

    test('preserves queue order for different encounters', async () => {
      simulateOffline();
      
      await OfflineService.saveEncounter({ id: 'enc_order_1' });
      await OfflineService.saveEncounter({ id: 'enc_order_2' });
      await OfflineService.saveEncounter({ id: 'enc_order_3' });
      
      const queue = await OfflineService.getSyncQueue();
      const createItems = queue.filter(q => q.type === 'create_encounter');
      
      expect(createItems[0].encounterId).toBe('enc_order_1');
      expect(createItems[1].encounterId).toBe('enc_order_2');
      expect(createItems[2].encounterId).toBe('enc_order_3');
    });

    test('removes item from queue after successful sync', async () => {
      await OfflineService.saveEncounter({ id: 'enc_to_sync', soapNote: {} });
      
      const queueBefore = await OfflineService.getSyncQueue();
      expect(queueBefore.length).toBeGreaterThan(0);
      
      simulateOnline();
      await OfflineService.syncQueue();
      
      const queueAfter = await OfflineService.getSyncQueue();
      expect(queueAfter.find(q => q.encounterId === 'enc_to_sync')).toBeUndefined();
    });
  });

  // ---------------------------------------------------------------------------
  // Sync Execution Tests
  // ---------------------------------------------------------------------------

  describe('Sync Execution', () => {
    test('syncs queue when coming online', async () => {
      const syncSpy = jest.spyOn(OfflineService, 'syncQueue');
      
      simulateOffline();
      await OfflineService.saveEncounter({ id: 'enc_sync_on_online' });
      
      simulateOnline();
      
      await waitFor(() => {
        expect(syncSpy).toHaveBeenCalled();
      });
    });

    test('syncs in correct order (FIFO)', async () => {
      const syncOrder: string[] = [];
      
      jest.spyOn(EncounterService, 'syncEncounter').mockImplementation(
        async (enc) => {
          syncOrder.push(enc.id);
          return { success: true };
        }
      );
      
      await OfflineService.saveEncounter({ id: 'fifo_1' });
      await OfflineService.saveEncounter({ id: 'fifo_2' });
      await OfflineService.saveEncounter({ id: 'fifo_3' });
      
      await OfflineService.syncQueue();
      
      expect(syncOrder).toEqual(['fifo_1', 'fifo_2', 'fifo_3']);
    });

    test('continues sync after single item failure', async () => {
      const syncedItems: string[] = [];
      
      jest.spyOn(EncounterService, 'syncEncounter').mockImplementation(
        async (enc) => {
          if (enc.id === 'fail_item') {
            throw new Error('Sync failed');
          }
          syncedItems.push(enc.id);
          return { success: true };
        }
      );
      
      await OfflineService.saveEncounter({ id: 'item_1' });
      await OfflineService.saveEncounter({ id: 'fail_item' });
      await OfflineService.saveEncounter({ id: 'item_3' });
      
      await OfflineService.syncQueue();
      
      // Should sync items 1 and 3, skip fail_item
      expect(syncedItems).toContain('item_1');
      expect(syncedItems).toContain('item_3');
    });

    test('retries failed items with exponential backoff', async () => {
      jest.useFakeTimers();
      
      let attempts = 0;
      jest.spyOn(EncounterService, 'syncEncounter').mockImplementation(
        async () => {
          attempts++;
          if (attempts < 3) {
            throw new Error('Temporary failure');
          }
          return { success: true };
        }
      );
      
      await OfflineService.saveEncounter({ id: 'retry_item' });
      await OfflineService.syncQueue();
      
      // First attempt
      expect(attempts).toBe(1);
      
      // Wait for backoff and retry
      await act(async () => {
        jest.advanceTimersByTime(1000); // 1s backoff
      });
      
      await OfflineService.syncQueue();
      expect(attempts).toBe(2);
      
      await act(async () => {
        jest.advanceTimersByTime(2000); // 2s backoff
      });
      
      await OfflineService.syncQueue();
      expect(attempts).toBe(3);
      
      jest.useRealTimers();
    });

    test('uploads audio chunk by chunk for large files', async () => {
      const uploadedChunks: number[] = [];
      
      jest.spyOn(EncounterService, 'uploadAudioChunk').mockImplementation(
        async (encId, chunkIndex) => {
          uploadedChunks.push(chunkIndex);
          return { success: true };
        }
      );
      
      await OfflineService.saveEncounter({
        id: 'chunked_upload',
        audioUri: 'file:///audio.m4a',
        audioSize: 10 * 1024 * 1024, // 10MB
        chunkSize: 1 * 1024 * 1024, // 1MB chunks
      });
      
      await OfflineService.syncQueue();
      
      expect(uploadedChunks.length).toBe(10);
    });
  });

  // ---------------------------------------------------------------------------
  // Conflict Resolution Tests
  // ---------------------------------------------------------------------------

  describe('Conflict Resolution', () => {
    test('detects conflict when server version is newer', async () => {
      const localEncounter = {
        id: 'conflict_enc',
        version: 1,
        updatedAt: '2026-01-01T10:00:00Z',
        soapNote: { subjective: 'Local edit' },
      };
      
      jest.spyOn(EncounterService, 'getServerVersion').mockResolvedValue({
        id: 'conflict_enc',
        version: 2,
        updatedAt: '2026-01-01T11:00:00Z',
        soapNote: { subjective: 'Server edit' },
      });
      
      const result = await OfflineService.checkForConflict(localEncounter);
      
      expect(result.hasConflict).toBe(true);
      expect(result.serverVersion).toBe(2);
    });

    test('resolves conflict with local-wins strategy', async () => {
      const localEncounter = {
        id: 'conflict_local_wins',
        soapNote: { subjective: 'Local preferred' },
      };
      
      const result = await OfflineService.resolveConflict(
        localEncounter,
        { soapNote: { subjective: 'Server version' } },
        'local'
      );
      
      expect(result.soapNote.subjective).toBe('Local preferred');
    });

    test('resolves conflict with server-wins strategy', async () => {
      const localEncounter = {
        id: 'conflict_server_wins',
        soapNote: { subjective: 'Local version' },
      };
      
      const result = await OfflineService.resolveConflict(
        localEncounter,
        { soapNote: { subjective: 'Server preferred' } },
        'server'
      );
      
      expect(result.soapNote.subjective).toBe('Server preferred');
    });

    test('creates merged version for manual resolution', async () => {
      const localEncounter = {
        id: 'conflict_merge',
        soapNote: { 
          subjective: 'Local subjective',
          objective: 'Shared objective',
        },
      };
      
      const serverEncounter = {
        soapNote: {
          subjective: 'Server subjective',
          objective: 'Shared objective',
        },
      };
      
      const merged = await OfflineService.createMergedVersion(
        localEncounter,
        serverEncounter
      );
      
      expect(merged.conflicts).toContain('subjective');
      expect(merged.shared).toContain('objective');
    });
  });

  // ---------------------------------------------------------------------------
  // Storage Limits Tests
  // ---------------------------------------------------------------------------

  describe('Storage Limits', () => {
    test('warns when storage is near capacity', async () => {
      jest.spyOn(OfflineService, 'getStorageUsage').mockResolvedValue({
        used: 450 * 1024 * 1024, // 450MB
        total: 500 * 1024 * 1024, // 500MB
        percentage: 90,
      });
      
      const status = await OfflineService.checkStorageStatus();
      
      expect(status.warning).toBe(true);
      expect(status.message).toContain('storage almost full');
    });

    test('cleans up old synced encounters when storage full', async () => {
      jest.spyOn(OfflineService, 'getStorageUsage').mockResolvedValue({
        used: 495 * 1024 * 1024,
        total: 500 * 1024 * 1024,
        percentage: 99,
      });
      
      const cleanupSpy = jest.spyOn(OfflineService, 'cleanupSyncedEncounters');
      
      await OfflineService.ensureStorageAvailable(10 * 1024 * 1024);
      
      expect(cleanupSpy).toHaveBeenCalled();
    });

    test('prioritizes pending sync items during cleanup', async () => {
      const deletedIds: string[] = [];
      
      jest.spyOn(OfflineService, 'deleteEncounter').mockImplementation(
        async (id) => {
          deletedIds.push(id);
        }
      );
      
      // Add synced and unsynced encounters
      await OfflineService.saveEncounter({ id: 'synced_1', syncStatus: 'synced' });
      await OfflineService.saveEncounter({ id: 'pending_1', syncStatus: 'pending' });
      await OfflineService.saveEncounter({ id: 'synced_2', syncStatus: 'synced' });
      
      await OfflineService.cleanupSyncedEncounters();
      
      // Should only delete synced items
      expect(deletedIds).toContain('synced_1');
      expect(deletedIds).toContain('synced_2');
      expect(deletedIds).not.toContain('pending_1');
    });
  });

  // ---------------------------------------------------------------------------
  // Sync Status Tracking Tests
  // ---------------------------------------------------------------------------

  describe('Sync Status Tracking', () => {
    test('tracks sync progress percentage', async () => {
      const progressUpdates: number[] = [];
      
      OfflineService.onSyncProgress?.((progress) => {
        progressUpdates.push(progress);
      });
      
      await OfflineService.saveEncounter({ id: 'prog_1' });
      await OfflineService.saveEncounter({ id: 'prog_2' });
      await OfflineService.saveEncounter({ id: 'prog_3' });
      
      await OfflineService.syncQueue();
      
      expect(progressUpdates).toContain(33);
      expect(progressUpdates).toContain(66);
      expect(progressUpdates).toContain(100);
    });

    test('reports sync completion time', async () => {
      await OfflineService.saveEncounter({ id: 'time_test' });
      
      const startTime = Date.now();
      await OfflineService.syncQueue();
      const endTime = Date.now();
      
      const status = await OfflineService.getSyncStatus();
      
      expect(status.lastSyncTime).toBeGreaterThanOrEqual(startTime);
      expect(status.lastSyncTime).toBeLessThanOrEqual(endTime);
    });

    test('tracks individual item sync status', async () => {
      await OfflineService.saveEncounter({ id: 'status_track' });
      
      let status = await OfflineService.getEncounterSyncStatus('status_track');
      expect(status).toBe('pending');
      
      await OfflineService.syncQueue();
      
      status = await OfflineService.getEncounterSyncStatus('status_track');
      expect(status).toBe('synced');
    });
  });
});
