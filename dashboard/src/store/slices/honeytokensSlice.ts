import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';
import type { Honeytoken, HoneytokenTrigger, HoneytokenType } from '../../types/honeytoken';
import { honeytokensApi } from '../../services/api/honeytokensApi';

interface HoneytokensState {
  items: Honeytoken[];
  triggers: HoneytokenTrigger[];
  selectedHoneytoken: Honeytoken | null;
  loading: boolean;
  error: string | null;
  stats: {
    total: number;
    active: number;
    triggered: number;
    byType: Record<HoneytokenType, number>;
  };
}

const initialState: HoneytokensState = {
  items: [],
  triggers: [],
  selectedHoneytoken: null,
  loading: false,
  error: null,
  stats: {
    total: 0,
    active: 0,
    triggered: 0,
    byType: {
      patient_record: 0,
      medication: 0,
      admin_credential: 0,
      api_key: 0,
      database: 0,
    },
  },
};

// Async thunks
export const fetchHoneytokens = createAsyncThunk(
  'honeytokens/fetchHoneytokens',
  async (_, { rejectWithValue }) => {
    try {
      const response = await honeytokensApi.getHoneytokens();
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch honeytokens');
    }
  }
);

export const fetchHoneytokenTriggers = createAsyncThunk(
  'honeytokens/fetchTriggers',
  async (honeytokenId: string | undefined, { rejectWithValue }) => {
    try {
      const response = await honeytokensApi.getTriggers(honeytokenId);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch triggers');
    }
  }
);

export const createHoneytoken = createAsyncThunk(
  'honeytokens/create',
  async (data: Partial<Honeytoken>, { rejectWithValue }) => {
    try {
      const response = await honeytokensApi.createHoneytoken(data);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to create honeytoken');
    }
  }
);

export const deactivateHoneytoken = createAsyncThunk(
  'honeytokens/deactivate',
  async (honeytokenId: string, { rejectWithValue }) => {
    try {
      await honeytokensApi.deactivateHoneytoken(honeytokenId);
      return honeytokenId;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to deactivate honeytoken');
    }
  }
);

// Calculate stats helper
const calculateStats = (items: Honeytoken[]) => {
  const byType: Record<HoneytokenType, number> = {
    patient_record: 0,
    medication: 0,
    admin_credential: 0,
    api_key: 0,
    database: 0,
  };
  
  items.forEach(item => {
    byType[item.type] = (byType[item.type] || 0) + 1;
  });
  
  return {
    total: items.length,
    active: items.filter(h => h.status === 'active').length,
    triggered: items.filter(h => h.triggerCount > 0).length,
    byType,
  };
};

const honeytokensSlice = createSlice({
  name: 'honeytokens',
  initialState,
  reducers: {
    selectHoneytoken: (state, action: PayloadAction<Honeytoken | null>) => {
      state.selectedHoneytoken = action.payload;
    },
    addTrigger: (state, action: PayloadAction<HoneytokenTrigger>) => {
      state.triggers.unshift(action.payload);
      // Update the corresponding honeytoken
      const honeytoken = state.items.find(h => h.id === action.payload.honeytokenId);
      if (honeytoken) {
        honeytoken.triggerCount += 1;
        honeytoken.lastTriggered = action.payload.timestamp;
      }
      state.stats = calculateStats(state.items);
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch honeytokens
      .addCase(fetchHoneytokens.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchHoneytokens.fulfilled, (state, action) => {
        state.loading = false;
        state.items = action.payload;
        state.stats = calculateStats(action.payload);
      })
      .addCase(fetchHoneytokens.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Fetch triggers
      .addCase(fetchHoneytokenTriggers.fulfilled, (state, action) => {
        state.triggers = action.payload;
      })
      // Create honeytoken
      .addCase(createHoneytoken.fulfilled, (state, action) => {
        state.items.push(action.payload);
        state.stats = calculateStats(state.items);
      })
      // Deactivate honeytoken
      .addCase(deactivateHoneytoken.fulfilled, (state, action) => {
        const honeytoken = state.items.find(h => h.id === action.payload);
        if (honeytoken) {
          honeytoken.status = 'inactive';
        }
        state.stats = calculateStats(state.items);
      });
  },
});

export const { selectHoneytoken, addTrigger } = honeytokensSlice.actions;

// Selectors
export const selectAllHoneytokens = (state: RootState) => state.honeytokens.items;
export const selectActiveHoneytokens = (state: RootState) => 
  state.honeytokens.items.filter(h => h.status === 'active');
export const selectHoneytokenTriggers = (state: RootState) => state.honeytokens.triggers;
export const selectSelectedHoneytoken = (state: RootState) => state.honeytokens.selectedHoneytoken;
export const selectHoneytokensLoading = (state: RootState) => state.honeytokens.loading;
export const selectHoneytokensStats = (state: RootState) => state.honeytokens.stats;

export default honeytokensSlice.reducer;
