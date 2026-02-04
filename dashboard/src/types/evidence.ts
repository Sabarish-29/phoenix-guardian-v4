export type EvidenceType = 
  | 'network_logs'
  | 'system_logs'
  | 'application_logs'
  | 'memory_dump'
  | 'disk_image'
  | 'screenshots'
  | 'network_capture'
  | 'malware_sample'
  | 'timeline'
  | 'report';

export interface EvidenceItem {
  id: string;
  type: EvidenceType;
  name: string;
  description: string;
  size: number;
  hash: {
    md5: string;
    sha256: string;
  };
  collectedAt: string;
  collectedBy: string;
  chainOfCustody: {
    timestamp: string;
    action: string;
    actor: string;
    notes?: string;
  }[];
}

export interface EvidencePackage {
  id: string;
  incidentId: string;
  incidentTitle: string;
  createdAt: string;
  createdBy: string;
  status: 'generating' | 'ready' | 'expired' | 'error';
  items: EvidenceItem[];
  totalSize: number;
  format: 'zip' | 'tar.gz';
  integrityVerified: boolean;
  integrityVerifiedAt?: string;
  expiresAt: string;
  downloadCount: number;
  lastDownloadedAt?: string;
}

export interface DownloadProgress {
  progress: number;
  status: 'pending' | 'downloading' | 'completed' | 'error';
}

export interface EvidenceGenerationRequest {
  incidentId: string;
  includeTypes: EvidenceType[];
  timeRange?: {
    start: string;
    end: string;
  };
  anonymize: boolean;
}
