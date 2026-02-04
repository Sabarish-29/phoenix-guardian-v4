/**
 * Phoenix Guardian Mobile - WebSocket Service
 * 
 * Real-time connection for SOAP note streaming.
 * 
 * Features:
 * - Bidirectional WebSocket communication
 * - Real-time transcription streaming
 * - SOAP note section streaming
 * - Automatic reconnection with backoff
 * - Message queuing during disconnection
 * - Connection state management
 * 
 * @module services/WebSocketService
 */

import { io, Socket } from 'socket.io-client';
import AuthService from './AuthService';
import { EventEmitter } from 'events';

// ============================================================================
// Types & Interfaces
// ============================================================================

export type ConnectionState = 
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'error';

export type SOAPSection = 'subjective' | 'objective' | 'assessment' | 'plan';

export interface TranscriptUpdate {
  type: 'transcript_update';
  text: string;
  isFinal: boolean;
  timestamp: string;
}

export interface SOAPSectionUpdate {
  type: 'soap_section_ready';
  section: SOAPSection;
  text: string;
  confidence: number;
}

export interface SOAPComplete {
  type: 'soap_complete';
  encounterId: string;
  soapNote: {
    subjective: string;
    objective: string;
    assessment: string;
    plan: string;
  };
}

export interface EncounterError {
  type: 'error';
  code: string;
  message: string;
}

export type EncounterEvent = 
  | TranscriptUpdate
  | SOAPSectionUpdate
  | SOAPComplete
  | EncounterError;

export interface StartEncounterOptions {
  patientId: string;
  encounterId: string;
  encounterType?: 'routine' | 'followup' | 'emergency' | 'consultation';
  language?: string;
}

export interface AudioChunkMetadata {
  sampleRate: number;
  channels: number;
  bitDepth: number;
  timestamp: number;
}

interface QueuedMessage {
  event: string;
  data: unknown;
  timestamp: number;
}

// ============================================================================
// Constants
// ============================================================================

const RECONNECT_DELAY_BASE = 1000;
const RECONNECT_DELAY_MAX = 30000;
const RECONNECT_ATTEMPTS = Infinity;
const PING_INTERVAL = 25000;
const MESSAGE_QUEUE_MAX_SIZE = 100;
const MESSAGE_QUEUE_MAX_AGE = 5 * 60 * 1000; // 5 minutes

// ============================================================================
// WebSocketService Class
// ============================================================================

class WebSocketService extends EventEmitter {
  private static instance: WebSocketService;
  private socket: Socket | null = null;
  private connectionState: ConnectionState = 'disconnected';
  private messageQueue: QueuedMessage[] = [];
  private currentEncounterId: string | null = null;
  private reconnectAttempts = 0;
  private pingTimer: ReturnType<typeof setInterval> | null = null;

  private constructor() {
    super();
    this.setMaxListeners(50);
  }

  static getInstance(): WebSocketService {
    if (!WebSocketService.instance) {
      WebSocketService.instance = new WebSocketService();
    }
    return WebSocketService.instance;
  }

  // ==========================================================================
  // Connection Management
  // ==========================================================================

  /**
   * Connect to WebSocket server.
   */
  async connect(): Promise<boolean> {
    if (this.socket?.connected) {
      return true;
    }

    const token = await AuthService.getToken();
    if (!token) {
      console.error('No auth token for WebSocket');
      this.setConnectionState('error');
      return false;
    }

    const tenantId = AuthService.getTenantId();
    if (!tenantId) {
      console.error('No tenant ID for WebSocket');
      this.setConnectionState('error');
      return false;
    }

    return new Promise((resolve) => {
      this.setConnectionState('connecting');

      const baseURL = __DEV__
        ? 'http://localhost:8000'
        : 'https://api.phoenix-guardian.ai';

      this.socket = io(baseURL, {
        path: '/ws/encounter',
        auth: { token, tenant_id: tenantId },
        transports: ['websocket'],
        reconnection: true,
        reconnectionDelay: RECONNECT_DELAY_BASE,
        reconnectionDelayMax: RECONNECT_DELAY_MAX,
        reconnectionAttempts: RECONNECT_ATTEMPTS,
        timeout: 20000,
      });

      this.setupSocketListeners(resolve);
    });
  }

  /**
   * Disconnect from WebSocket server.
   */
  disconnect(): void {
    this.stopPing();
    
    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
    }
    
