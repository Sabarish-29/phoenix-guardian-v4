import { configureStore } from '@reduxjs/toolkit';
import threatsReducer from './slices/threatsSlice';
import websocketReducer from './slices/websocketSlice';
import honeytokensReducer from './slices/honeytokensSlice';
import evidenceReducer from './slices/evidenceSlice';
import incidentsReducer from './slices/incidentsSlice';
import federatedReducer from './slices/federatedSlice';
import settingsReducer from './slices/settingsSlice';

export const store = configureStore({
  reducer: {
    threats: threatsReducer,
    websocket: websocketReducer,
    honeytokens: honeytokensReducer,
    evidence: evidenceReducer,
    incidents: incidentsReducer,
    federated: federatedReducer,
    settings: settingsReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types for serialization check
        ignoredActions: ['websocket/messageReceived'],
        // Ignore these paths in the state
        ignoredPaths: ['threats.lastUpdate', 'incidents.lastUpdate'],
      },
    }),
  devTools: import.meta.env.DEV,
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
