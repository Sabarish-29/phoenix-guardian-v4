/**
 * Phoenix Guardian Mobile - Audio Service
 * 
 * Handles audio recording, processing, and streaming.
 * 
 * Features:
 * - Native audio capture (iOS/Android)
 * - Real-time audio streaming
 * - Audio compression
 * - Voice activity detection (VAD)
 * - Audio file management
 * 
 * @module services/AudioService
 */

import { Platform, NativeEventEmitter, NativeModules } from 'react-native';
import RNFS from 'react-native-fs';
import { EventEmitter } from 'events';

// ============================================================================
// Types & Interfaces
// ============================================================================

export type RecordingState = 
  | 'idle'
  | 'preparing'
  | 'recording'
  | 'paused'
  | 'stopping'
  | 'error';

export interface AudioConfig {
  sampleRate: number;
  channels: number;
  bitDepth: number;
  encoding: 'pcm' | 'aac' | 'opus';
  chunkDurationMs: number;
}

export interface RecordingMetrics {
  duration: number;        // Total recording duration in ms
  peakAmplitude: number;   // Peak amplitude (0-1)
  averageAmplitude: number; // Average amplitude (0-1)
  isSpeaking: boolean;     // Voice activity detected
  chunksSent: number;      // Number of chunks sent
  bytesRecorded: number;   // Total bytes recorded
}

export interface AudioChunk {
  data: ArrayBuffer;
  timestamp: number;
  duration: number;
  isSpeech: boolean;
}

export interface SavedRecording {
  id: string;
  filePath: string;
  duration: number;
  size: number;
  createdAt: string;
  mimeType: string;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_CONFIG: AudioConfig = {
  sampleRate: 16000,      // 16kHz - good for speech
  channels: 1,            // Mono
  bitDepth: 16,           // 16-bit
  encoding: 'pcm',        // PCM for streaming
  chunkDurationMs: 250,   // 250ms chunks
};

const VAD_THRESHOLD = 0.02;        // Voice activity threshold
const VAD_SILENCE_DURATION = 1500; // Silence before VAD triggers
const RECORDINGS_DIR = `${RNFS.DocumentDirectoryPath}/recordings`;

// ============================================================================
// AudioService Class
// ============================================================================

class AudioService extends EventEmitter {
  private static instance: AudioService;
  private config: AudioConfig = DEFAULT_CONFIG;
  private recordingState: RecordingState = 'idle';
  private currentRecordingPath: string | null = null;
  private recordingStartTime: number = 0;
  private metrics: RecordingMetrics = this.initMetrics();
  private vadSilenceStart: number = 0;
  private audioChunkBuffer: AudioChunk[] = [];
  private chunkTimer: ReturnType<typeof setInterval> | null = null;

  private constructor() {
    super();
    this.setMaxListeners(20);
    this.ensureRecordingsDirectory();
  }

  static getInstance(): AudioService {
    if (!AudioService.instance) {
      AudioService.instance = new AudioService();
    }
    return AudioService.instance;
  }

  // ==========================================================================
  // Configuration
  // ==========================================================================

