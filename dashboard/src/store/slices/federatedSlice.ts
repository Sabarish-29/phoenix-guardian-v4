import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';
import type { FederatedModel, ThreatSignature, PrivacyMetrics, HospitalContribution } from '../../types/federated';
import { federatedApi } from '../../services/api/federatedApi';

interface FederatedState {
  globalModel: FederatedModel | null;
  signatures: ThreatSignature[];
  privacyMetrics: PrivacyMetrics | null;
  contributions: HospitalContribution[];
  loading: boolean;
  error: string | null;
  lastSync: string | null;
  stats: {
    totalSignatures: number;
    participatingHospitals: number;
    avgConfidence: number;
    privacyBudgetUsed: number;
  };
}

const initialState: FederatedState = {
  globalModel: null,
  signatures: [],
  privacyMetrics: null,
  contributions: [],
  loading: false,
  error: null,
  lastSync: null,
  stats: {
    totalSignatures: 0,
    participatingHospitals: 0,
    avgConfidence: 0,
    privacyBudgetUsed: 0,
  },
};

// Async thunks
export const fetchGlobalModel = createAsyncThunk(
  'federated/fetchGlobalModel',
  async (_, { rejectWithValue }) => {
    try {
      const response = await federatedApi.getGlobalModel();
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch global model');
    }
  }
);

export const fetchThreatSignatures = createAsyncThunk(
  'federated/fetchSignatures',
  async (params: { limit?: number; attackType?: string } | undefined, { rejectWithValue }) => {
    try {
      const response = await federatedApi.getSignatures(params);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch signatures');
    }
  }
);

export const fetchPrivacyMetrics = createAsyncThunk(
  'federated/fetchPrivacyMetrics',
  async (_, { rejectWithValue }) => {
    try {
      const response = await federatedApi.getPrivacyMetrics();
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch privacy metrics');
    }
  }
);

export const fetchContributions = createAsyncThunk(
  'federated/fetchContributions',
  async (_, { rejectWithValue }) => {
    try {
      const response = await federatedApi.getContributions();
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch contributions');
    }
  }
);

export const triggerModelSync = createAsyncThunk(
  'federated/triggerSync',
  async (_, { rejectWithValue }) => {
    try {
      const response = await federatedApi.triggerSync();
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to trigger sync');
    }
  }
);

// Calculate stats helper
const calculateStats = (signatures: ThreatSignature[], contributions: HospitalContribution[], privacyMetrics: PrivacyMetrics | null) => {
  const avgConfidence = signatures.length > 0
    ? signatures.reduce((sum, s) => sum + s.confidence, 0) / signatures.length
    : 0;
  
  return {
    totalSignatures: signatures.length,
    participatingHospitals: contributions.length,
    avgConfidence: Math.round(avgConfidence * 100) / 100,
    privacyBudgetUsed: privacyMetrics?.budgetUsed || 0,
  };
};

const federatedSlice = createSlice({
  name: 'federated',
  initialState,
  reducers: {
    addSignature: (state, action: PayloadAction<ThreatSignature>) => {
      state.signatures.unshift(action.payload);
      state.stats = calculateStats(state.signatures, state.contributions, state.privacyMetrics);
    },
    updatePrivacyBudget: (state, action: PayloadAction<number>) => {
      if (state.privacyMetrics) {
        state.privacyMetrics.budgetUsed = action.payload;
        state.stats.privacyBudgetUsed = action.payload;
      }
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch global model
      .addCase(fetchGlobalModel.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchGlobalModel.fulfilled, (state, action) => {
        state.loading = false;
        state.globalModel = action.payload;
        state.lastSync = action.payload.lastUpdated;
      })
      .addCase(fetchGlobalModel.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Fetch signatures
      .addCase(fetchThreatSignatures.fulfilled, (state, action) => {
        state.signatures = action.payload;
        state.stats = calculateStats(action.payload, state.contributions, state.privacyMetrics);
      })
      // Fetch privacy metrics
      .addCase(fetchPrivacyMetrics.fulfilled, (state, action) => {
        state.privacyMetrics = action.payload;
        state.stats = calculateStats(state.signatures, state.contributions, action.payload);
      })
      // Fetch contributions
      .addCase(fetchContributions.fulfilled, (state, action) => {
        state.contributions = action.payload;
        state.stats = calculateStats(state.signatures, action.payload, state.privacyMetrics);
      })
      // Trigger sync
      .addCase(triggerModelSync.fulfilled, (state, action) => {
        state.globalModel = action.payload;
        state.lastSync = new Date().toISOString();
      });
  },
});

export const { addSignature, updatePrivacyBudget } = federatedSlice.actions;

// Selectors
export const selectGlobalModel = (state: RootState) => state.federated.globalModel;
export const selectThreatSignatures = (state: RootState) => state.federated.signatures;
export const selectPrivacyMetrics = (state: RootState) => state.federated.privacyMetrics;
export const selectContributions = (state: RootState) => state.federated.contributions;
export const selectFederatedLoading = (state: RootState) => state.federated.loading;
export const selectFederatedStats = (state: RootState) => state.federated.stats;
export const selectLastSync = (state: RootState) => state.federated.lastSync;

export default federatedSlice.reducer;
