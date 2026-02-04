export type ThreatSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export type AttackType = 
  | 'ransomware'
  | 'data_exfiltration'
  | 'privilege_escalation'
  | 'lateral_movement'
  | 'credential_theft'
  | 'phishing'
  | 'malware'
  | 'unauthorized_access'
  | 'ddos'
  | 'insider_threat'
  | 'unknown';

export interface ThreatLocation {
  latitude: number;
  longitude: number;
  city?: string;
  country?: string;
  region?: string;
}

export interface Threat {
  id: string;
  title: string;
  description: string;
  severity: ThreatSeverity;
  attackType: AttackType;
  sourceIp: string;
  sourceLocation?: ThreatLocation;
  targetAsset: string;
  targetDepartment?: string;
  indicators: string[];
  mitreAttackIds: string[];
  confidence: number;
  timestamp: string;
  acknowledged: boolean;
  acknowledgedAt?: string;
  acknowledgedBy?: string;
  relatedIncidentId?: string;
  honeytokenTriggered?: boolean;
  metadata?: Record<string, any>;
}

export interface ThreatFilters {
  severity: ThreatSeverity[];
  attackType: AttackType[];
  timeRange: '1h' | '6h' | '24h' | '7d' | '30d' | 'custom';
  startDate?: string;
  endDate?: string;
  searchQuery: string;
  acknowledged?: boolean;
}

export interface ThreatStats {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  byHour: { hour: string; count: number; severity: ThreatSeverity }[];
  byAttackType: { type: AttackType; count: number }[];
  topSources: { ip: string; count: number; country?: string }[];
}

export interface ThreatTimelineEntry {
  timestamp: string;
  count: number;
  severity: ThreatSeverity;
}
