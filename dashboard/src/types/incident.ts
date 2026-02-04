export type IncidentStatus = 
  | 'open'
  | 'investigating'
  | 'contained'
  | 'eradicating'
  | 'recovering'
  | 'resolved'
  | 'closed';

export type IncidentPriority = 'P1' | 'P2' | 'P3' | 'P4';

export type IncidentCategory =
  | 'malware'
  | 'ransomware'
  | 'data_breach'
  | 'unauthorized_access'
  | 'insider_threat'
  | 'phishing'
  | 'ddos'
  | 'policy_violation'
  | 'other';

export interface Incident {
  id: string;
  title: string;
  description: string;
  status: IncidentStatus;
  priority: IncidentPriority;
  category: IncidentCategory;
  severity: 'critical' | 'high' | 'medium' | 'low';
  affectedAssets: string[];
  affectedDepartments: string[];
  threatIds: string[];
  assignee?: {
    id: string;
    name: string;
    email: string;
  };
  createdAt: string;
  updatedAt: string;
  resolvedAt?: string;
  closedAt?: string;
  slaDeadline?: string;
  slaBreach: boolean;
  containmentActions: string[];
  remediationActions: string[];
  lessonsLearned?: string;
  evidencePackageId?: string;
}

export interface IncidentTimeline {
  id: string;
  incidentId: string;
  timestamp: string;
  type: 'status_change' | 'note' | 'assignment' | 'evidence' | 'action' | 'alert';
  actor: {
    id: string;
    name: string;
  };
  content: string;
  previousValue?: string;
  newValue?: string;
  metadata?: Record<string, any>;
}

export interface IncidentMetrics {
  mttr: number; // Mean Time To Resolve (hours)
  mttd: number; // Mean Time To Detect (minutes)
  openIncidents: number;
  resolvedThisWeek: number;
  slaBreach: number;
  byCategory: Record<IncidentCategory, number>;
  byPriority: Record<IncidentPriority, number>;
}
