/**
 * Phoenix Guardian Mobile - Offline Service
 * 
 * Handles offline data storage, sync, and conflict resolution.
 * 
 * Features:
 * - Local database (SQLite-like via MMKV)
 * - Offline encounter queue
 * - Background sync when connected
 * - Conflict resolution
 * - Progress tracking
 * 
 * @module services/OfflineService
 */

import { MMKV } from 'react-native-mmkv';
import NetInfo, { NetInfoState } from '@react-native-community/netinfo';
import { EventEmitter } from 'events';
import AuthService from './AuthService';

// ============================================================================
// Types & Interfaces
// ============================================================================

export type SyncStatus = 
  | 'pending'
  | 'syncing'
  | 'synced'
  | 'error'
  | 'conflict';

export type NetworkStatus = 'online' | 'offline' | 'limited';

export interface OfflineEncounter {
  id: string;
  patientId: string;
  tenantId: string;
  audioFilePath: string;
  audioDuration: number;
  audioSize: number;
  transcript?: string;
  soapNote?: SOAPNote;
  status: SyncStatus;
  createdAt: string;
  updatedAt: string;
  syncAttempts: number;
  lastSyncError?: string;
}

export interface SOAPNote {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
  edits?: SOAPEdit[];
}

export interface SOAPEdit {
  section: keyof SOAPNote;
  oldText: string;
  newText: string;
  editedAt: string;
}

export interface SyncProgress {
  total: number;
  completed: number;
  current: string | null;
  errors: number;
}

export interface ConflictResolution {
  encounterId: string;
  localVersion: OfflineEncounter;
  serverVersion: OfflineEncounter;
  resolution: 'local' | 'server' | 'merge';
  resolvedAt: string;
}

export interface OfflineSettings {
  maxOfflineEncounters: number;
  maxStorageMB: number;
  autoSyncEnabled: boolean;
  syncIntervalMinutes: number;
  retryDelaySeconds: number;
  maxRetries: number;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_SETTINGS: OfflineSettings = {
  maxOfflineEncounters: 50,
  maxStorageMB: 500,
  autoSyncEnabled: true,
  syncIntervalMinutes: 5,
  retryDelaySeconds: 30,
  maxRetries: 3,
};

const STORAGE_KEYS = {
  ENCOUNTERS: 'offline_encounters',
  SYNC_QUEUE: 'sync_queue',
  SETTINGS: 'offline_settings',
  LAST_SYNC: 'last_sync_time',
  CONFLICTS: 'sync_conflicts',
};

// ============================================================================
// OfflineService Class
// ============================================================================

class OfflineService extends EventEmitter {
  private static instance: OfflineService;
  private storage: MMKV;
  private settings: OfflineSettings = DEFAULT_SETTINGS;
  private networkStatus: NetworkStatus = 'offline';
  private isSyncing = false;
  private syncTimer: ReturnType<typeof setInterval> | null = null;
  private networkUnsubscribe: (() => void) | null = null;

  private constructor() {
    super();
    this.setMaxListeners(20);
    this.storage = new MMKV({ id: 'phoenix-guardian-offline' });
    this.loadSettings();
    this.setupNetworkListener();
  }

  static getInstance(): OfflineService {
    if (!OfflineService.instance) {
      OfflineService.instance = new OfflineService();
    }
    return OfflineService.instance;
  }

  // ==========================================================================
  // Network Status
  // ==========================================================================

  /**
   * Get current network status.
   */
  getNetworkStatus(): NetworkStatus {
    return this.networkStatus;
  }

  /**
   * Check if device is online.
   */
  isOnline(): boolean {
    return this.networkStatus === 'online';
  }

  /**
   * Subscribe to network status changes.
   */
  onNetworkChange(callback: (status: NetworkStatus) => void): () => void {
    this.on('network_change', callback);
    return () => this.off('network_change', callback);
  }

  private setupNetworkListener(): void {
    this.networkUnsubscribe = NetInfo.addEventListener((state: NetInfoState) => {
      const newStatus = this.determineNetworkStatus(state);
      
      if (newStatus !== this.networkStatus) {
        const wasOffline = this.networkStatus === 'offline';
        this.networkStatus = newStatus;
        this.emit('network_change', newStatus);
        
        // Trigger sync when coming back online
        if (wasOffline && newStatus === 'online' && this.settings.autoSyncEnabled) {
          this.triggerSync();
        }
      }
    });
  }

