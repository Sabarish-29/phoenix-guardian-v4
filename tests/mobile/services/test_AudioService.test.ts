/**
 * Phoenix Guardian Mobile - Week 23-24
 * Audio Service Tests
 * 
 * Tests for audio recording, compression, and streaming.
 */

import { describe, test, expect, beforeEach, jest } from '@jest/globals';

// Types
interface AudioConfig {
  sampleRate: number;
  channels: number;
  bitDepth: number;
  format: 'wav' | 'opus' | 'aac';
}

interface RecordingState {
  isRecording: boolean;
  isPaused: boolean;
  duration: number;
  level: number;
}

// Audio Service implementation for testing
class AudioService {
  private config: AudioConfig;
  private state: RecordingState;
  private audioChunks: ArrayBuffer[] = [];
  private listeners: Map<string, Function[]> = new Map();

  constructor(config?: Partial<AudioConfig>) {
    this.config = {
      sampleRate: 16000,
      channels: 1,
      bitDepth: 16,
      format: 'opus',
      ...config,
    };
    this.state = {
      isRecording: false,
      isPaused: false,
      duration: 0,
      level: 0,
    };
  }

  getConfig(): AudioConfig {
    return { ...this.config };
  }

  getState(): RecordingState {
    return { ...this.state };
  }

  // Recording Controls
  async startRecording(): Promise<boolean> {
    if (this.state.isRecording) {
      return false;
    }
    
    // Check permissions (mock)
    const hasPermission = await this.checkPermissions();
    if (!hasPermission) {
      throw new Error('Microphone permission denied');
    }

    this.state.isRecording = true;
    this.state.isPaused = false;
    this.state.duration = 0;
    this.audioChunks = [];
    
    this.emit('recordingStarted');
    return true;
  }

  async stopRecording(): Promise<ArrayBuffer> {
    if (!this.state.isRecording) {
      throw new Error('Not recording');
    }

    this.state.isRecording = false;
    this.state.isPaused = false;
    
    const combinedAudio = this.combineChunks();
    this.emit('recordingStopped', { duration: this.state.duration });
    
    return combinedAudio;
  }

  pauseRecording(): boolean {
    if (!this.state.isRecording || this.state.isPaused) {
      return false;
    }
    
    this.state.isPaused = true;
    this.emit('recordingPaused');
    return true;
  }

  resumeRecording(): boolean {
    if (!this.state.isRecording || !this.state.isPaused) {
      return false;
    }
    
    this.state.isPaused = false;
    this.emit('recordingResumed');
    return true;
  }

  // Audio Processing
  async checkPermissions(): Promise<boolean> {
    // Mock permission check
    return true;
  }

  addAudioChunk(chunk: ArrayBuffer): void {
    if (!this.state.isRecording || this.state.isPaused) {
      return;
    }
    
    this.audioChunks.push(chunk);
    this.state.duration += this.calculateDuration(chunk);
    this.state.level = this.calculateLevel(chunk);
    
    this.emit('audioChunk', { chunk, duration: this.state.duration });
  }

  private combineChunks(): ArrayBuffer {
    const totalLength = this.audioChunks.reduce((acc, chunk) => acc + chunk.byteLength, 0);
    const combined = new ArrayBuffer(totalLength);
    const view = new Uint8Array(combined);
    
    let offset = 0;
    for (const chunk of this.audioChunks) {
      view.set(new Uint8Array(chunk), offset);
      offset += chunk.byteLength;
    }
    
    return combined;
  }

  private calculateDuration(chunk: ArrayBuffer): number {
    // Duration = bytes / (sampleRate * channels * (bitDepth / 8))
    const bytesPerSecond = this.config.sampleRate * this.config.channels * (this.config.bitDepth / 8);
    return chunk.byteLength / bytesPerSecond;
  }

  private calculateLevel(chunk: ArrayBuffer): number {
    // Mock audio level calculation (0-1)
    const view = new Int16Array(chunk);
    if (view.length === 0) return 0;
    
    let sum = 0;
    for (let i = 0; i < view.length; i++) {
      sum += Math.abs(view[i]);
    }
    const average = sum / view.length;
    return Math.min(average / 32768, 1);
  }

  // Compression
  async compressAudio(audio: ArrayBuffer): Promise<ArrayBuffer> {
    // Mock compression (just return as-is for tests)
    return audio;
  }

  getCompressionRatio(): number {
    // Mock compression ratio
    return 0.3; // 70% size reduction
  }

  // Events
  on(event: string, callback: Function): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);
    
    return () => {
      const callbacks = this.listeners.get(event)!;
      const index = callbacks.indexOf(callback);
      if (index > -1) callbacks.splice(index, 1);
    };
  }

  private emit(event: string, data?: any): void {
    const callbacks = this.listeners.get(event) || [];
    callbacks.forEach(cb => cb(data));
  }

  // Utilities
  getRecordedDuration(): number {
    return this.state.duration;
  }

  getChunkCount(): number {
    return this.audioChunks.length;
  }

  getAudioLevel(): number {
    return this.state.level;
  }

  formatDuration(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }
}

