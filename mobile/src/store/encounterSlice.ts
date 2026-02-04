/**
 * Phoenix Guardian Mobile - Week 23-24
 * Encounter Slice: Redux state for encounter management.
 * 
 * Features:
 * - Encounter list management
 * - Active encounter tracking
 * - SOAP note state
 * - Recording status
 * - Real-time updates
 */

import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Types
export type EncounterStatus = 
  | 'recording'
  | 'processing'
  | 'draft'
  | 'review'
  | 'approved'
  | 'submitted'
  | 'error';

export interface SOAPSection {
  key: 'subjective' | 'objective' | 'assessment' | 'plan';
  title: string;
  content: string;
  originalContent: string;
  confidence: number;
  lastModified?: string;
}

export interface Encounter {
  id: string;
  patientId: string;
  patientName: string;
  patientMRN: string;
  encounterType: string;
  status: EncounterStatus;
  startTime: string;
  endTime?: string;
  duration?: number;
  sections: SOAPSection[];
  aiConfidence: number;
  wordCount: number;
  physicianEdits: number;
  ehrConfirmationId?: string;
  lastModified: string;
  isOffline: boolean;
}

export interface RecordingState {
  isRecording: boolean;
  isPaused: boolean;
  duration: number;
  audioLevel: number;
  transcript: string;
}

interface EncounterState {
  encounters: Encounter[];
  activeEncounterId: string | null;
  recording: RecordingState;
  isLoading: boolean;
  isSyncing: boolean;
  error: string | null;
  lastFetchedAt: string | null;
  filter: 'all' | 'today' | 'pending' | 'completed';
}

// Initial state
const initialState: EncounterState = {
  encounters: [],
  activeEncounterId: null,
  recording: {
    isRecording: false,
    isPaused: false,
    duration: 0,
    audioLevel: 0,
    transcript: '',
  },
  isLoading: false,
  isSyncing: false,
  error: null,
  lastFetchedAt: null,
  filter: 'all',
};

// Async thunks
export const fetchEncounters = createAsyncThunk(
  'encounters/fetch',
  async (_, { rejectWithValue }) => {
    try {
      // In production, fetch from API
      await new Promise(resolve => setTimeout(resolve, 500));

      // Mock data
      const encounters: Encounter[] = [
        {
          id: 'enc_001',
          patientId: 'P12345',
          patientName: 'John Smith',
          patientMRN: 'MRN-2024-12345',
          encounterType: 'Office Visit',
          status: 'draft',
          startTime: new Date(Date.now() - 3600000).toISOString(),
          endTime: new Date(Date.now() - 3300000).toISOString(),
          duration: 300,
          sections: [],
          aiConfidence: 0.93,
          wordCount: 342,
          physicianEdits: 0,
          lastModified: new Date().toISOString(),
          isOffline: false,
        },
        {
          id: 'enc_002',
          patientId: 'P12346',
          patientName: 'Jane Doe',
          patientMRN: 'MRN-2024-12346',
          encounterType: 'Follow-up',
          status: 'review',
          startTime: new Date(Date.now() - 7200000).toISOString(),
          endTime: new Date(Date.now() - 6900000).toISOString(),
          duration: 300,
          sections: [],
          aiConfidence: 0.88,
          wordCount: 256,
          physicianEdits: 2,
          lastModified: new Date().toISOString(),
          isOffline: false,
        },
      ];

      return encounters;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch encounters');
    }
  }
);

export const createEncounter = createAsyncThunk<Encounter, { patientId: string; patientName: string; encounterType: string }>(
  'encounters/create',
  async (data, { rejectWithValue }) => {
    try {
      // In production, create via API
      await new Promise(resolve => setTimeout(resolve, 300));

      const encounter: Encounter = {
        id: `enc_${Date.now()}`,
        patientId: data.patientId,
        patientName: data.patientName,
        patientMRN: `MRN-${data.patientId}`,
        encounterType: data.encounterType,
        status: 'recording',
        startTime: new Date().toISOString(),
        sections: [],
        aiConfidence: 0,
        wordCount: 0,
        physicianEdits: 0,
        lastModified: new Date().toISOString(),
        isOffline: false,
      };

      return encounter;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to create encounter');
    }
  }
);

