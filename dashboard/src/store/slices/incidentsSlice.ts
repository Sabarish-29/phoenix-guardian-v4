import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';
import type { Incident, IncidentStatus, IncidentPriority, IncidentTimeline } from '../../types/incident';
import { incidentsApi } from '../../services/api/incidentsApi';

interface IncidentsState {
  items: Incident[];
  currentIncident: Incident | null;
  timeline: IncidentTimeline[];
  loading: boolean;
  error: string | null;
  lastUpdate: string | null;
  stats: {
    total: number;
    open: number;
    investigating: number;
    contained: number;
    resolved: number;
  };
}

const initialState: IncidentsState = {
  items: [],
  currentIncident: null,
  timeline: [],
  loading: false,
  error: null,
  lastUpdate: null,
  stats: {
    total: 0,
    open: 0,
    investigating: 0,
    contained: 0,
    resolved: 0,
  },
};

// Async thunks
export const fetchIncidents = createAsyncThunk(
  'incidents/fetchIncidents',
  async (status: IncidentStatus | undefined, { rejectWithValue }) => {
    try {
      const response = await incidentsApi.getIncidents(status);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch incidents');
    }
  }
);

export const fetchIncidentById = createAsyncThunk(
  'incidents/fetchById',
  async (incidentId: string, { rejectWithValue }) => {
    try {
      const response = await incidentsApi.getIncidentById(incidentId);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch incident');
    }
  }
);

export const fetchIncidentTimeline = createAsyncThunk(
  'incidents/fetchTimeline',
  async (incidentId: string, { rejectWithValue }) => {
    try {
      const response = await incidentsApi.getIncidentTimeline(incidentId);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch timeline');
    }
  }
);

export const createIncident = createAsyncThunk(
  'incidents/create',
  async (data: Partial<Incident>, { rejectWithValue }) => {
    try {
      const response = await incidentsApi.createIncident(data);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to create incident');
    }
  }
);

export const updateIncidentStatus = createAsyncThunk(
  'incidents/updateStatus',
  async ({ incidentId, status, notes }: { incidentId: string; status: IncidentStatus; notes?: string }, { rejectWithValue }) => {
    try {
      const response = await incidentsApi.updateStatus(incidentId, status, notes);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to update status');
    }
  }
);

export const assignIncident = createAsyncThunk(
  'incidents/assign',
  async ({ incidentId, assigneeId }: { incidentId: string; assigneeId: string }, { rejectWithValue }) => {
    try {
      const response = await incidentsApi.assignIncident(incidentId, assigneeId);
      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to assign incident');
    }
  }
);

export const addIncidentNote = createAsyncThunk(
  'incidents/addNote',
  async ({ incidentId, note }: { incidentId: string; note: string }, { rejectWithValue }) => {
    try {
      const response = await incidentsApi.addNote(incidentId, note);
      return { incidentId, timeline: response };
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to add note');
    }
  }
);

// Calculate stats helper
const calculateStats = (items: Incident[]) => {
  return {
    total: items.length,
    open: items.filter(i => i.status === 'open').length,
    investigating: items.filter(i => i.status === 'investigating').length,
    contained: items.filter(i => i.status === 'contained').length,
    resolved: items.filter(i => i.status === 'resolved').length,
  };
};

const incidentsSlice = createSlice({
  name: 'incidents',
  initialState,
  reducers: {
    selectIncident: (state, action: PayloadAction<Incident | null>) => {
      state.currentIncident = action.payload;
    },
    updateIncident: (state, action: PayloadAction<Incident>) => {
      const index = state.items.findIndex(i => i.id === action.payload.id);
      if (index !== -1) {
        state.items[index] = action.payload;
        state.stats = calculateStats(state.items);
      }
      if (state.currentIncident?.id === action.payload.id) {
        state.currentIncident = action.payload;
      }
    },
    addTimelineEntry: (state, action: PayloadAction<IncidentTimeline>) => {
      state.timeline.unshift(action.payload);
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch incidents
      .addCase(fetchIncidents.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchIncidents.fulfilled, (state, action) => {
        state.loading = false;
        state.items = action.payload;
        state.stats = calculateStats(action.payload);
        state.lastUpdate = new Date().toISOString();
      })
      .addCase(fetchIncidents.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Fetch incident by ID
      .addCase(fetchIncidentById.fulfilled, (state, action) => {
        state.currentIncident = action.payload;
      })
      // Fetch timeline
      .addCase(fetchIncidentTimeline.fulfilled, (state, action) => {
        state.timeline = action.payload;
      })
      // Create incident
      .addCase(createIncident.fulfilled, (state, action) => {
        state.items.unshift(action.payload);
        state.stats = calculateStats(state.items);
      })
      // Update status
      .addCase(updateIncidentStatus.fulfilled, (state, action) => {
        const index = state.items.findIndex(i => i.id === action.payload.id);
        if (index !== -1) {
          state.items[index] = action.payload;
          state.stats = calculateStats(state.items);
        }
        if (state.currentIncident?.id === action.payload.id) {
          state.currentIncident = action.payload;
        }
      })
      // Assign incident
      .addCase(assignIncident.fulfilled, (state, action) => {
        const index = state.items.findIndex(i => i.id === action.payload.id);
        if (index !== -1) {
          state.items[index] = action.payload;
        }
        if (state.currentIncident?.id === action.payload.id) {
          state.currentIncident = action.payload;
        }
      })
      // Add note
      .addCase(addIncidentNote.fulfilled, (state, action) => {
        state.timeline.unshift(action.payload.timeline);
      });
  },
});

export const { selectIncident, updateIncident, addTimelineEntry } = incidentsSlice.actions;

// Selectors
export const selectAllIncidents = (state: RootState) => state.incidents.items;
export const selectCurrentIncident = (state: RootState) => state.incidents.currentIncident;
export const selectIncidentTimeline = (state: RootState) => state.incidents.timeline;
export const selectIncidentsLoading = (state: RootState) => state.incidents.loading;
export const selectIncidentsError = (state: RootState) => state.incidents.error;
export const selectIncidentsStats = (state: RootState) => state.incidents.stats;
export const selectOpenIncidents = (state: RootState) => 
  state.incidents.items.filter(i => i.status === 'open' || i.status === 'investigating');

export default incidentsSlice.reducer;
