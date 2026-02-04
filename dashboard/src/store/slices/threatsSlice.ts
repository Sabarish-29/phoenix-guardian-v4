import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';
import type { Threat, ThreatSeverity, ThreatFilters } from '../../types/threat';
import { threatsApi } from '../../services/api/threatsApi';

interface ThreatsState {
  items: Threat[];
  filteredItems: Threat[];
  selectedThreat: Threat | null;
  filters: ThreatFilters;
  loading: boolean;
  error: string | null;
  lastUpdate: string | null;
  stats: {
    total: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
}

const initialState: ThreatsState = {
  items: [],
  filteredItems: [],
  selectedThreat: null,
  filters: {
    severity: [],
    attackType: [],
    timeRange: '24h',
    searchQuery: '',
  },
  loading: false,
  error: null,
  lastUpdate: null,
  stats: {
    total: 0,
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
  },
};

// Async thunks
export const fetchThreats = createAsyncThunk(
  'threats/fetchThreats',
  async (params: ThreatFilters | undefined, { rejectWithValue }) => {
    try {
      const response = await threatsApi.getThreats(params);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch threats');
    }
  }
);

export const fetchThreatById = createAsyncThunk(
  'threats/fetchThreatById',
  async (threatId: string, { rejectWithValue }) => {
    try {
      const response = await threatsApi.getThreatById(threatId);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch threat details');
    }
  }
);

export const acknowledgeThreat = createAsyncThunk(
  'threats/acknowledgeThreat',
  async (threatId: string, { rejectWithValue }) => {
    try {
      await threatsApi.acknowledgeThreat(threatId);
      return threatId;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to acknowledge threat');
    }
  }
);

// Helper function to apply filters
const applyFilters = (items: Threat[], filters: ThreatFilters): Threat[] => {
  return items.filter((threat) => {
    // Severity filter
    if (filters.severity.length > 0 && !filters.severity.includes(threat.severity)) {
      return false;
    }
    
    // Attack type filter
    if (filters.attackType.length > 0 && !filters.attackType.includes(threat.attackType)) {
      return false;
    }
    
    // Search query
    if (filters.searchQuery) {
      const query = filters.searchQuery.toLowerCase();
      const searchable = [
        threat.title,
        threat.description,
        threat.sourceIp,
        threat.targetAsset,
      ].join(' ').toLowerCase();
      
      if (!searchable.includes(query)) {
        return false;
      }
    }
    
    return true;
  });
};

// Calculate stats
const calculateStats = (items: Threat[]) => {
  return {
    total: items.length,
    critical: items.filter(t => t.severity === 'critical').length,
    high: items.filter(t => t.severity === 'high').length,
    medium: items.filter(t => t.severity === 'medium').length,
    low: items.filter(t => t.severity === 'low').length,
  };
};

const threatsSlice = createSlice({
  name: 'threats',
  initialState,
  reducers: {
    setFilters: (state, action: PayloadAction<Partial<ThreatFilters>>) => {
      state.filters = { ...state.filters, ...action.payload };
      state.filteredItems = applyFilters(state.items, state.filters);
    },
    clearFilters: (state) => {
      state.filters = initialState.filters;
      state.filteredItems = state.items;
    },
    selectThreat: (state, action: PayloadAction<Threat | null>) => {
      state.selectedThreat = action.payload;
    },
    addThreat: (state, action: PayloadAction<Threat>) => {
      // Add new threat at the beginning
      state.items.unshift(action.payload);
      state.filteredItems = applyFilters(state.items, state.filters);
      state.stats = calculateStats(state.items);
      state.lastUpdate = new Date().toISOString();
    },
    updateThreat: (state, action: PayloadAction<Threat>) => {
      const index = state.items.findIndex(t => t.id === action.payload.id);
      if (index !== -1) {
        state.items[index] = action.payload;
        state.filteredItems = applyFilters(state.items, state.filters);
        state.stats = calculateStats(state.items);
      }
    },
    removeThreat: (state, action: PayloadAction<string>) => {
      state.items = state.items.filter(t => t.id !== action.payload);
      state.filteredItems = applyFilters(state.items, state.filters);
      state.stats = calculateStats(state.items);
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch threats
      .addCase(fetchThreats.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchThreats.fulfilled, (state, action) => {
        state.loading = false;
        state.items = action.payload;
        state.filteredItems = applyFilters(action.payload, state.filters);
        state.stats = calculateStats(action.payload);
        state.lastUpdate = new Date().toISOString();
      })
      .addCase(fetchThreats.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Fetch threat by ID
      .addCase(fetchThreatById.fulfilled, (state, action) => {
        state.selectedThreat = action.payload;
      })
      // Acknowledge threat
      .addCase(acknowledgeThreat.fulfilled, (state, action) => {
        const threat = state.items.find(t => t.id === action.payload);
        if (threat) {
          threat.acknowledged = true;
          threat.acknowledgedAt = new Date().toISOString();
        }
      });
  },
});

export const {
  setFilters,
  clearFilters,
  selectThreat,
  addThreat,
  updateThreat,
  removeThreat,
} = threatsSlice.actions;

// Selectors
export const selectAllThreats = (state: RootState) => state.threats.items;
export const selectFilteredThreats = (state: RootState) => state.threats.filteredItems;
export const selectSelectedThreat = (state: RootState) => state.threats.selectedThreat;
export const selectThreatFilters = (state: RootState) => state.threats.filters;
export const selectThreatsLoading = (state: RootState) => state.threats.loading;
export const selectThreatsError = (state: RootState) => state.threats.error;
export const selectThreatStats = (state: RootState) => state.threats.stats;
export const selectLastUpdate = (state: RootState) => state.threats.lastUpdate;

export default threatsSlice.reducer;