    this.setConnectionState('disconnected');
    this.currentEncounterId = null;
  }

  /**
   * Get current connection state.
   */
  getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  /**
   * Check if connected.
   */
  isConnected(): boolean {
    return this.socket?.connected || false;
  }

  // ==========================================================================
  // Socket Event Listeners
  // ==========================================================================

  private setupSocketListeners(connectResolve: (value: boolean) => void): void {
    if (!this.socket) return;

    // Connection established
    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.setConnectionState('connected');
      this.reconnectAttempts = 0;
      this.startPing();
      this.flushMessageQueue();
      connectResolve(true);
    });

    // Connection error
    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      this.setConnectionState('error');
      connectResolve(false);
    });

    // Disconnected
    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      this.stopPing();
      
      if (reason === 'io server disconnect') {
        // Server disconnected us - don't auto reconnect
        this.setConnectionState('disconnected');
      } else {
        // Client disconnect or network issue - will auto reconnect
        this.setConnectionState('reconnecting');
      }
    });

    // Reconnecting
    this.socket.on('reconnect_attempt', (attempt) => {
      console.log('WebSocket reconnect attempt:', attempt);
      this.reconnectAttempts = attempt;
      this.setConnectionState('reconnecting');
    });

    // Reconnected
    this.socket.on('reconnect', () => {
      console.log('WebSocket reconnected');
      this.setConnectionState('connected');
      this.startPing();
      this.flushMessageQueue();
      
      // Resume encounter if one was active
      if (this.currentEncounterId) {
        this.socket?.emit('resume_encounter', { 
          encounter_id: this.currentEncounterId 
        });
      }
    });

    // Reconnect failed
    this.socket.on('reconnect_failed', () => {
      console.error('WebSocket reconnect failed');
      this.setConnectionState('error');
    });

    // Server events
    this.socket.on('transcript_update', (data) => {
      this.emit('encounter_event', {
        type: 'transcript_update',
        text: data.text,
        isFinal: data.is_final,
        timestamp: data.timestamp,
      } as TranscriptUpdate);
    });

    this.socket.on('soap_section_ready', (data) => {
      this.emit('encounter_event', {
        type: 'soap_section_ready',
        section: data.section,
        text: data.text,
        confidence: data.confidence,
      } as SOAPSectionUpdate);
    });

    this.socket.on('soap_complete', (data) => {
      this.emit('encounter_event', {
        type: 'soap_complete',
        encounterId: data.encounter_id,
        soapNote: {
          subjective: data.subjective,
          objective: data.objective,
          assessment: data.assessment,
          plan: data.plan,
        },
      } as SOAPComplete);
      
      this.currentEncounterId = null;
    });

    this.socket.on('error', (data) => {
      this.emit('encounter_event', {
        type: 'error',
        code: data.code,
        message: data.message,
      } as EncounterError);
    });

    // Pong response
    this.socket.on('pong', () => {
      // Connection is alive
    });
  }

  // ==========================================================================
  // Encounter Operations
  // ==========================================================================

  /**
   * Start a new encounter recording session.
   */
  startEncounter(options: StartEncounterOptions): void {
    if (!this.socket?.connected) {
      this.queueMessage('start_encounter', {
        patient_id: options.patientId,
        encounter_id: options.encounterId,
        encounter_type: options.encounterType || 'routine',
        language: options.language || 'en-US',
        timestamp: new Date().toISOString(),
      });
      return;
    }

    this.currentEncounterId = options.encounterId;
    
    this.socket.emit('start_encounter', {
      patient_id: options.patientId,
      encounter_id: options.encounterId,
      encounter_type: options.encounterType || 'routine',
      language: options.language || 'en-US',
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Send audio chunk for transcription.
   */
  sendAudioChunk(audioData: ArrayBuffer, metadata: AudioChunkMetadata): void {
    if (!this.socket?.connected) {
      // Don't queue audio chunks - they're too large and time-sensitive
      console.warn('Cannot send audio chunk - not connected');
      return;
    }

    this.socket.emit('audio_chunk', {
      audio: audioData,
      sample_rate: metadata.sampleRate,
      channels: metadata.channels,
      bit_depth: metadata.bitDepth,
      timestamp: metadata.timestamp,
    });
  }

  /**
   * Send complete audio file (for offline recordings).
   */
  sendAudioFile(audioData: ArrayBuffer, filename: string): void {
    if (!this.socket?.connected) {
      throw new Error('WebSocket not connected');
    }

    this.socket.emit('audio_file', {
      audio: audioData,
      filename,
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Stop the current encounter recording.
   */
  stopEncounter(): void {
    if (!this.socket?.connected) {
      this.queueMessage('stop_encounter', {
        timestamp: new Date().toISOString(),
      });
      return;
    }

    this.socket.emit('stop_encounter', {
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Cancel the current encounter.
   */
  cancelEncounter(): void {
    if (!this.socket?.connected) {
      this.currentEncounterId = null;
      return;
    }

    this.socket.emit('cancel_encounter');
    this.currentEncounterId = null;
  }

  /**
   * Request regeneration of a SOAP section.
   */
  regenerateSection(section: SOAPSection, context?: string): void {
    if (!this.socket?.connected) {
      throw new Error('WebSocket not connected');
    }

    this.socket.emit('regenerate_section', {
      section,
      context,
      timestamp: new Date().toISOString(),
    });
  }

  // ==========================================================================
  // Event Subscription
  // ==========================================================================

  /**
   * Subscribe to encounter events.
   */
  onEncounterEvent(callback: (event: EncounterEvent) => void): () => void {
    this.on('encounter_event', callback);
    return () => this.off('encounter_event', callback);
  }

  /**
   * Subscribe to connection state changes.
   */
  onConnectionStateChange(callback: (state: ConnectionState) => void): () => void {
    this.on('connection_state', callback);
    return () => this.off('connection_state', callback);
  }

  // ==========================================================================
  // Private Methods
  // ==========================================================================

  private setConnectionState(state: ConnectionState): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.emit('connection_state', state);
    }
  }

  private startPing(): void {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      if (this.socket?.connected) {
        this.socket.emit('ping');
      }
    }, PING_INTERVAL);
  }

  private stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private queueMessage(event: string, data: unknown): void {
    if (this.messageQueue.length >= MESSAGE_QUEUE_MAX_SIZE) {
      // Remove oldest message
      this.messageQueue.shift();
    }

    this.messageQueue.push({
      event,
      data,
      timestamp: Date.now(),
    });
  }

  private flushMessageQueue(): void {
    if (!this.socket?.connected) return;

    const now = Date.now();
    
    // Filter out expired messages
    const validMessages = this.messageQueue.filter(
      msg => now - msg.timestamp < MESSAGE_QUEUE_MAX_AGE
    );

    // Send all valid messages
    validMessages.forEach(msg => {
      this.socket?.emit(msg.event, msg.data);
    });

    // Clear queue
    this.messageQueue = [];
  }

  /**
   * Get current encounter ID.
   */
  getCurrentEncounterId(): string | null {
    return this.currentEncounterId;
  }
}

// Export singleton instance
export default WebSocketService.getInstance();
