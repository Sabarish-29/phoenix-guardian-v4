/**
 * Create encounter page component.
 * 
 * Allows physicians to create new patient encounters by:
 * - Entering patient information
 * - Providing chief complaint
 * - Pasting or uploading transcript
 * - Processing through AI pipeline
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { encounterService, CreateEncounterRequest } from '../api/services/encounterService';
import { LoadingSpinner } from '../components/LoadingSpinner';

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
  
  // Create encounter mutation
  const createMutation = useMutation({
    mutationFn: encounterService.createEncounter,
    onSuccess: async (encounter) => {
      // Automatically process the encounter through AI pipeline
      setIsProcessing(true);
      try {
        await encounterService.processEncounter(encounter.id);
        navigate(`/encounters/${encounter.uuid}/review`);
      } catch (processError) {
        // Still navigate to the encounter even if processing fails
        console.error('Processing error:', processError);
        navigate(`/encounters/${encounter.uuid}`);
      }
    },
    onError: (err: Error & { response?: { data?: { detail?: string } } }) => {
      const message = err.response?.data?.detail || 'Failed to create encounter';
      setError(message);
      setIsProcessing(false);
    },
  });
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    // Validation
    if (!patientFirstName || !patientLastName) {
      setError('Patient first and last name are required');
      return;
    }
    
    if (!transcriptText.trim()) {
      setError('Transcript text is required for AI processing');
      return;
    }
    
    const request: CreateEncounterRequest = {
      patient_info: {
        first_name: patientFirstName,
        last_name: patientLastName,
        date_of_birth: patientDob || undefined,
        mrn: patientMrn || undefined,
        gender: patientGender || undefined,
      },
      encounter_type: encounterType,
      chief_complaint: chiefComplaint || undefined,
      transcript_text: transcriptText,
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
                Medical Record Number (MRN)
              </label>
              <input
                id="mrn"
                type="text"
                value={patientMrn}
                onChange={(e) => setPatientMrn(e.target.value)}
                className="input-field"
                placeholder="MRN-12345"
                disabled={isSubmitting}
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
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Encounter Transcript <span className="text-red-500">*</span>
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Paste the patient-physician conversation transcript below. The AI will process this
            to generate the SOAP note, suggest ICD/CPT codes, and check for safety concerns.
          </p>
          
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
            required
          />
          
          <div className="mt-2 flex items-center justify-between text-sm text-gray-500">
            <span>{transcriptText.length} characters</span>
            <span>{transcriptText.split(/\s+/).filter(Boolean).length} words</span>
          </div>
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
