/**
 * Transcription Types for Phoenix Guardian Voice Transcription System.
 *
 * HIPAA-compliant, medical-grade voice transcription interfaces.
 */

/* ─── Recording Status ─── */    
export type RecordingStatus =
  | 'idle'
  | 'requesting_permission'
  | 'ready'
  | 'recording'
  | 'paused'
  | 'processing'
  | 'completed'
  | 'error';

export type SpeakerLabel = 'doctor' | 'patient' | 'unknown';

/* ─── Word-Level Detail ─── */
export interface WordDetail {
  word: string;
  startTime: number;   // seconds
  endTime: number;
  confidence: number;  // 0–1
  isMedical: boolean;
}

/* ─── Transcript Segment ─── */
export interface TranscriptSegment {
  id: string;
  text: string;
  startTime: number;   // seconds from recording start
  endTime: number;
  confidence: number;  // 0–1
  speaker: SpeakerLabel;
  isFinal: boolean;
  isMedicalTerm: boolean;
  alternatives: string[];
  words: WordDetail[];
}

/* ─── Recording Metadata ─── */
export interface RecordingMetadata {
  duration: number;       // seconds
  sampleRate: number;
  channels: number;
  bitDepth: number;
  averageVolume: number;  // 0–1
  noiseLevel: number;     // 0–1
  qualityScore: number;   // 0–100
}

/* ─── Flagged Term ─── */
export interface FlaggedTerm {
  term: string;
  position: number;
  confidence: number;
  suggestions: string[];
  context: string;
}

/* ─── Correction (audit trail) ─── */
export interface Correction {
  timestamp: number;
  original: string;
  corrected: string;
  reason: string;
  userId: string;
}

/* ─── Transcription Error ─── */
export interface TranscriptionError {
  code:
    | 'MICROPHONE_DENIED'
    | 'MICROPHONE_NOT_FOUND'
    | 'BROWSER_NOT_SUPPORTED'
    | 'NETWORK_ERROR'
    | 'LOW_QUALITY_AUDIO'
    | 'TRANSCRIPTION_FAILED'
    | 'TIMEOUT'
    | 'UNKNOWN';
  message: string;
  details?: string;
  recoverable: boolean;
}

/* ─── Voice Recorder Props ─── */
export interface VoiceRecorderProps {
  onTranscriptUpdate: (text: string, segments: TranscriptSegment[]) => void;
  onRecordingComplete: (audioBlob: Blob | null, transcript: string, segments: TranscriptSegment[]) => void;
  onError: (error: TranscriptionError) => void;
  maxDuration?: number;   // milliseconds, default 30 min
  disabled?: boolean;
}

/* ─── Transcript Editor Props ─── */
export interface TranscriptEditorProps {
  transcript: string;
  segments: TranscriptSegment[];
  onSave: (correctedTranscript: string, corrections: Correction[]) => void;
  onCancel: () => void;
  medicalTerms: string[];
  flaggedTerms: FlaggedTerm[];
  readOnly?: boolean;
}

/* ─── Backend Transcription Request ─── */
export interface TranscriptionRequest {
  language: string;
  enableSpeakerDiarization: boolean;
  medicalContext: boolean;
  enableWordConfidence: boolean;
  customVocabulary?: string[];
}

/* ─── Backend Transcription Response ─── */
export interface TranscriptionResponse {
  transcript: string;
  segments: TranscriptSegment[];
  confidence: number;
  duration: number;
  medicalTermsDetected: string[];
  warnings: string[];
  processingTime: number;
  sessionId: string;
}

/* ─── Medical Term Verification Response ─── */
export interface MedicalTermVerificationResponse {
  verifiedTerms: string[];
  flaggedTerms: FlaggedTerm[];
  suggestions: Record<string, string[]>;
}

/* ─── Audio Quality Check ─── */
export interface AudioQualityReport {
  score: number;          // 0–100
  sampleRate: number;
  duration: number;
  snr: number;            // signal-to-noise ratio in dB
  issues: string[];
  acceptable: boolean;
}
