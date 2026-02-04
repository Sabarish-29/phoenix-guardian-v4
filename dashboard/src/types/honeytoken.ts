export type HoneytokenType = 
  | 'patient_record'
  | 'medication'
  | 'admin_credential'
  | 'api_key'
  | 'database';

export type HoneytokenStatus = 'active' | 'inactive' | 'expired';

export interface Honeytoken {
  id: string;
  name: string;
  type: HoneytokenType;
  description: string;
  status: HoneytokenStatus;
  location: string;
  triggerCount: number;
  lastTriggered?: string;
  createdAt: string;
  expiresAt?: string;
  alertLevel: 'critical' | 'high' | 'medium';
  metadata?: {
    fakePatientId?: string;
    fakeMedication?: string;
    fakeCredential?: string;
  };
}

export interface HoneytokenTrigger {
  id: string;
  honeytokenId: string;
  honeytokenName: string;
  timestamp: string;
  sourceIp: string;
  sourceUser?: string;
  accessType: 'read' | 'write' | 'delete' | 'query';
  targetSystem: string;
  threatId?: string;
  details: {
    query?: string;
    endpoint?: string;
    headers?: Record<string, string>;
  };
}

export interface HoneytokenStats {
  total: number;
  active: number;
  triggered: number;
  byType: Record<HoneytokenType, number>;
  recentTriggers: HoneytokenTrigger[];
}
