export interface FederatedModel {
  id: string;
  version: string;
  lastUpdated: string;
  accuracy: number;
  participatingHospitals: number;
  totalContributions: number;
  signatureCount: number;
  status: 'active' | 'training' | 'validating';
  privacyGuarantee: {
    epsilon: number;
    delta: number;
  };
}

export interface ThreatSignature {
  id: string;
  signatureHash: string;
  attackType: string;
  confidence: number;
  contributorCount: number;
  firstSeen: string;
  lastSeen: string;
  indicators: string[];
  mitreMapping: string[];
  privacyPreserved: boolean;
}

export interface PrivacyMetrics {
  epsilon: number;
  delta: number;
  budgetTotal: number;
  budgetUsed: number;
  budgetRemaining: number;
  lastReset: string;
  nextReset: string;
  queriesThisPeriod: number;
  noiseMultiplier: number;
}

export interface HospitalContribution {
  hospitalId: string;
  hospitalName: string;
  region: string;
  contributionCount: number;
  lastContribution: string;
  privacyCompliant: boolean;
  qualityScore: number;
  signatureTypes: string[];
}

export interface FederatedStats {
  totalSignatures: number;
  participatingHospitals: number;
  avgConfidence: number;
  privacyBudgetUsed: number;
  modelAccuracy: number;
  contributionsByRegion: Record<string, number>;
  signaturesByType: Record<string, number>;
}