  /**
   * Configure audio recording settings.
   */
  configure(config: Partial<AudioConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * Get current configuration.
   */
  getConfig(): AudioConfig {
    return { ...this.config };
  }

  // ==========================================================================
  // Recording Control
  // ==========================================================================

  /**
   * Start audio recording.
   */
  async startRecording(): Promise<boolean> {
    if (this.recordingState !== 'idle') {
      console.warn('Already recording');
      return false;
    }

    try {
      this.setRecordingState('preparing');
      
      // Request permissions if needed
      const hasPermission = await this.requestPermissions();
      if (!hasPermission) {
        throw new Error('Microphone permission denied');
      }

      // Create unique file path for this recording
      const timestamp = Date.now();
      const extension = this.config.encoding === 'aac' ? 'm4a' : 'wav';
      this.currentRecordingPath = `${RECORDINGS_DIR}/recording_${timestamp}.${extension}`;

      // Initialize recording with native module
      await this.initializeNativeRecording();

      // Start chunk timer for streaming
      this.startChunkTimer();

      // Update state
      this.recordingStartTime = Date.now();
      this.metrics = this.initMetrics();
      this.setRecordingState('recording');

      console.log('Recording started:', this.currentRecordingPath);
      return true;
    } catch (error) {
      console.error('Failed to start recording:', error);
      this.setRecordingState('error');
      return false;
    }
  }

  /**
   * Pause recording.
   */
  async pauseRecording(): Promise<void> {
    if (this.recordingState !== 'recording') {
      console.warn('Not currently recording');
      return;
    }

    try {
      await this.pauseNativeRecording();
      this.stopChunkTimer();
      this.setRecordingState('paused');
    } catch (error) {
      console.error('Failed to pause recording:', error);
    }
  }

  /**
   * Resume recording.
   */
  async resumeRecording(): Promise<void> {
    if (this.recordingState !== 'paused') {
      console.warn('Not paused');
      return;
    }

    try {
      await this.resumeNativeRecording();
      this.startChunkTimer();
      this.setRecordingState('recording');
    } catch (error) {
      console.error('Failed to resume recording:', error);
    }
  }

  /**
   * Stop recording and save file.
   */
  async stopRecording(): Promise<SavedRecording | null> {
    if (this.recordingState !== 'recording' && this.recordingState !== 'paused') {
      console.warn('Not recording');
      return null;
    }

    try {
      this.setRecordingState('stopping');
      this.stopChunkTimer();

      // Stop native recording
      const filePath = await this.stopNativeRecording();

      // Get file info
      const fileInfo = await RNFS.stat(filePath);
      
      const recording: SavedRecording = {
        id: `rec_${Date.now()}`,
        filePath,
        duration: Date.now() - this.recordingStartTime,
        size: fileInfo.size,
        createdAt: new Date().toISOString(),
        mimeType: this.config.encoding === 'aac' ? 'audio/m4a' : 'audio/wav',
      };

      this.setRecordingState('idle');
      this.currentRecordingPath = null;

      console.log('Recording saved:', recording);
      return recording;
    } catch (error) {
      console.error('Failed to stop recording:', error);
      this.setRecordingState('error');
      return null;
    }
  }

  /**
   * Cancel recording without saving.
   */
  async cancelRecording(): Promise<void> {
    if (this.recordingState === 'idle') {
      return;
    }

    try {
      this.stopChunkTimer();
      await this.stopNativeRecording();

      // Delete the file
      if (this.currentRecordingPath && await RNFS.exists(this.currentRecordingPath)) {
        await RNFS.unlink(this.currentRecordingPath);
      }

      this.currentRecordingPath = null;
      this.setRecordingState('idle');
    } catch (error) {
      console.error('Failed to cancel recording:', error);
      this.setRecordingState('error');
    }
  }

  // ==========================================================================
  // State & Metrics
  // ==========================================================================

  /**
   * Get current recording state.
   */
  getRecordingState(): RecordingState {
    return this.recordingState;
  }

  /**
   * Get current recording metrics.
   */
  getMetrics(): RecordingMetrics {
    if (this.recordingState === 'recording') {
      return {
        ...this.metrics,
        duration: Date.now() - this.recordingStartTime,
      };
    }
    return { ...this.metrics };
  }

  /**
   * Check if currently recording.
   */
  isRecording(): boolean {
    return this.recordingState === 'recording';
  }

  // ==========================================================================
  // Event Subscriptions
  // ==========================================================================

  /**
   * Subscribe to audio chunks.
   */
  onAudioChunk(callback: (chunk: AudioChunk) => void): () => void {
    this.on('audio_chunk', callback);
    return () => this.off('audio_chunk', callback);
  }

  /**
   * Subscribe to recording state changes.
   */
  onStateChange(callback: (state: RecordingState) => void): () => void {
    this.on('state_change', callback);
    return () => this.off('state_change', callback);
  }

  /**
   * Subscribe to metrics updates.
   */
  onMetricsUpdate(callback: (metrics: RecordingMetrics) => void): () => void {
    this.on('metrics_update', callback);
    return () => this.off('metrics_update', callback);
  }

  /**
   * Subscribe to voice activity detection.
   */
  onVoiceActivity(callback: (isSpeaking: boolean) => void): () => void {
    this.on('voice_activity', callback);
    return () => this.off('voice_activity', callback);
  }

  // ==========================================================================
  // File Management
  // ==========================================================================

  /**
   * Get all saved recordings.
   */
  async getSavedRecordings(): Promise<SavedRecording[]> {
    try {
      const files = await RNFS.readDir(RECORDINGS_DIR);
      
      const recordings: SavedRecording[] = await Promise.all(
        files
          .filter(f => f.isFile() && (f.name.endsWith('.wav') || f.name.endsWith('.m4a')))
          .map(async (file) => ({
            id: file.name.replace(/\.[^.]+$/, ''),
            filePath: file.path,
            duration: 0, // Would need to parse audio file
            size: file.size,
            createdAt: file.mtime?.toISOString() || new Date().toISOString(),
            mimeType: file.name.endsWith('.m4a') ? 'audio/m4a' : 'audio/wav',
          }))
      );

      return recordings.sort((a, b) => 
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      );
    } catch (error) {
      console.error('Failed to get saved recordings:', error);
      return [];
    }
  }

  /**
   * Delete a saved recording.
   */
  async deleteRecording(id: string): Promise<boolean> {
    try {
      const recordings = await this.getSavedRecordings();
      const recording = recordings.find(r => r.id === id);
      
      if (recording && await RNFS.exists(recording.filePath)) {
        await RNFS.unlink(recording.filePath);
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Failed to delete recording:', error);
      return false;
    }
  }

  /**
   * Read audio file as ArrayBuffer.
   */
  async readAudioFile(filePath: string): Promise<ArrayBuffer> {
    const base64 = await RNFS.readFile(filePath, 'base64');
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }

  /**
   * Get storage usage for recordings.
   */
  async getStorageUsage(): Promise<{ used: number; available: number }> {
    try {
      const recordings = await this.getSavedRecordings();
      const used = recordings.reduce((sum, r) => sum + r.size, 0);
      
      const fsInfo = await RNFS.getFSInfo();
      
      return {
        used,
        available: fsInfo.freeSpace,
      };
    } catch (error) {
      console.error('Failed to get storage usage:', error);
      return { used: 0, available: 0 };
    }
  }

  // ==========================================================================
  // Private Methods
  // ==========================================================================

  private initMetrics(): RecordingMetrics {
    return {
      duration: 0,
      peakAmplitude: 0,
      averageAmplitude: 0,
      isSpeaking: false,
      chunksSent: 0,
      bytesRecorded: 0,
    };
  }

  private setRecordingState(state: RecordingState): void {
    if (this.recordingState !== state) {
      this.recordingState = state;
      this.emit('state_change', state);
    }
  }

  private async ensureRecordingsDirectory(): Promise<void> {
    try {
      const exists = await RNFS.exists(RECORDINGS_DIR);
      if (!exists) {
        await RNFS.mkdir(RECORDINGS_DIR);
      }
    } catch (error) {
      console.error('Failed to create recordings directory:', error);
    }
  }

  private async requestPermissions(): Promise<boolean> {
    // Permissions are handled by React Native's PermissionsAndroid
    // or iOS Info.plist - this is a placeholder for the actual implementation
    if (Platform.OS === 'android') {
      const { PermissionsAndroid } = require('react-native');
      const granted = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
        {
          title: 'Microphone Permission',
          message: 'Phoenix Guardian needs access to your microphone to record patient encounters.',
          buttonNeutral: 'Ask Me Later',
          buttonNegative: 'Cancel',
          buttonPositive: 'OK',
        }
      );
      return granted === PermissionsAndroid.RESULTS.GRANTED;
    }
    
    // iOS handles permissions automatically via Info.plist
    return true;
  }

  private async initializeNativeRecording(): Promise<void> {
    // This would use a native module for audio recording
    // For now, we simulate the initialization
    console.log('Initializing native audio recording...');
  }

  private async pauseNativeRecording(): Promise<void> {
    console.log('Pausing native audio recording...');
  }

  private async resumeNativeRecording(): Promise<void> {
    console.log('Resuming native audio recording...');
  }

  private async stopNativeRecording(): Promise<string> {
    console.log('Stopping native audio recording...');
    return this.currentRecordingPath || '';
  }

  private startChunkTimer(): void {
    this.stopChunkTimer();
    
    this.chunkTimer = setInterval(() => {
      this.processAudioChunk();
    }, this.config.chunkDurationMs);
  }

  private stopChunkTimer(): void {
    if (this.chunkTimer) {
      clearInterval(this.chunkTimer);
      this.chunkTimer = null;
    }
  }

  private processAudioChunk(): void {
    // Simulate audio chunk processing
    // In real implementation, this would get data from native module
    const timestamp = Date.now();
    const amplitude = Math.random() * 0.5; // Simulated amplitude
    
    // Voice activity detection
    const isSpeech = amplitude > VAD_THRESHOLD;
    
    if (isSpeech) {
      this.vadSilenceStart = 0;
      if (!this.metrics.isSpeaking) {
        this.metrics.isSpeaking = true;
        this.emit('voice_activity', true);
      }
    } else {
      if (this.vadSilenceStart === 0) {
        this.vadSilenceStart = timestamp;
      }
      
      if (timestamp - this.vadSilenceStart > VAD_SILENCE_DURATION) {
        if (this.metrics.isSpeaking) {
          this.metrics.isSpeaking = false;
          this.emit('voice_activity', false);
        }
      }
    }

    // Update metrics
    this.metrics.peakAmplitude = Math.max(this.metrics.peakAmplitude, amplitude);
    this.metrics.chunksSent++;
    
    // Simulate chunk data
    const chunkSize = (this.config.sampleRate * this.config.chunkDurationMs / 1000) * 
                      this.config.channels * (this.config.bitDepth / 8);
    this.metrics.bytesRecorded += chunkSize;

    const chunk: AudioChunk = {
      data: new ArrayBuffer(chunkSize),
      timestamp,
      duration: this.config.chunkDurationMs,
      isSpeech,
    };

    this.emit('audio_chunk', chunk);
    this.emit('metrics_update', this.getMetrics());
  }
}

// Export singleton instance
export default AudioService.getInstance();
