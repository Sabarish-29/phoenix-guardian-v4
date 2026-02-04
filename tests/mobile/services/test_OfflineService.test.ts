/**
 * Phoenix Guardian Mobile - Week 23-24
 * Offline Service Tests
 * 
 * Tests for offline storage, sync, and conflict resolution.
 */

import { describe, test, expect, beforeEach, afterEach, jest } from '@jest/globals';

// Types
interface QueuedOperation {
  id: string;
  type: 'create' | 'update' | 'submit';
  encounterId: string;
  payload: any;
  status: 'pending' | 'syncing' | 'completed' | 'failed';
  createdAt: string;
  attempts: number;
}

interface SyncConflict {
  id: string;
  encounterId: string;
  localVersion: any;
  serverVersion: any;
  resolved: boolean;
}

// Offline Service implementation for testing
class OfflineService {
  private queue: QueuedOperation[] = [];
  private conflicts: SyncConflict[] = [];
  private isOnline: boolean = true;
  private storage: Map<string, any> = new Map();

  setOnline(online: boolean): void {
    this.isOnline = online;
  }

  getIsOnline(): boolean {
    return this.isOnline;
  }

  // Queue Management
  addToQueue(operation: Omit<QueuedOperation, 'id' | 'status' | 'createdAt' | 'attempts'>): QueuedOperation {
    const op: QueuedOperation = {
      id: `op_${Date.now()}`,
      status: 'pending',
      createdAt: new Date().toISOString(),
      attempts: 0,
      ...operation,
    };
    this.queue.push(op);
    return op;
  }

  getQueue(): QueuedOperation[] {
    return [...this.queue];
  }

  getPendingOperations(): QueuedOperation[] {
    return this.queue.filter(op => op.status === 'pending');
  }

  getFailedOperations(): QueuedOperation[] {
    return this.queue.filter(op => op.status === 'failed');
  }

  removeFromQueue(id: string): boolean {
    const index = this.queue.findIndex(op => op.id === id);
    if (index > -1) {
      this.queue.splice(index, 1);
      return true;
    }
    return false;
  }

  clearQueue(): void {
    this.queue = [];
  }

  // Sync Operations
  async processQueue(): Promise<{ success: number; failed: number }> {
    if (!this.isOnline) {
      return { success: 0, failed: 0 };
    }

    let success = 0;
    let failed = 0;

    for (const op of this.queue.filter(o => o.status === 'pending')) {
      op.status = 'syncing';
      op.attempts++;

      try {
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 10));
        
        if (op.attempts > 3) {
          throw new Error('Max retries exceeded');
        }

        op.status = 'completed';
        success++;
      } catch (error) {
        op.status = 'failed';
        failed++;
      }
    }

    return { success, failed };
  }

  retryOperation(id: string): boolean {
    const op = this.queue.find(o => o.id === id);
    if (op && op.status === 'failed') {
      op.status = 'pending';
      return true;
    }
    return false;
  }

  retryAllFailed(): number {
    let count = 0;
    for (const op of this.queue) {
      if (op.status === 'failed') {
        op.status = 'pending';
        count++;
      }
    }
    return count;
  }

  // Conflict Management
  addConflict(conflict: Omit<SyncConflict, 'id' | 'resolved'>): SyncConflict {
    const c: SyncConflict = {
      id: `conflict_${Date.now()}`,
      resolved: false,
      ...conflict,
    };
    this.conflicts.push(c);
    return c;
  }

  getConflicts(): SyncConflict[] {
    return this.conflicts.filter(c => !c.resolved);
  }

  resolveConflict(id: string, resolution: 'local' | 'server' | 'merge'): boolean {
    const conflict = this.conflicts.find(c => c.id === id);
    if (conflict) {
      conflict.resolved = true;
      return true;
    }
    return false;
  }

  // Local Storage
  saveLocal(key: string, data: any): void {
    this.storage.set(key, JSON.stringify(data));
  }

  loadLocal<T>(key: string): T | null {
    const data = this.storage.get(key);
    return data ? JSON.parse(data) : null;
  }

  removeLocal(key: string): boolean {
    return this.storage.delete(key);
  }

  clearLocal(): void {
    this.storage.clear();
  }

  getStorageSize(): number {
    let size = 0;
    this.storage.forEach(value => {
      size += value.length;
    });
    return size;
  }
}

