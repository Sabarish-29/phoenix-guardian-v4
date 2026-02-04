/**
 * Review SOAP Note page component.
 * 
 * Allows physicians to:
 * - View AI-generated SOAP note
 * - See safety flags and coding suggestions
 * - Edit the SOAP note
 * - Approve or reject the note
 */

import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  encounterService, 
  Encounter, 
  SOAPSection, 
  SafetyFlag,
  ICDCode,
  CPTCode 
} from '../api/services/encounterService';
import { useAuthStore } from '../stores/authStore';
import { LoadingSpinner, LoadingScreen } from '../components/LoadingSpinner';

/**
 * SOAP Section Editor component
 */
const SOAPEditor: React.FC<{
  section: keyof SOAPSection;
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}> = ({ section, label, value, onChange, disabled }) => {
  const sectionColors: Record<string, string> = {
    subjective: 'border-l-medical-blue',
    objective: 'border-l-medical-green',
    assessment: 'border-l-medical-amber',
    plan: 'border-l-medical-red',
  };
  
  return (
    <div className={`soap-section ${sectionColors[section]}`}>
      <label className="block text-sm font-semibold text-gray-900 mb-2 uppercase tracking-wide">
        {label}
      </label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full min-h-[120px] p-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-y"
        disabled={disabled}
      />
    </div>
  );
};

/**
 * Safety Flag Alert component
 */
const SafetyFlagAlert: React.FC<{ flag: SafetyFlag }> = ({ flag }) => {
  const severityConfig: Record<string, { bg: string; border: string; icon: string }> = {
    critical: { bg: 'bg-red-50', border: 'border-red-500', icon: '🚨' },
    high: { bg: 'bg-orange-50', border: 'border-orange-500', icon: '⚠️' },
    medium: { bg: 'bg-yellow-50', border: 'border-yellow-500', icon: '⚡' },
    low: { bg: 'bg-blue-50', border: 'border-blue-500', icon: 'ℹ️' },
  };
  
  const config = severityConfig[flag.severity] || severityConfig.low;
  
  return (
    <div className={`${config.bg} border-l-4 ${config.border} p-4 rounded-r-lg`}>
      <div className="flex items-start">
        <span className="text-xl mr-2">{config.icon}</span>
        <div>
          <p className="font-medium text-gray-900">{flag.message}</p>
          {flag.recommendation && (
            <p className="mt-1 text-sm text-gray-600">{flag.recommendation}</p>
          )}
          <p className="mt-1 text-xs text-gray-500">
            Code: {flag.code} | Category: {flag.category}
          </p>
        </div>
      </div>
    </div>
  );
};

/**
 * Code suggestion component (ICD/CPT)
 */
const CodeSuggestion: React.FC<{
  code: ICDCode | CPTCode;
  type: 'ICD' | 'CPT';
}> = ({ code, type }) => {
  const confidenceColor = 
    code.confidence >= 0.8 ? 'text-green-600' :
    code.confidence >= 0.6 ? 'text-yellow-600' : 'text-red-600';
  
  return (
    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
      <div>
        <span className="font-mono font-semibold text-gray-900">{code.code}</span>
        <p className="text-sm text-gray-600">{code.description}</p>
      </div>
      <div className="text-right">
        <span className={`text-sm font-medium ${confidenceColor}`}>
          {Math.round(code.confidence * 100)}%
        </span>
        <p className="text-xs text-gray-500">{type}</p>
      </div>
    </div>
  );
};

