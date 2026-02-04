/**
 * Phoenix Guardian Mobile - Week 23-24
 * Offline Slice: Redux state for offline queue management.
 * 
 * Features:
 * - Offline queue for pending operations
 * - Sync status tracking
 * - Conflict resolution
 * - Network status
 */

import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Types
export type OperationType = 
  | 'create_encounter'
  | 'update_encounter'
  | 'submit_encounter'
  | 'upload_audio';

export type OperationStatus = 
  | 'pending'
  | 'syncing'
  | 'completed'
  | 'failed'
  | 'conflict';

export interface QueuedOperation {
  id: string;
  type: OperationType;
  encounterId: string;
  payload: any;
  status: OperationStatus;
  createdAt: string;
  attempts: number;
  lastAttemptAt?: string;
  error?: string;
  priority: number;
}

export interface SyncConflict {
  id: string;
  operationId: string;
  encounterId: string;
  localVersion: any;
  serverVersion: any;
  detectedAt: string;
  resolved: boolean;
}

interface OfflineState {
  isOnline: boolean;
  isAutoSyncEnabled: boolean;
  queue: QueuedOperation[];
  conflicts: SyncConflict[];
  isSyncing: boolean;
  lastSyncAt: string | null;
  syncProgress: {
    total: number;
    completed: number;
    failed: number;
  };
  pendingAudioUploads: number;
  storageUsedMB: number;
  maxStorageMB: number;
}

// Initial state
const initialState: OfflineState = {
  isOnline: true,
  isAutoSyncEnabled: true,
  queue: [],
  conflicts: [],
  isSyncing: false,
  lastSyncAt: null,
  syncProgress: {
    total: 0,
    completed: 0,
    failed: 0,
  },
  pendingAudioUploads: 0,
  storageUsedMB: 0,
  maxStorageMB: 500,
};

// Async thunks
export const processQueue = createAsyncThunk(
  'offline/processQueue',
  async (_, { getState, dispatch, rejectWithValue }) => {
    const state = getState() as { offline: OfflineState };
    
    if (!state.offline.isOnline) {
      return rejectWithValue('Device is offline');
    }

    const pendingOps = state.offline.queue
      .filter(op => op.status === 'pending')
      .sort((a, b) => b.priority - a.priority);

    const results: { id: string; success: boolean }[] = [];

    for (const op of pendingOps) {
      dispatch(updateOperationStatus({ id: op.id, status: 'syncing' }));

      try {
        // In production, process each operation type
        await new Promise(resolve => setTimeout(resolve, 500));

        dispatch(updateOperationStatus({ id: op.id, status: 'completed' }));
        results.push({ id: op.id, success: true });
      } catch (error: any) {
        dispatch(updateOperationStatus({ 
          id: op.id, 
          status: 'failed',
          error: error.message,
        }));
        results.push({ id: op.id, success: false });
      }
    }

    return results;
  }
);

export const resolveConflict = createAsyncThunk<string, { conflictId: string; resolution: 'local' | 'server' | 'merge' }>(
  'offline/resolveConflict',
  async ({ conflictId, resolution }, { getState, rejectWithValue }) => {
    try {
      const state = getState() as { offline: OfflineState };
      const conflict = state.offline.conflicts.find(c => c.id === conflictId);

      if (!conflict) {
        return rejectWithValue('Conflict not found');
      }

      // In production, apply resolution logic
      await new Promise(resolve => setTimeout(resolve, 500));

      return conflictId;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to resolve conflict');
    }
  }
);

export const clearCompletedOperations = createAsyncThunk(
  'offline/clearCompleted',
  async () => {
    // Clean up completed operations older than 24 hours
    await new Promise(resolve => setTimeout(resolve, 100));
    return true;
  }
);