export const submitEncounter = createAsyncThunk<{ encounterId: string; ehrConfirmationId: string }, string>(
  'encounters/submit',
  async (encounterId, { rejectWithValue }) => {
    try {
      // In production, submit to EHR via API
      await new Promise(resolve => setTimeout(resolve, 1500));

      return {
        encounterId,
        ehrConfirmationId: `EHR-${Date.now().toString(36).toUpperCase()}`,
      };
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to submit encounter');
    }
  }
);

export const syncOfflineEncounters = createAsyncThunk(
  'encounters/syncOffline',
  async (_, { getState, rejectWithValue }) => {
    try {
      const state = getState() as { encounters: EncounterState };
      const offlineEncounters = state.encounters.encounters.filter(e => e.isOffline);

      // In production, sync each offline encounter
      await new Promise(resolve => setTimeout(resolve, 1000));

      return offlineEncounters.map(e => e.id);
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to sync offline encounters');
    }
  }
);

// Slice
const encounterSlice = createSlice({
  name: 'encounters',
  initialState,
  reducers: {
    // Recording actions
    startRecording: (state, action: PayloadAction<string>) => {
      state.activeEncounterId = action.payload;
      state.recording = {
        isRecording: true,
        isPaused: false,
        duration: 0,
        audioLevel: 0,
        transcript: '',
      };
    },
    pauseRecording: (state) => {
      state.recording.isPaused = true;
    },
    resumeRecording: (state) => {
      state.recording.isPaused = false;
    },
    stopRecording: (state) => {
      state.recording.isRecording = false;
      state.recording.isPaused = false;
      
      // Update encounter status
      const encounter = state.encounters.find(e => e.id === state.activeEncounterId);
      if (encounter) {
        encounter.status = 'processing';
        encounter.endTime = new Date().toISOString();
        encounter.duration = state.recording.duration;
      }
    },
    updateRecordingDuration: (state, action: PayloadAction<number>) => {
      state.recording.duration = action.payload;
    },
    updateAudioLevel: (state, action: PayloadAction<number>) => {
      state.recording.audioLevel = action.payload;
    },
    updateTranscript: (state, action: PayloadAction<string>) => {
      state.recording.transcript = action.payload;
    },

    // SOAP section updates (from WebSocket)
    updateSOAPSection: (state, action: PayloadAction<{ encounterId: string; section: SOAPSection }>) => {
      const encounter = state.encounters.find(e => e.id === action.payload.encounterId);
      if (encounter) {
        const sectionIndex = encounter.sections.findIndex(s => s.key === action.payload.section.key);
        if (sectionIndex >= 0) {
          encounter.sections[sectionIndex] = action.payload.section;
        } else {
          encounter.sections.push(action.payload.section);
        }
        encounter.lastModified = new Date().toISOString();
      }
    },
    completeSOAPGeneration: (state, action: PayloadAction<string>) => {
      const encounter = state.encounters.find(e => e.id === action.payload);
      if (encounter) {
        encounter.status = 'draft';
        encounter.lastModified = new Date().toISOString();
      }
    },

    // Encounter updates
    updateEncounterStatus: (state, action: PayloadAction<{ encounterId: string; status: EncounterStatus }>) => {
      const encounter = state.encounters.find(e => e.id === action.payload.encounterId);
      if (encounter) {
        encounter.status = action.payload.status;
        encounter.lastModified = new Date().toISOString();
      }
    },
    updateEncounterSection: (state, action: PayloadAction<{ 
      encounterId: string; 
      sectionKey: string; 
      content: string 
    }>) => {
      const encounter = state.encounters.find(e => e.id === action.payload.encounterId);
      if (encounter) {
        const section = encounter.sections.find(s => s.key === action.payload.sectionKey);
        if (section) {
          section.content = action.payload.content;
          section.lastModified = new Date().toISOString();
          encounter.physicianEdits += 1;
          encounter.lastModified = new Date().toISOString();
        }
      }
    },
    markEncounterOffline: (state, action: PayloadAction<string>) => {
      const encounter = state.encounters.find(e => e.id === action.payload);
      if (encounter) {
        encounter.isOffline = true;
      }
    },

    // Filter
    setFilter: (state, action: PayloadAction<EncounterState['filter']>) => {
      state.filter = action.payload;
    },

    // Clear
    clearActiveEncounter: (state) => {
      state.activeEncounterId = null;
      state.recording = initialState.recording;
    },
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    // Fetch encounters
    builder.addCase(fetchEncounters.pending, (state) => {
      state.isLoading = true;
      state.error = null;
    });
    builder.addCase(fetchEncounters.fulfilled, (state, action) => {
      state.isLoading = false;
      state.encounters = action.payload;
      state.lastFetchedAt = new Date().toISOString();
    });
    builder.addCase(fetchEncounters.rejected, (state, action) => {
      state.isLoading = false;
      state.error = action.payload as string;
    });

    // Create encounter
    builder.addCase(createEncounter.pending, (state) => {
      state.isLoading = true;
    });
    builder.addCase(createEncounter.fulfilled, (state, action) => {
      state.isLoading = false;
      state.encounters.unshift(action.payload);
      state.activeEncounterId = action.payload.id;
    });
    builder.addCase(createEncounter.rejected, (state, action) => {
      state.isLoading = false;
      state.error = action.payload as string;
    });

    // Submit encounter
    builder.addCase(submitEncounter.pending, (state) => {
      state.isLoading = true;
    });
    builder.addCase(submitEncounter.fulfilled, (state, action) => {
      state.isLoading = false;
      const encounter = state.encounters.find(e => e.id === action.payload.encounterId);
      if (encounter) {
        encounter.status = 'submitted';
        encounter.ehrConfirmationId = action.payload.ehrConfirmationId;
        encounter.lastModified = new Date().toISOString();
      }
    });
    builder.addCase(submitEncounter.rejected, (state, action) => {
      state.isLoading = false;
      state.error = action.payload as string;
    });

    // Sync offline
    builder.addCase(syncOfflineEncounters.pending, (state) => {
      state.isSyncing = true;
    });
    builder.addCase(syncOfflineEncounters.fulfilled, (state, action) => {
      state.isSyncing = false;
      action.payload.forEach(id => {
        const encounter = state.encounters.find(e => e.id === id);
        if (encounter) {
          encounter.isOffline = false;
        }
      });
    });
    builder.addCase(syncOfflineEncounters.rejected, (state) => {
      state.isSyncing = false;
    });
  },
});

