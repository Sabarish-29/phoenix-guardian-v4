import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';

interface AlertSettings {
  emailEnabled: boolean;
  slackEnabled: boolean;
  smsEnabled: boolean;
  criticalOnly: boolean;
  recipients: string[];
}

interface DashboardSettings {
  refreshInterval: number; // seconds
  theme: 'dark' | 'light';
  compactMode: boolean;
  showAnimations: boolean;
}

interface SettingsState {
  alerts: AlertSettings;
  dashboard: DashboardSettings;
  notifications: {
    sound: boolean;
    desktop: boolean;
  };
  savedFilters: {
    name: string;
    filters: Record<string, any>;
  }[];
}

const initialState: SettingsState = {
  alerts: {
    emailEnabled: true,
    slackEnabled: false,
    smsEnabled: false,
    criticalOnly: false,
    recipients: [],
  },
  dashboard: {
    refreshInterval: 30,
    theme: 'dark',
    compactMode: false,
    showAnimations: true,
  },
  notifications: {
    sound: true,
    desktop: true,
  },
  savedFilters: [],
};

const settingsSlice = createSlice({
  name: 'settings',
  initialState,
  reducers: {
    updateAlertSettings: (state, action: PayloadAction<Partial<AlertSettings>>) => {
      state.alerts = { ...state.alerts, ...action.payload };
    },
    updateDashboardSettings: (state, action: PayloadAction<Partial<DashboardSettings>>) => {
      state.dashboard = { ...state.dashboard, ...action.payload };
    },
    updateNotificationSettings: (state, action: PayloadAction<Partial<{ sound: boolean; desktop: boolean }>>) => {
      state.notifications = { ...state.notifications, ...action.payload };
    },
    addAlertRecipient: (state, action: PayloadAction<string>) => {
      if (!state.alerts.recipients.includes(action.payload)) {
        state.alerts.recipients.push(action.payload);
      }
    },
    removeAlertRecipient: (state, action: PayloadAction<string>) => {
      state.alerts.recipients = state.alerts.recipients.filter(r => r !== action.payload);
    },
    saveFilter: (state, action: PayloadAction<{ name: string; filters: Record<string, any> }>) => {
      const existingIndex = state.savedFilters.findIndex(f => f.name === action.payload.name);
      if (existingIndex >= 0) {
        state.savedFilters[existingIndex] = action.payload;
      } else {
        state.savedFilters.push(action.payload);
      }
    },
    deleteFilter: (state, action: PayloadAction<string>) => {
      state.savedFilters = state.savedFilters.filter(f => f.name !== action.payload);
    },
    resetSettings: () => initialState,
  },
});

export const {
  updateAlertSettings,
  updateDashboardSettings,
  updateNotificationSettings,
  addAlertRecipient,
  removeAlertRecipient,
  saveFilter,
  deleteFilter,
  resetSettings,
} = settingsSlice.actions;

// Selectors
export const selectAlertSettings = (state: RootState) => state.settings.alerts;
export const selectDashboardSettings = (state: RootState) => state.settings.dashboard;
export const selectNotificationSettings = (state: RootState) => state.settings.notifications;
export const selectSavedFilters = (state: RootState) => state.settings.savedFilters;
export const selectRefreshInterval = (state: RootState) => state.settings.dashboard.refreshInterval;

export default settingsSlice.reducer;