  private determineNetworkStatus(state: NetInfoState): NetworkStatus {
    if (!state.isConnected) {
      return 'offline';
    }
    
    if (state.isInternetReachable === false) {
      return 'limited';
    }
    
    return 'online';
  }

  // ==========================================================================
  // Encounter Storage
  // ==========================================================================

  /**
   * Save an encounter for offline storage.
   */
  async saveEncounter(encounter: Omit<OfflineEncounter, 'status' | 'syncAttempts' | 'updatedAt'>): Promise<OfflineEncounter> {
    const encounters = this.getEncounters();
    
    // Check storage limits
    if (encounters.length >= this.settings.maxOfflineEncounters) {
      // Remove oldest synced encounters
      const synced = encounters.filter(e => e.status === 'synced');
      if (synced.length > 0) {
        const oldest = synced.sort((a, b) => 
          new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
        )[0];
        await this.deleteEncounter(oldest.id);
      } else {
        throw new Error('Offline storage limit reached');
      }
    }

    const newEncounter: OfflineEncounter = {
      ...encounter,
      status: 'pending',
      syncAttempts: 0,
      updatedAt: new Date().toISOString(),
    };

    encounters.push(newEncounter);
    this.storage.set(STORAGE_KEYS.ENCOUNTERS, JSON.stringify(encounters));

    this.emit('encounter_saved', newEncounter);
    
    // Trigger sync if online
    if (this.isOnline() && this.settings.autoSyncEnabled) {
      this.triggerSync();
    }

    return newEncounter;
  }

  /**
   * Get all offline encounters.
   */
  getEncounters(): OfflineEncounter[] {
    const data = this.storage.getString(STORAGE_KEYS.ENCOUNTERS);
    return data ? JSON.parse(data) : [];
  }

  /**
   * Get encounter by ID.
   */
  getEncounter(id: string): OfflineEncounter | null {
    const encounters = this.getEncounters();
    return encounters.find(e => e.id === id) || null;
  }

  /**
   * Update an encounter.
   */
  async updateEncounter(id: string, updates: Partial<OfflineEncounter>): Promise<OfflineEncounter | null> {
    const encounters = this.getEncounters();
    const index = encounters.findIndex(e => e.id === id);
    
    if (index === -1) {
      return null;
    }

    encounters[index] = {
      ...encounters[index],
      ...updates,
      updatedAt: new Date().toISOString(),
    };

    this.storage.set(STORAGE_KEYS.ENCOUNTERS, JSON.stringify(encounters));
    this.emit('encounter_updated', encounters[index]);

    return encounters[index];
  }

  /**
   * Delete an encounter.
   */
  async deleteEncounter(id: string): Promise<boolean> {
    const encounters = this.getEncounters();
    const filtered = encounters.filter(e => e.id !== id);
    
    if (filtered.length === encounters.length) {
      return false;
    }

    this.storage.set(STORAGE_KEYS.ENCOUNTERS, JSON.stringify(filtered));
    this.emit('encounter_deleted', id);

    return true;
  }

  /**
   * Get pending encounters (not yet synced).
   */
  getPendingEncounters(): OfflineEncounter[] {
    return this.getEncounters().filter(e => 
      e.status === 'pending' || e.status === 'error'
    );
  }

  // ==========================================================================
  // SOAP Note Editing
  // ==========================================================================

  /**
   * Update SOAP note for an encounter.
   */
  async updateSOAPNote(encounterId: string, section: keyof SOAPNote, newText: string): Promise<OfflineEncounter | null> {
    const encounter = this.getEncounter(encounterId);
    
    if (!encounter || !encounter.soapNote) {
      return null;
    }

    // Track edit
    const edit: SOAPEdit = {
      section,
      oldText: encounter.soapNote[section] as string,
      newText,
      editedAt: new Date().toISOString(),
    };

    const updatedSoap: SOAPNote = {
      ...encounter.soapNote,
      [section]: newText,
      edits: [...(encounter.soapNote.edits || []), edit],
    };

    return this.updateEncounter(encounterId, {
      soapNote: updatedSoap,
      status: 'pending', // Mark for re-sync
    });
  }