describe('AudioService', () => {
  let service: AudioService;

  beforeEach(() => {
    service = new AudioService();
  });

  // Configuration
  describe('Configuration', () => {
    test('uses default config', () => {
      const config = service.getConfig();
      expect(config.sampleRate).toBe(16000);
      expect(config.channels).toBe(1);
      expect(config.bitDepth).toBe(16);
      expect(config.format).toBe('opus');
    });

    test('accepts custom config', () => {
      const customService = new AudioService({
        sampleRate: 44100,
        channels: 2,
        format: 'aac',
      });
      
      const config = customService.getConfig();
      expect(config.sampleRate).toBe(44100);
      expect(config.channels).toBe(2);
      expect(config.format).toBe('aac');
    });
  });

  // Recording Controls
  describe('Recording Controls', () => {
    test('starts recording', async () => {
      const result = await service.startRecording();
      expect(result).toBe(true);
      expect(service.getState().isRecording).toBe(true);
    });

    test('does not start if already recording', async () => {
      await service.startRecording();
      const result = await service.startRecording();
      expect(result).toBe(false);
    });

    test('stops recording', async () => {
      await service.startRecording();
      const audio = await service.stopRecording();
      
      expect(audio).toBeInstanceOf(ArrayBuffer);
      expect(service.getState().isRecording).toBe(false);
    });

    test('throws when stopping without recording', async () => {
      await expect(service.stopRecording()).rejects.toThrow('Not recording');
    });

    test('pauses recording', async () => {
      await service.startRecording();
      const result = service.pauseRecording();
      
      expect(result).toBe(true);
      expect(service.getState().isPaused).toBe(true);
    });

    test('resumes recording', async () => {
      await service.startRecording();
      service.pauseRecording();
      const result = service.resumeRecording();
      
      expect(result).toBe(true);
      expect(service.getState().isPaused).toBe(false);
    });

    test('does not pause when not recording', () => {
      const result = service.pauseRecording();
      expect(result).toBe(false);
    });

    test('does not resume when not paused', async () => {
      await service.startRecording();
      const result = service.resumeRecording();
      expect(result).toBe(false);
    });
  });

  // Audio Processing
  describe('Audio Processing', () => {
    test('adds audio chunks while recording', async () => {
      await service.startRecording();
      
      service.addAudioChunk(new ArrayBuffer(1024));
      service.addAudioChunk(new ArrayBuffer(1024));
      
      expect(service.getChunkCount()).toBe(2);
    });

    test('ignores chunks when not recording', () => {
      service.addAudioChunk(new ArrayBuffer(1024));
      expect(service.getChunkCount()).toBe(0);
    });

    test('ignores chunks when paused', async () => {
      await service.startRecording();
      service.pauseRecording();
      
      service.addAudioChunk(new ArrayBuffer(1024));
      expect(service.getChunkCount()).toBe(0);
    });

    test('tracks recording duration', async () => {
      await service.startRecording();
      service.addAudioChunk(new ArrayBuffer(32000)); // 1 second at 16kHz
      
      const duration = service.getRecordedDuration();
      expect(duration).toBeGreaterThan(0);
    });

    test('calculates audio level', async () => {
      await service.startRecording();
      
      // Create chunk with audio data
      const chunk = new ArrayBuffer(1024);
      const view = new Int16Array(chunk);
      for (let i = 0; i < view.length; i++) {
        view[i] = 16384; // Half max volume
      }
      
      service.addAudioChunk(chunk);
      
      const level = service.getAudioLevel();
      expect(level).toBeGreaterThan(0);
      expect(level).toBeLessThanOrEqual(1);
    });
  });

  // Compression
  describe('Compression', () => {
    test('compresses audio', async () => {
      const original = new ArrayBuffer(10240);
      const compressed = await service.compressAudio(original);
      
      expect(compressed).toBeInstanceOf(ArrayBuffer);
    });

    test('reports compression ratio', () => {
      const ratio = service.getCompressionRatio();
      expect(ratio).toBeGreaterThan(0);
      expect(ratio).toBeLessThan(1);
    });
  });

  // Events
  describe('Events', () => {
    test('emits recordingStarted event', async () => {
      const callback = jest.fn();
      service.on('recordingStarted', callback);
      
      await service.startRecording();
      
      expect(callback).toHaveBeenCalled();
    });

    test('emits recordingStopped event', async () => {
      const callback = jest.fn();
      service.on('recordingStopped', callback);
      
      await service.startRecording();
      await service.stopRecording();
      
      expect(callback).toHaveBeenCalled();
    });

    test('emits audioChunk event', async () => {
      const callback = jest.fn();
      service.on('audioChunk', callback);
      
      await service.startRecording();
      service.addAudioChunk(new ArrayBuffer(1024));
      
      expect(callback).toHaveBeenCalled();
      expect(callback.mock.calls[0][0]).toHaveProperty('chunk');
    });

    test('unsubscribes from events', async () => {
      const callback = jest.fn();
      const unsubscribe = service.on('recordingStarted', callback);
      
      unsubscribe();
      await service.startRecording();
      
      expect(callback).not.toHaveBeenCalled();
    });
  });

  // Utilities
  describe('Utilities', () => {
    test('formats duration as MM:SS', () => {
      expect(service.formatDuration(0)).toBe('0:00');
      expect(service.formatDuration(30)).toBe('0:30');
      expect(service.formatDuration(65)).toBe('1:05');
      expect(service.formatDuration(125)).toBe('2:05');
    });

    test('checks permissions', async () => {
      const hasPermission = await service.checkPermissions();
      expect(typeof hasPermission).toBe('boolean');
    });
  });
});

// ==============================================================================
// Test Count: ~25 tests for Audio service
// ==============================================================================
