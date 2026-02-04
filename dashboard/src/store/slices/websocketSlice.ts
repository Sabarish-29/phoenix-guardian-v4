import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';
import { socketService } from '../../services/websocket/socketService';
import { addThreat } from './threatsSlice';

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp: string;
}

interface WebSocketState {
  status: ConnectionStatus;
  lastMessage: WebSocketMessage | null;
  unreadAlerts: number;
  reconnectAttempts: number;
  error: string | null;
}

const initialState: WebSocketState = {
  status: 'disconnected',
  lastMessage: null,
  unreadAlerts: 0,
  reconnectAttempts: 0,
  error: null,
};

// Initialize WebSocket connection
export const initializeWebSocket = createAsyncThunk(
  'websocket/initialize',
  async (_, { dispatch, rejectWithValue }) => {
    try {
      await socketService.connect();
      
      // Set up message handlers
      socketService.on('threat', (data) => {
        dispatch(messageReceived({ type: 'threat', payload: data, timestamp: new Date().toISOString() }));
        dispatch(addThreat(data));
        dispatch(incrementUnreadAlerts());
      });
      
      socketService.on('alert', (data) => {
        dispatch(messageReceived({ type: 'alert', payload: data, timestamp: new Date().toISOString() }));
        dispatch(incrementUnreadAlerts());
      });
      
      socketService.on('incident_update', (data) => {
        dispatch(messageReceived({ type: 'incident_update', payload: data, timestamp: new Date().toISOString() }));
      });
      
      socketService.on('honeytoken_trigger', (data) => {
        dispatch(messageReceived({ type: 'honeytoken_trigger', payload: data, timestamp: new Date().toISOString() }));
        dispatch(incrementUnreadAlerts());
      });
      
      socketService.on('disconnect', () => {
        dispatch(setConnectionStatus('disconnected'));
      });
      
      socketService.on('reconnect_attempt', (attempt: number) => {
        dispatch(setReconnectAttempts(attempt));
        dispatch(setConnectionStatus('connecting'));
      });
      
      socketService.on('reconnect', () => {
        dispatch(setConnectionStatus('connected'));
        dispatch(setReconnectAttempts(0));
      });
      
      return true;
    } catch (error: any) {
      return rejectWithValue(error.message || 'WebSocket connection failed');
    }
  }
);

// Disconnect WebSocket
export const disconnectWebSocket = createAsyncThunk(
  'websocket/disconnect',
  async () => {
    socketService.disconnect();
    return true;
  }
);

const websocketSlice = createSlice({
  name: 'websocket',
  initialState,
  reducers: {
    setConnectionStatus: (state, action: PayloadAction<ConnectionStatus>) => {
      state.status = action.payload;
      if (action.payload === 'connected') {
        state.error = null;
      }
    },
    messageReceived: (state, action: PayloadAction<WebSocketMessage>) => {
      state.lastMessage = action.payload;
    },
    incrementUnreadAlerts: (state) => {
      state.unreadAlerts += 1;
    },
    clearUnreadAlerts: (state) => {
      state.unreadAlerts = 0;
    },
    setReconnectAttempts: (state, action: PayloadAction<number>) => {
      state.reconnectAttempts = action.payload;
    },
    setError: (state, action: PayloadAction<string>) => {
      state.error = action.payload;
      state.status = 'error';
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(initializeWebSocket.pending, (state) => {
        state.status = 'connecting';
        state.error = null;
      })
      .addCase(initializeWebSocket.fulfilled, (state) => {
        state.status = 'connected';
        state.error = null;
        state.reconnectAttempts = 0;
      })
      .addCase(initializeWebSocket.rejected, (state, action) => {
        state.status = 'error';
        state.error = action.payload as string;
      })
      .addCase(disconnectWebSocket.fulfilled, (state) => {
        state.status = 'disconnected';
      });
  },
});

export const {
  setConnectionStatus,
  messageReceived,
  incrementUnreadAlerts,
  clearUnreadAlerts,
  setReconnectAttempts,
  setError,
} = websocketSlice.actions;

// Selectors
export const selectConnectionStatus = (state: RootState) => state.websocket.status;
export const selectLastMessage = (state: RootState) => state.websocket.lastMessage;
export const selectUnreadAlerts = (state: RootState) => state.websocket.unreadAlerts;
export const selectReconnectAttempts = (state: RootState) => state.websocket.reconnectAttempts;
export const selectWebSocketError = (state: RootState) => state.websocket.error;

export default websocketSlice.reducer;