  // ==========================================================================
  // Synchronization
  // ==========================================================================

  /**
   * Trigger a sync of pending encounters.
   */
  async triggerSync(): Promise<SyncProgress> {
    if (this.isSyncing) {
      console.log('Sync already in progress');
      return this.getSyncProgress();
    }

    if (!this.isOnline()) {
      console.log('Cannot sync - offline');
      return { total: 0, completed: 0, current: null, errors: 0 };
    }

    this.isSyncing = true;
    const pending = this.getPendingEncounters();
    
    const progress: SyncProgress = {
      total: pending.length,
      completed: 0,
      current: null,
      errors: 0,
    };

    this.emit('sync_started', progress);

    for (const encounter of pending) {
      progress.current = encounter.id;
      this.emit('sync_progress', progress);

      try {
        await this.syncEncounter(encounter);
        progress.completed++;
      } catch (error) {
        progress.errors++;
        console.error(`Failed to sync encounter ${encounter.id}:`, error);
      }
    }

    progress.current = null;
    this.storage.set(STORAGE_KEYS.LAST_SYNC, new Date().toISOString());
    this.isSyncing = false;
    
    this.emit('sync_completed', progress);
    return progress;
  }

  /**
   * Sync a single encounter to the server.
   */
  private async syncEncounter(encounter: OfflineEncounter): Promise<void> {
    await this.updateEncounter(encounter.id, { status: 'syncing' });

    try {
      const apiClient = AuthService.getApiClient();
      
      // Upload audio file first
      const audioData = await this.readAudioFile(encounter.audioFilePath);
      
      const response = await apiClient.post('/encounters/sync', {
        encounter_id: encounter.id,
        patient_id: encounter.patientId,
        audio_data: audioData,
        audio_duration: encounter.audioDuration,
        transcript: encounter.transcript,
        soap_note: encounter.soapNote,
        created_at: encounter.createdAt,
        edits: encounter.soapNote?.edits,
      });

      if (response.data.conflict) {
        // Handle conflict
        await this.handleConflict(encounter, response.data.server_version);
      } else {
        // Success
        await this.updateEncounter(encounter.id, {
          status: 'synced',
          lastSyncError: undefined,
        });
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      await this.updateEncounter(encounter.id, {
        status: 'error',
        syncAttempts: encounter.syncAttempts + 1,
        lastSyncError: errorMessage,
      });

      // If max retries exceeded, mark as permanent error
      if (encounter.syncAttempts + 1 >= this.settings.maxRetries) {
        this.emit('sync_failed_permanent', encounter.id);
      }

      throw error;
    }
  }

  /**
   * Handle sync conflict.
   */
  private async handleConflict(local: OfflineEncounter, server: OfflineEncounter): Promise<void> {
    const conflict: ConflictResolution = {
      encounterId: local.id,
      localVersion: local,
      serverVersion: server,
      resolution: 'merge', // Default to merge
      resolvedAt: new Date().toISOString(),
    };

    // Store conflict for user resolution
    const conflicts = this.getConflicts();
    conflicts.push(conflict);
    this.storage.set(STORAGE_KEYS.CONFLICTS, JSON.stringify(conflicts));

    await this.updateEncounter(local.id, { status: 'conflict' });
    this.emit('sync_conflict', conflict);
  }

  /**
   * Get pending conflicts.
   */
  getConflicts(): ConflictResolution[] {
    const data = this.storage.getString(STORAGE_KEYS.CONFLICTS);
    return data ? JSON.parse(data) : [];
  }

  /**
   * Resolve a conflict.
   */
  async resolveConflict(encounterId: string, resolution: 'local' | 'server' | 'merge'): Promise<void> {
    const conflicts = this.getConflicts();
    const conflict = conflicts.find(c => c.encounterId === encounterId);
    
    if (!conflict) {
      throw new Error('Conflict not found');
    }

    switch (resolution) {
      case 'local':
        // Keep local version, re-upload
        await this.updateEncounter(encounterId, { status: 'pending' });
        break;
      
      case 'server':
        // Accept server version
        await this.updateEncounter(encounterId, {
          ...conflict.serverVersion,
          status: 'synced',
        });
        break;
      
      case 'merge':
        // Merge - prefer local edits on server base
        const merged = this.mergeEncounters(conflict.localVersion, conflict.serverVersion);
        await this.updateEncounter(encounterId, {
          ...merged,
          status: 'pending', // Re-sync merged version
        });
        break;
    }

    // Remove conflict
    const remaining = conflicts.filter(c => c.encounterId !== encounterId);
    this.storage.set(STORAGE_KEYS.CONFLICTS, JSON.stringify(remaining));
  }

  private mergeEncounters(local: OfflineEncounter, server: OfflineEncounter): Partial<OfflineEncounter> {
    // Simple merge strategy: server base + local SOAP edits
    return {
      transcript: server.transcript,
      soapNote: {
        ...server.soapNote!,
        edits: [...(server.soapNote?.edits || []), ...(local.soapNote?.edits || [])],
      },
    };
  }

  // ==========================================================================
  // Auto Sync
  // ==========================================================================

  /**
   * Start automatic sync timer.
   */
  startAutoSync(): void {
    this.stopAutoSync();
    
    if (!this.settings.autoSyncEnabled) {
      return;
    }

    this.syncTimer = setInterval(
      () => this.triggerSync(),
      this.settings.syncIntervalMinutes * 60 * 1000
    );
  }

  /**
   * Stop automatic sync timer.
   */
  stopAutoSync(): void {
    if (this.syncTimer) {
      clearInterval(this.syncTimer);
      this.syncTimer = null;
    }
  }

  // ==========================================================================
  // Settings
  // ==========================================================================

  /**
   * Update settings.
   */
  updateSettings(updates: Partial<OfflineSettings>): void {
    this.settings = { ...this.settings, ...updates };
    this.storage.set(STORAGE_KEYS.SETTINGS, JSON.stringify(this.settings));
    
    // Restart auto sync if interval changed
    if (updates.syncIntervalMinutes || updates.autoSyncEnabled !== undefined) {
      if (this.settings.autoSyncEnabled) {
        this.startAutoSync();
      } else {
        this.stopAutoSync();
      }
    }
  }

  /**
   * Get current settings.
   */
  getSettings(): OfflineSettings {
    return { ...this.settings };
  }

  private loadSettings(): void {
    const data = this.storage.getString(STORAGE_KEYS.SETTINGS);
    if (data) {
      this.settings = { ...DEFAULT_SETTINGS, ...JSON.parse(data) };
    }
  }

  // ==========================================================================
  // Helpers
  // ==========================================================================

  /**
   * Get sync progress.
   */
  getSyncProgress(): SyncProgress {
    const pending = this.getPendingEncounters();
    const synced = this.getEncounters().filter(e => e.status === 'synced').length;
    const errors = this.getEncounters().filter(e => e.status === 'error').length;
    
    return {
      total: pending.length,
      completed: synced,
      current: this.isSyncing ? 'syncing' : null,
      errors,
    };
  }

  /**
   * Get last sync time.
   */
  getLastSyncTime(): string | null {
    return this.storage.getString(STORAGE_KEYS.LAST_SYNC) || null;
  }

  /**
   * Get storage usage.
   */
  getStorageUsage(): { used: number; limit: number; percentage: number } {
    const encounters = this.getEncounters();
    const used = encounters.reduce((sum, e) => sum + e.audioSize, 0);
    const limit = this.settings.maxStorageMB * 1024 * 1024;
    
    return {
      used,
      limit,
      percentage: Math.round((used / limit) * 100),
    };
  }

  private async readAudioFile(filePath: string): Promise<string> {
    const RNFS = require('react-native-fs');
    return RNFS.readFile(filePath, 'base64');
  }

  /**
   * Clear all offline data.
   */
  clearAll(): void {
    this.storage.delete(STORAGE_KEYS.ENCOUNTERS);
    this.storage.delete(STORAGE_KEYS.SYNC_QUEUE);
    this.storage.delete(STORAGE_KEYS.CONFLICTS);
    this.storage.delete(STORAGE_KEYS.LAST_SYNC);
    this.emit('data_cleared');
  }

  /**
   * Cleanup on unmount.
   */
  destroy(): void {
    this.stopAutoSync();
    if (this.networkUnsubscribe) {
      this.networkUnsubscribe();
    }
    this.removeAllListeners();
  }
}

// Export singleton instance
export default OfflineService.getInstance();