export const {
  startRecording,
  pauseRecording,
  resumeRecording,
  stopRecording,
  updateRecordingDuration,
  updateAudioLevel,
  updateTranscript,
  updateSOAPSection,
  completeSOAPGeneration,
  updateEncounterStatus,
  updateEncounterSection,
  markEncounterOffline,
  setFilter,
  clearActiveEncounter,
  clearError,
} = encounterSlice.actions;

export default encounterSlice.reducer;

// Selectors
export const selectEncounters = (state: { encounters: EncounterState }) => state.encounters.encounters;
export const selectActiveEncounter = (state: { encounters: EncounterState }) => {
  const { encounters, activeEncounterId } = state.encounters;
  return encounters.find(e => e.id === activeEncounterId) || null;
};
export const selectRecordingState = (state: { encounters: EncounterState }) => state.encounters.recording;
export const selectEncounterById = (id: string) => (state: { encounters: EncounterState }) => 
  state.encounters.encounters.find(e => e.id === id);
export const selectFilteredEncounters = (state: { encounters: EncounterState }) => {
  const { encounters, filter } = state.encounters;
  const today = new Date().toDateString();

  switch (filter) {
    case 'today':
      return encounters.filter(e => new Date(e.startTime).toDateString() === today);
    case 'pending':
      return encounters.filter(e => ['draft', 'review'].includes(e.status));
    case 'completed':
      return encounters.filter(e => e.status === 'submitted');
    default:
      return encounters;
  }
};
export const selectOfflineEncounters = (state: { encounters: EncounterState }) => 
  state.encounters.encounters.filter(e => e.isOffline);
export const selectEncounterLoading = (state: { encounters: EncounterState }) => state.encounters.isLoading;
export const selectEncounterError = (state: { encounters: EncounterState }) => state.encounters.error;
