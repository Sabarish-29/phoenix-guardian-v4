import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';
import type { EvidencePackage, EvidenceItem, DownloadProgress } from '../../types/evidence';
import { evidenceApi } from '../../services/api/evidenceApi';

interface EvidenceState {
  packages: EvidencePackage[];
  currentPackage: EvidencePackage | null;
  downloads: Record<string, DownloadProgress>;
  loading: boolean;
  error: string | null;
}

const initialState: EvidenceState = {
  packages: [],
  currentPackage: null,
  downloads: {},
  loading: false,
  error: null,
};

// Async thunks
export const fetchEvidencePackages = createAsyncThunk(
  'evidence/fetchPackages',
  async (incidentId: string | undefined, { rejectWithValue }) => {
    try {
      const response = await evidenceApi.getPackages(incidentId);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch evidence packages');
    }
  }
);

export const fetchEvidencePackageById = createAsyncThunk(
  'evidence/fetchPackageById',
  async (packageId: string, { rejectWithValue }) => {
    try {
      const response = await evidenceApi.getPackageById(packageId);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch evidence package');
    }
  }
);

export const generateEvidencePackage = createAsyncThunk(
  'evidence/generatePackage',
  async (incidentId: string, { rejectWithValue }) => {
    try {
      const response = await evidenceApi.generatePackage(incidentId);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to generate evidence package');
    }
  }
);

export const downloadEvidencePackage = createAsyncThunk(
  'evidence/downloadPackage',
  async (packageId: string, { dispatch, rejectWithValue }) => {
    try {
      // Initialize download progress
      dispatch(setDownloadProgress({ packageId, progress: 0, status: 'downloading' }));
      
      const blob = await evidenceApi.downloadPackage(packageId, (progress) => {
        dispatch(setDownloadProgress({ packageId, progress, status: 'downloading' }));
      });
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `evidence_${packageId}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      dispatch(setDownloadProgress({ packageId, progress: 100, status: 'completed' }));
      
      return packageId;
    } catch (error: any) {
      dispatch(setDownloadProgress({ packageId, progress: 0, status: 'error' }));
      return rejectWithValue(error.message || 'Failed to download evidence package');
    }
  }
);

export const verifyEvidenceIntegrity = createAsyncThunk(
  'evidence/verifyIntegrity',
  async (packageId: string, { rejectWithValue }) => {
    try {
      const response = await evidenceApi.verifyIntegrity(packageId);
      return { packageId, ...response };
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to verify evidence integrity');
    }
  }
);

const evidenceSlice = createSlice({
  name: 'evidence',
  initialState,
  reducers: {
    selectPackage: (state, action: PayloadAction<EvidencePackage | null>) => {
      state.currentPackage = action.payload;
    },
    setDownloadProgress: (state, action: PayloadAction<{
      packageId: string;
      progress: number;
      status: 'pending' | 'downloading' | 'completed' | 'error';
    }>) => {
      const { packageId, progress, status } = action.payload;
      state.downloads[packageId] = { progress, status };
    },
    clearDownloadProgress: (state, action: PayloadAction<string>) => {
      delete state.downloads[action.payload];
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch packages
      .addCase(fetchEvidencePackages.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchEvidencePackages.fulfilled, (state, action) => {
        state.loading = false;
        state.packages = action.payload;
      })
      .addCase(fetchEvidencePackages.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Fetch package by ID
      .addCase(fetchEvidencePackageById.fulfilled, (state, action) => {
        state.currentPackage = action.payload;
      })
      // Generate package
      .addCase(generateEvidencePackage.fulfilled, (state, action) => {
        state.packages.unshift(action.payload);
      })
      // Verify integrity
      .addCase(verifyEvidenceIntegrity.fulfilled, (state, action) => {
        const pkg = state.packages.find(p => p.id === action.payload.packageId);
        if (pkg) {
          pkg.integrityVerified = action.payload.valid;
          pkg.integrityVerifiedAt = new Date().toISOString();
        }
      });
  },
});

export const { selectPackage, setDownloadProgress, clearDownloadProgress } = evidenceSlice.actions;

// Selectors
export const selectAllPackages = (state: RootState) => state.evidence.packages;
export const selectCurrentPackage = (state: RootState) => state.evidence.currentPackage;
export const selectDownloads = (state: RootState) => state.evidence.downloads;
export const selectEvidenceLoading = (state: RootState) => state.evidence.loading;
export const selectEvidenceError = (state: RootState) => state.evidence.error;

export default evidenceSlice.reducer;