export const ReviewSOAPNotePage: React.FC = () => {
  const { uuid } = useParams<{ uuid: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { canSignNotes, getFullName } = useAuthStore();
  
  // SOAP note editing state
  const [editedSOAP, setEditedSOAP] = useState<SOAPSection | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [signature, setSignature] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);
  
  // Fetch encounter data
  const { data: encounter, isLoading, error } = useQuery({
    queryKey: ['encounter', uuid],
    queryFn: () => encounterService.getEncounter(uuid!),
    enabled: !!uuid,
    refetchInterval: (query) => {
      // Poll while processing
      const data = query.state.data;
      if (data && ['processing', 'scribe_processing'].includes(data.status)) {
        return 2000; // Poll every 2 seconds
      }
      return false;
    },
  });
  
  // Update SOAP mutation
  const updateMutation = useMutation({
    mutationFn: (data: { encounterId: number; soap: SOAPSection }) =>
      encounterService.updateSOAPNote(data.encounterId, { soap_note: data.soap }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['encounter', uuid] });
      setIsEditing(false);
    },
  });
  
  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: (data: { encounterId: number; signature: string }) =>
      encounterService.approveSOAPNote(data.encounterId, { signature: data.signature }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['encounter', uuid] });
      navigate('/dashboard');
    },
  });
  
  // Reject mutation
  const rejectMutation = useMutation({
    mutationFn: (data: { encounterId: number; reason: string }) =>
      encounterService.rejectSOAPNote(data.encounterId, { reason: data.reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['encounter', uuid] });
      setShowRejectModal(false);
      navigate('/dashboard');
    },
  });
  
  // Initialize edited SOAP when data loads
  React.useEffect(() => {
    if (encounter?.soapNote && !editedSOAP) {
      setEditedSOAP(encounter.soapNote);
    }
  }, [encounter?.soapNote, editedSOAP]);
  
  if (isLoading) {
    return <LoadingScreen message="Loading encounter..." />;
  }
  
  if (error || !encounter) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">Encounter not found</h2>
        <p className="mt-2 text-gray-500">The requested encounter could not be loaded.</p>
        <Link to="/dashboard" className="mt-4 inline-block btn-primary">
          Return to Dashboard
        </Link>
      </div>
    );
  }
  
  const soapNote = editedSOAP || encounter.soapNote;
  const isProcessing = ['processing', 'scribe_processing'].includes(encounter.status);
  const canEdit = ['awaiting_review', 'rejected'].includes(encounter.status) && canSignNotes();
  const canApprove = encounter.status === 'awaiting_review' && canSignNotes();
  
  const handleUpdateSOAP = (section: keyof SOAPSection, value: string) => {
    if (editedSOAP) {
      setEditedSOAP({ ...editedSOAP, [section]: value });
    }
  };
  
  const handleSaveChanges = () => {
    if (editedSOAP && encounter) {
      updateMutation.mutate({ encounterId: encounter.id, soap: editedSOAP });
    }
  };
  
  const handleApprove = () => {
    if (!signature.trim()) {
      return;
    }
    approveMutation.mutate({ encounterId: encounter.id, signature });
  };
  
  const handleReject = () => {
    if (!rejectReason.trim()) {
      return;
    }
    rejectMutation.mutate({ encounterId: encounter.id, reason: rejectReason });
  };
  
  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8 flex items-start justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <Link to="/dashboard" className="text-gray-400 hover:text-gray-600">
              <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">Review SOAP Note</h1>
          </div>
          <p className="mt-1 text-gray-500">
            Patient: {encounter.patientFirstName} {encounter.patientLastName}
            {encounter.patientMrn && ` | MRN: ${encounter.patientMrn}`}
          </p>
        </div>
        
        {/* Confidence Score */}
        {encounter.aiConfidenceScore && (
          <div className="text-right">
            <p className="text-sm text-gray-500">AI Confidence</p>
            <p className={`text-2xl font-bold ${
              encounter.aiConfidenceScore >= 0.8 ? 'text-green-600' :
              encounter.aiConfidenceScore >= 0.6 ? 'text-yellow-600' : 'text-red-600'
            }`}>
              {Math.round(encounter.aiConfidenceScore * 100)}%
            </p>
          </div>
        )}
      </div>
      
      {/* Processing State */}
      {isProcessing && (
        <div className="card mb-6 bg-blue-50 border-blue-200">
          <div className="flex items-center">
            <LoadingSpinner size="md" className="mr-4" />
            <div>
              <h3 className="font-semibold text-blue-900">AI Processing in Progress</h3>
              <p className="text-sm text-blue-700">
                The AI is analyzing the transcript and generating the SOAP note...
              </p>
            </div>
          </div>
        </div>
      )}
      
      {/* Safety Flags */}
      {encounter.safetyFlags && encounter.safetyFlags.length > 0 && (
        <div className="card mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <span className="mr-2">🛡️</span>
            Safety Alerts ({encounter.safetyFlags.length})
          </h2>
          <div className="space-y-3">
            {encounter.safetyFlags.map((flag, index) => (
              <SafetyFlagAlert key={index} flag={flag} />
            ))}
          </div>
        </div>
      )}
      
      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* SOAP Note Section */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">SOAP Note</h2>
              {canEdit && !isEditing && (
                <button
                  onClick={() => setIsEditing(true)}
                  className="text-primary-600 hover:text-primary-700 text-sm font-medium"
                >
                  Edit Note
                </button>
              )}
            </div>
            
            {soapNote ? (
              <div className="space-y-4">
                <SOAPEditor
                  section="subjective"
                  label="Subjective"
                  value={soapNote.subjective}
                  onChange={(v) => handleUpdateSOAP('subjective', v)}
                  disabled={!isEditing}
                />
                <SOAPEditor
                  section="objective"
                  label="Objective"
                  value={soapNote.objective}
                  onChange={(v) => handleUpdateSOAP('objective', v)}
                  disabled={!isEditing}
                />
                <SOAPEditor
                  section="assessment"
                  label="Assessment"
                  value={soapNote.assessment}
                  onChange={(v) => handleUpdateSOAP('assessment', v)}
                  disabled={!isEditing}
                />
                <SOAPEditor
                  section="plan"
                  label="Plan"
                  value={soapNote.plan}
                  onChange={(v) => handleUpdateSOAP('plan', v)}
                  disabled={!isEditing}
                />
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">
                {isProcessing ? 'SOAP note is being generated...' : 'No SOAP note available.'}
              </p>
            )}
            
            {/* Edit Actions */}
            {isEditing && (
              <div className="mt-4 flex items-center justify-end space-x-3">
                <button
                  onClick={() => {
                    setEditedSOAP(encounter.soapNote);
                    setIsEditing(false);
                  }}
                  className="btn-secondary"
                  disabled={updateMutation.isPending}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveChanges}
                  className="btn-primary"
                  disabled={updateMutation.isPending}
                >
                  {updateMutation.isPending ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2" />
                      Saving...
                    </>
                  ) : (
                    'Save Changes'
                  )}
                </button>
              </div>
            )}
          </div>
          
          {/* Original Transcript */}
          {encounter.transcriptText && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Original Transcript</h2>
              <div className="bg-gray-50 rounded-lg p-4 max-h-64 overflow-y-auto">
                <pre className="whitespace-pre-wrap text-sm text-gray-700 font-mono">
                  {encounter.transcriptText}
                </pre>
              </div>
            </div>
          )}
        </div>
        
        {/* Sidebar */}
        <div className="space-y-6">
          {/* Coding Suggestions */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Suggested Codes</h2>
            
            {/* ICD-10 Codes */}
            {encounter.icdCodes && encounter.icdCodes.length > 0 && (
              <div className="mb-4">
                <h3 className="text-sm font-medium text-gray-700 mb-2">ICD-10 Diagnosis</h3>
                <div className="space-y-2">
                  {encounter.icdCodes.map((code, index) => (
                    <CodeSuggestion key={index} code={code} type="ICD" />
                  ))}
                </div>
              </div>
            )}
            
            {/* CPT Codes */}
            {encounter.cptCodes && encounter.cptCodes.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">CPT Procedure</h3>
                <div className="space-y-2">
                  {encounter.cptCodes.map((code, index) => (
                    <CodeSuggestion key={index} code={code} type="CPT" />
                  ))}
                </div>
              </div>
            )}
            
            {(!encounter.icdCodes || encounter.icdCodes.length === 0) &&
             (!encounter.cptCodes || encounter.cptCodes.length === 0) && (
              <p className="text-gray-500 text-sm text-center py-4">
                No coding suggestions available.
              </p>
            )}
          </div>
          
          {/* Approval Section */}
          {canApprove && !isEditing && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Sign & Approve</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Electronic Signature
                  </label>
                  <input
                    type="text"
                    value={signature}
                    onChange={(e) => setSignature(e.target.value)}
                    placeholder={`/s/ ${getFullName()}`}
                    className="input-field"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    By signing, you attest that you have reviewed and approve this documentation.
                  </p>
                </div>
                
                <button
                  onClick={handleApprove}
                  disabled={!signature.trim() || approveMutation.isPending}
                  className="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {approveMutation.isPending ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2 inline" />
                      Approving...
                    </>
                  ) : (
                    '✓ Approve & Sign'
                  )}
                </button>
                
                <button
                  onClick={() => setShowRejectModal(true)}
                  className="w-full btn-danger"
                  disabled={approveMutation.isPending}
                >
                  Reject Note
                </button>
              </div>
            </div>
          )}
          
          {/* Encounter Info */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Encounter Details</h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Type</dt>
                <dd className="text-gray-900">{encounter.encounterType || 'N/A'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Chief Complaint</dt>
                <dd className="text-gray-900">{encounter.chiefComplaint || 'N/A'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Created</dt>
                <dd className="text-gray-900">
                  {new Date(encounter.createdAt).toLocaleString()}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Status</dt>
                <dd className="text-gray-900 capitalize">{encounter.status.replace(/_/g, ' ')}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
      
      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Reject SOAP Note</h3>
            <p className="text-sm text-gray-500 mb-4">
              Please provide a reason for rejecting this note. It will be sent back for revision.
            </p>
            
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Enter rejection reason..."
              className="input-field min-h-[100px]"
            />
            
            <div className="mt-4 flex items-center justify-end space-x-3">
              <button
                onClick={() => setShowRejectModal(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={!rejectReason.trim() || rejectMutation.isPending}
                className="btn-danger"
              >
                {rejectMutation.isPending ? 'Rejecting...' : 'Reject Note'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReviewSOAPNotePage;