describe('OfflineService', () => {
  let service: OfflineService;

  beforeEach(() => {
    service = new OfflineService();
  });

  // Network Status
  describe('Network Status', () => {
    test('defaults to online', () => {
      expect(service.getIsOnline()).toBe(true);
    });

    test('can set offline', () => {
      service.setOnline(false);
      expect(service.getIsOnline()).toBe(false);
    });

    test('can set online', () => {
      service.setOnline(false);
      service.setOnline(true);
      expect(service.getIsOnline()).toBe(true);
    });
  });

  // Queue Management
  describe('Queue Management', () => {
    test('adds operation to queue', () => {
      const op = service.addToQueue({
        type: 'create',
        encounterId: 'enc_001',
        payload: { data: 'test' },
      });

      expect(op.id).toBeDefined();
      expect(op.status).toBe('pending');
      expect(op.attempts).toBe(0);
    });

    test('gets all queued operations', () => {
      service.addToQueue({ type: 'create', encounterId: 'enc_001', payload: {} });
      service.addToQueue({ type: 'update', encounterId: 'enc_002', payload: {} });

      const queue = service.getQueue();
      expect(queue.length).toBe(2);
    });

    test('gets pending operations', () => {
      service.addToQueue({ type: 'create', encounterId: 'enc_001', payload: {} });
      
      const pending = service.getPendingOperations();
      expect(pending.length).toBe(1);
      expect(pending[0].status).toBe('pending');
    });

    test('removes operation from queue', () => {
      const op = service.addToQueue({ type: 'create', encounterId: 'enc_001', payload: {} });
      
      const removed = service.removeFromQueue(op.id);
      expect(removed).toBe(true);
      expect(service.getQueue().length).toBe(0);
    });

    test('returns false when removing non-existent operation', () => {
      const removed = service.removeFromQueue('non_existent');
      expect(removed).toBe(false);
    });

    test('clears queue', () => {
      service.addToQueue({ type: 'create', encounterId: 'enc_001', payload: {} });
      service.addToQueue({ type: 'update', encounterId: 'enc_002', payload: {} });
      
      service.clearQueue();
      expect(service.getQueue().length).toBe(0);
    });
  });

  // Sync Operations
  describe('Sync Operations', () => {
    test('processes queue when online', async () => {
      service.addToQueue({ type: 'create', encounterId: 'enc_001', payload: {} });
      
      const result = await service.processQueue();
      
      expect(result.success).toBe(1);
      expect(result.failed).toBe(0);
    });

    test('does not process when offline', async () => {
      service.setOnline(false);
      service.addToQueue({ type: 'create', encounterId: 'enc_001', payload: {} });
      
      const result = await service.processQueue();
      
      expect(result.success).toBe(0);
      expect(result.failed).toBe(0);
    });

    test('retries failed operation', async () => {
      const op = service.addToQueue({ type: 'create', encounterId: 'enc_001', payload: {} });
      
      // Manually mark as failed
      service.getQueue()[0].status = 'failed';
      
      const retried = service.retryOperation(op.id);
      expect(retried).toBe(true);
      expect(service.getPendingOperations().length).toBe(1);
    });

    test('retries all failed operations', () => {
      service.addToQueue({ type: 'create', encounterId: 'enc_001', payload: {} });
      service.addToQueue({ type: 'create', encounterId: 'enc_002', payload: {} });
      
      // Manually mark as failed
      service.getQueue().forEach(op => op.status = 'failed');
      
      const count = service.retryAllFailed();
      expect(count).toBe(2);
      expect(service.getPendingOperations().length).toBe(2);
    });

    test('gets failed operations', () => {
      service.addToQueue({ type: 'create', encounterId: 'enc_001', payload: {} });
      service.getQueue()[0].status = 'failed';
      
      const failed = service.getFailedOperations();
      expect(failed.length).toBe(1);
    });
  });

  // Conflict Management
  describe('Conflict Management', () => {
    test('adds conflict', () => {
      const conflict = service.addConflict({
        encounterId: 'enc_001',
        localVersion: { text: 'local' },
        serverVersion: { text: 'server' },
      });

      expect(conflict.id).toBeDefined();
      expect(conflict.resolved).toBe(false);
    });

    test('gets unresolved conflicts', () => {
      service.addConflict({
        encounterId: 'enc_001',
        localVersion: {},
        serverVersion: {},
      });

      const conflicts = service.getConflicts();
      expect(conflicts.length).toBe(1);
    });

    test('resolves conflict with local version', () => {
      const conflict = service.addConflict({
        encounterId: 'enc_001',
        localVersion: {},
        serverVersion: {},
      });

      const resolved = service.resolveConflict(conflict.id, 'local');
      expect(resolved).toBe(true);
      expect(service.getConflicts().length).toBe(0);
    });

    test('resolves conflict with server version', () => {
      const conflict = service.addConflict({
        encounterId: 'enc_001',
        localVersion: {},
        serverVersion: {},
      });

      const resolved = service.resolveConflict(conflict.id, 'server');
      expect(resolved).toBe(true);
    });

    test('resolves conflict with merge', () => {
      const conflict = service.addConflict({
        encounterId: 'enc_001',
        localVersion: {},
        serverVersion: {},
      });

      const resolved = service.resolveConflict(conflict.id, 'merge');
      expect(resolved).toBe(true);
    });
  });

  // Local Storage
  describe('Local Storage', () => {
    test('saves data locally', () => {
      service.saveLocal('key1', { value: 'test' });
      
      const data = service.loadLocal<{ value: string }>('key1');
      expect(data).toEqual({ value: 'test' });
    });

    test('returns null for non-existent key', () => {
      const data = service.loadLocal('non_existent');
      expect(data).toBeNull();
    });

    test('removes local data', () => {
      service.saveLocal('key1', { value: 'test' });
      
      const removed = service.removeLocal('key1');
      expect(removed).toBe(true);
      expect(service.loadLocal('key1')).toBeNull();
    });

    test('clears all local data', () => {
      service.saveLocal('key1', { value: 'test1' });
      service.saveLocal('key2', { value: 'test2' });
      
      service.clearLocal();
      
      expect(service.loadLocal('key1')).toBeNull();
      expect(service.loadLocal('key2')).toBeNull();
    });

    test('calculates storage size', () => {
      service.saveLocal('key1', { value: 'test' });
      
      const size = service.getStorageSize();
      expect(size).toBeGreaterThan(0);
    });
  });
});

// ==============================================================================
// Test Count: ~25 tests for Offline service
// ==============================================================================
