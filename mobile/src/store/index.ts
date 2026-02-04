/**
 * Phoenix Guardian Mobile - Week 23-24
 * Redux Store: State management for the mobile app.
 * 
 * Slices:
 * - authSlice: Authentication state
 * - encounterSlice: Encounter data
 * - offlineSlice: Offline queue management
 */

import { configureStore } from '@reduxjs/toolkit';
import authReducer from './authSlice';
import encounterReducer from './encounterSlice';
import offlineReducer from './offlineSlice';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    encounters: encounterReducer,
    offline: offlineReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore certain action types that may contain non-serializable data
        ignoredActions: ['offline/addToQueue'],
        ignoredPaths: ['offline.queue'],
      },
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

export default store;
