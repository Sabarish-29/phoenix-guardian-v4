/**
 * Create encounter page component.
 * 
 * Allows physicians to create new patient encounters by:
 * - Entering patient information
 * - Providing chief complaint
 * - Pasting or uploading transcript
 * - Processing through AI pipeline
 */

import React, { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { encounterService, CreateEncounterRequest, SOAPNoteApiResponse } from '../api/services/encounterService';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { VoiceRecorder } from '../components/VoiceRecorder';
import { TranscriptEditor } from '../components/TranscriptEditor';
import type { TranscriptSegment, Correction } from '../types/transcription';

type EncounterType = 
  | 'office_visit'
  | 'follow_up'
  | 'annual_physical'
  | 'urgent_care'
  | 'telehealth'
  | 'procedure';

const ENCOUNTER_TYPES: { value: EncounterType; label: string }[] = [
  { value: 'office_visit', label: 'Office Visit' },
  { value: 'follow_up', label: 'Follow-up Visit' },
  { value: 'annual_physical', label: 'Annual Physical' },
  { value: 'urgent_care', label: 'Urgent Care' },
  { value: 'telehealth', label: 'Telehealth' },
  { value: 'procedure', label: 'Procedure' },
];

export const CreateEncounterPage: React.FC = () => {
  const navigate = useNavigate();
  
  // Patient info state
  const [patientFirstName, setPatientFirstName] = useState('');
  const [patientLastName, setPatientLastName] = useState('');
  const [patientDob, setPatientDob] = useState('');
  const [patientMrn, setPatientMrn] = useState('');
  const [patientGender, setPatientGender] = useState('');
  
  // Encounter info state
  const [encounterType, setEncounterType] = useState<EncounterType>('office_visit');
  const [chiefComplaint, setChiefComplaint] = useState('');
  const [transcriptText, setTranscriptText] = useState('');
  
  // UI state
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Voice recording state
  type InputMode = 'type' | 'record';
  const [inputMode, setInputMode] = useState<InputMode>('type');
  const [recordingSegments, setRecordingSegments] = useState<TranscriptSegment[]>([]);
  const [showEditor, setShowEditor] = useState(false);

  // Voice recording callbacks
  const handleTranscriptUpdate = useCallback((text: string) => {
    setTranscriptText(text);
  }, []);

  const handleRecordingComplete = useCallback(
    (_audioBlob: Blob | null, text: string, segments: TranscriptSegment[]) => {
      setTranscriptText(text);
      setRecordingSegments(segments);
      setShowEditor(true);
    },
    []
  );

  const handleEditorSave = useCallback(
    (correctedTranscript: string, _corrections: Correction[]) => {
      setTranscriptText(correctedTranscript);
      setShowEditor(false);
    },
    []
  );

  const handleEditorCancel = useCallback(() => {
    setShowEditor(false);
  }, []);
  
  // Create encounter mutation
  const createMutation = useMutation({
    mutationFn: encounterService.createEncounter,
    onSuccess: async (response: SOAPNoteApiResponse) => {
      // Backend returns SOAPNoteResponse with encounter_id
      const encounterId = response.encounter_id;
      
      // Navigate to the encounter review page
      setIsProcessing(true);
      // The encounter was already processed during creation
      navigate(`/encounters/${encounterId}/review`);
    },
    onError: (err: Error & { response?: { data?: { detail?: string | Array<{msg: string}> } } }) => {
      const detail = err.response?.data?.detail;
      let message = 'Failed to create encounter';
      if (typeof detail === 'string') {
        message = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        // Handle Pydantic validation errors
        message = detail.map(e => e.msg).join(', ');
      }
      setError(message);
      setIsProcessing(false);
    },
  });
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    // Validation - match backend requirements
    if (!patientMrn.trim()) {
      setError('Patient MRN is required');
      return;
    }
    
    if (patientMrn.trim().length < 5) {
      setError('Patient MRN must be at least 5 characters');
      return;
    }
    
    if (patientMrn.trim().length > 20) {
      setError('Patient MRN must be at most 20 characters');
      return;
    }
    
    if (!transcriptText.trim()) {
      setError('Transcript text is required for AI processing');
      return;
    }
    
    if (transcriptText.trim().length < 50) {
      setError('Transcript must be at least 50 characters');
      return;
    }
    
    // Map encounter type to backend format
    const encounterTypeMap: Record<string, CreateEncounterRequest['encounter_type']> = {
      'office_visit': 'office_visit',
      'follow_up': 'follow_up',
      'annual_physical': 'office_visit',
      'urgent_care': 'urgent_care',
      'telehealth': 'telehealth',
      'procedure': 'office_visit',
    };
    
    const request: CreateEncounterRequest = {
      patient_mrn: patientMrn.trim(),
      encounter_type: encounterTypeMap[encounterType] || 'office_visit',
      transcript: transcriptText.trim(),
    };
    
    createMutation.mutate(request);
  };
  
  const isSubmitting = createMutation.isPending || isProcessing;
  
  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Create New Encounter</h1>
        <p className="mt-1 text-gray-500">
          Enter patient information and paste the encounter transcript for AI processing.
        </p>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Error Alert */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}
        
        {/* Patient Information Section */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Patient Information</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="firstName" className="block text-sm font-medium text-gray-700 mb-1">
                First Name <span className="text-red-500">*</span>
              </label>
              <input
                id="firstName"
                type="text"
                value={patientFirstName}
                onChange={(e) => setPatientFirstName(e.target.value)}
                className="input-field"
                placeholder="John"
                disabled={isSubmitting}
                required
              />
            </div>
            
            <div>
              <label htmlFor="lastName" className="block text-sm font-medium text-gray-700 mb-1">
                Last Name <span className="text-red-500">*</span>
              </label>
              <input
                id="lastName"
                type="text"
                value={patientLastName}
                onChange={(e) => setPatientLastName(e.target.value)}
                className="input-field"
                placeholder="Doe"
                disabled={isSubmitting}
                required
              />
            </div>
            
            <div>
              <label htmlFor="dob" className="block text-sm font-medium text-gray-700 mb-1">
                Date of Birth
              </label>
              <input
                id="dob"
                type="date"
                value={patientDob}
                onChange={(e) => setPatientDob(e.target.value)}
                className="input-field"
                disabled={isSubmitting}
              />
            </div>
            
            <div>
              <label htmlFor="mrn" className="block text-sm font-medium text-gray-700 mb-1">
                Medical Record Number (MRN) <span className="text-red-500">*</span>
              </label>
              <input
                id="mrn"
                type="text"
                value={patientMrn}
                onChange={(e) => setPatientMrn(e.target.value)}
                className="input-field"
                placeholder="MRN-12345"
                disabled={isSubmitting}
                required
              />
            </div>
            
            <div>
              <label htmlFor="gender" className="block text-sm font-medium text-gray-700 mb-1">
                Gender
              </label>
              <select
                id="gender"
                value={patientGender}
                onChange={(e) => setPatientGender(e.target.value)}
                className="input-field"
                disabled={isSubmitting}
              >
                <option value="">Select gender</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
          </div>
        </div>
        
        {/* Encounter Details Section */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Encounter Details</h2>
          
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="encounterType" className="block text-sm font-medium text-gray-700 mb-1">
                  Encounter Type
                </label>
                <select
                  id="encounterType"
                  value={encounterType}
                  onChange={(e) => setEncounterType(e.target.value as EncounterType)}
                  className="input-field"
                  disabled={isSubmitting}
                >
                  {ENCOUNTER_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>
              
              <div>
                <label htmlFor="chiefComplaint" className="block text-sm font-medium text-gray-700 mb-1">
                  Chief Complaint
                </label>
                <input
                  id="chiefComplaint"
                  type="text"
                  value={chiefComplaint}
                  onChange={(e) => setChiefComplaint(e.target.value)}
                  className="input-field"
                  placeholder="e.g., Chest pain, Follow-up for diabetes"
                  disabled={isSubmitting}
                />
              </div>
            </div>
          </div>
        </div>
        
        {/* Transcript Section */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                Encounter Transcript <span className="text-red-500">*</span>
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                {inputMode === 'type'
                  ? 'Paste the patient-physician conversation transcript below.'
                  : 'Use your microphone to transcribe the conversation in real time.'}
              </p>
            </div>

            {/* Type / Record toggle */}
            <div className="flex bg-gray-100 rounded-lg p-1">
              <button
                type="button"
                onClick={() => setInputMode('type')}
                className={`px-4 py-1.5 text-sm font-medium rounded-md transition ${
                  inputMode === 'type'
                    ? 'bg-white shadow text-blue-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
                disabled={isSubmitting}
              >
                ⌨️ Type
              </button>
              <button
                type="button"
                onClick={() => setInputMode('record')}
                className={`px-4 py-1.5 text-sm font-medium rounded-md transition ${
                  inputMode === 'record'
                    ? 'bg-white shadow text-blue-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
                disabled={isSubmitting}
              >
                🎙️ Record
              </button>
            </div>
          </div>

          {/* Type mode — textarea */}
          {inputMode === 'type' && (
            <>
              <textarea
                id="transcript"
                value={transcriptText}
                onChange={(e) => setTranscriptText(e.target.value)}
                className="input-field min-h-[300px] font-mono text-sm"
                placeholder={`Doctor: Good morning! What brings you in today?

Patient: I've been having chest pain for the past two days. It's a sharp pain on the left side.

Doctor: Can you describe when it occurs? Is it constant or does it come and go?

Patient: It comes and goes. It's worse when I take deep breaths.

Doctor: Any shortness of breath, dizziness, or nausea?

Patient: Some shortness of breath, but no dizziness or nausea.

...`}
                disabled={isSubmitting}
                required={inputMode === 'type' && !transcriptText}
              />
              
              <div className="mt-2 flex items-center justify-between text-sm text-gray-500">
                <span>{transcriptText.length} characters</span>
                <span>{transcriptText.split(/\s+/).filter(Boolean).length} words</span>
              </div>
            </>
          )}

          {/* Record mode — VoiceRecorder */}
          {inputMode === 'record' && !showEditor && (
            <VoiceRecorder
              onTranscriptUpdate={handleTranscriptUpdate}
              onRecordingComplete={handleRecordingComplete}
              disabled={isSubmitting}
            />
          )}

          {/* Post-recording editor */}
          {inputMode === 'record' && showEditor && (
            <TranscriptEditor
              transcript={transcriptText}
              segments={recordingSegments}
              onSave={handleEditorSave}
              onCancel={handleEditorCancel}
            />
          )}

          {/* Show transcript preview when in record mode (after text is captured) */}
          {inputMode === 'record' && transcriptText && !showEditor && (
            <div className="mt-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-gray-500">
                  Captured transcript ({transcriptText.split(/\s+/).filter(Boolean).length} words)
                </span>
                {recordingSegments.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowEditor(true)}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    Review & Edit
                  </button>
                )}
              </div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap line-clamp-4">
                {transcriptText}
              </p>
            </div>
          )}
        </div>
        
        {/* Submit Section */}
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="btn-secondary"
            disabled={isSubmitting}
          >
            Cancel
          </button>
          
          <button
            type="submit"
            disabled={isSubmitting}
            className="btn-primary flex items-center"
          >
            {isSubmitting ? (
              <>
                <LoadingSpinner size="sm" className="mr-2" />
                {isProcessing ? 'Processing with AI...' : 'Creating...'}
              </>
            ) : (
              <>
                <svg className="mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Create & Process
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default CreateEncounterPage;