// Slice
const offlineSlice = createSlice({
  name: 'offline',
  initialState,
  reducers: {
    // Network status
    setOnlineStatus: (state, action: PayloadAction<boolean>) => {
      state.isOnline = action.payload;
    },
    setAutoSyncEnabled: (state, action: PayloadAction<boolean>) => {
      state.isAutoSyncEnabled = action.payload;
    },

    // Queue management
    addToQueue: (state, action: PayloadAction<Omit<QueuedOperation, 'id' | 'status' | 'createdAt' | 'attempts'>>) => {
      const operation: QueuedOperation = {
        id: `op_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        status: 'pending',
        createdAt: new Date().toISOString(),
        attempts: 0,
        ...action.payload,
      };
      state.queue.push(operation);
    },
    removeFromQueue: (state, action: PayloadAction<string>) => {
      state.queue = state.queue.filter(op => op.id !== action.payload);
    },
    updateOperationStatus: (state, action: PayloadAction<{ 
      id: string; 
      status: OperationStatus; 
      error?: string 
    }>) => {
      const operation = state.queue.find(op => op.id === action.payload.id);
      if (operation) {
        operation.status = action.payload.status;
        operation.lastAttemptAt = new Date().toISOString();
        operation.attempts += 1;
        if (action.payload.error) {
          operation.error = action.payload.error;
        }
      }
    },
    retryOperation: (state, action: PayloadAction<string>) => {
      const operation = state.queue.find(op => op.id === action.payload);
      if (operation) {
        operation.status = 'pending';
        operation.error = undefined;
      }
    },
    retryAllFailed: (state) => {
      state.queue.forEach(op => {
        if (op.status === 'failed') {
          op.status = 'pending';
          op.error = undefined;
        }
      });
    },

    // Conflicts
    addConflict: (state, action: PayloadAction<Omit<SyncConflict, 'id' | 'detectedAt' | 'resolved'>>) => {
      const conflict: SyncConflict = {
        id: `conflict_${Date.now()}`,
        detectedAt: new Date().toISOString(),
        resolved: false,
        ...action.payload,
      };
      state.conflicts.push(conflict);
    },
    markConflictResolved: (state, action: PayloadAction<string>) => {
      const conflict = state.conflicts.find(c => c.id === action.payload);
      if (conflict) {
        conflict.resolved = true;
      }
    },
    removeConflict: (state, action: PayloadAction<string>) => {
      state.conflicts = state.conflicts.filter(c => c.id !== action.payload);
    },

    // Sync progress
    setSyncProgress: (state, action: PayloadAction<OfflineState['syncProgress']>) => {
      state.syncProgress = action.payload;
    },
    resetSyncProgress: (state) => {
      state.syncProgress = { total: 0, completed: 0, failed: 0 };
    },

    // Audio uploads
    incrementPendingAudioUploads: (state) => {
      state.pendingAudioUploads += 1;
    },
    decrementPendingAudioUploads: (state) => {
      state.pendingAudioUploads = Math.max(0, state.pendingAudioUploads - 1);
    },

    // Storage
    updateStorageUsed: (state, action: PayloadAction<number>) => {
      state.storageUsedMB = action.payload;
    },

    // Clear all
    clearQueue: (state) => {
      state.queue = [];
    },
    clearConflicts: (state) => {
      state.conflicts = [];
    },
  },
  extraReducers: (builder) => {
    // Process queue
    builder.addCase(processQueue.pending, (state) => {
      state.isSyncing = true;
      const pendingCount = state.queue.filter(op => op.status === 'pending').length;
      state.syncProgress = {
        total: pendingCount,
        completed: 0,
        failed: 0,
      };
    });
    builder.addCase(processQueue.fulfilled, (state, action) => {
      state.isSyncing = false;
      state.lastSyncAt = new Date().toISOString();
      
      const results = action.payload;
      state.syncProgress = {
        total: results.length,
        completed: results.filter(r => r.success).length,
        failed: results.filter(r => !r.success).length,
      };
    });
    builder.addCase(processQueue.rejected, (state) => {
      state.isSyncing = false;
    });

    // Resolve conflict
    builder.addCase(resolveConflict.fulfilled, (state, action) => {
      const conflict = state.conflicts.find(c => c.id === action.payload);
      if (conflict) {
        conflict.resolved = true;
      }
    });

    // Clear completed
    builder.addCase(clearCompletedOperations.fulfilled, (state) => {
      const cutoff = Date.now() - 24 * 60 * 60 * 1000; // 24 hours
      state.queue = state.queue.filter(
        op => op.status !== 'completed' || new Date(op.createdAt).getTime() > cutoff
      );
    });
  },
});

export const {
  setOnlineStatus,
  setAutoSyncEnabled,
  addToQueue,
  removeFromQueue,
  updateOperationStatus,
  retryOperation,
  retryAllFailed,
  addConflict,
  markConflictResolved,
  removeConflict,
  setSyncProgress,
  resetSyncProgress,
  incrementPendingAudioUploads,
  decrementPendingAudioUploads,
  updateStorageUsed,
  clearQueue,
  clearConflicts,
} = offlineSlice.actions;

export default offlineSlice.reducer;

// Selectors
export const selectIsOnline = (state: { offline: OfflineState }) => state.offline.isOnline;
export const selectQueue = (state: { offline: OfflineState }) => state.offline.queue;
export const selectPendingOperations = (state: { offline: OfflineState }) => 
  state.offline.queue.filter(op => op.status === 'pending');
export const selectFailedOperations = (state: { offline: OfflineState }) => 
  state.offline.queue.filter(op => op.status === 'failed');
export const selectConflicts = (state: { offline: OfflineState }) => 
  state.offline.conflicts.filter(c => !c.resolved);
export const selectIsSyncing = (state: { offline: OfflineState }) => state.offline.isSyncing;
export const selectSyncProgress = (state: { offline: OfflineState }) => state.offline.syncProgress;
export const selectLastSyncAt = (state: { offline: OfflineState }) => state.offline.lastSyncAt;
export const selectPendingAudioUploads = (state: { offline: OfflineState }) => state.offline.pendingAudioUploads;
export const selectStorageInfo = (state: { offline: OfflineState }) => ({
  used: state.offline.storageUsedMB,
  max: state.offline.maxStorageMB,
  percentage: (state.offline.storageUsedMB / state.offline.maxStorageMB) * 100,
});
export const selectHasPendingWork = (state: { offline: OfflineState }) => 
  state.offline.queue.some(op => op.status === 'pending') || 
  state.offline.pendingAudioUploads > 0;
