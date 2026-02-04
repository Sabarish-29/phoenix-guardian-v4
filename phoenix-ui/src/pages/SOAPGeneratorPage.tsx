/**
 * SOAP Generator Page
 * 
 * AI-powered clinical documentation tool using the ScribeAgent.
 * Generates structured SOAP notes from encounter data with automatic ICD-10 coding.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { agentsAPI, SOAPRequest, SOAPResponse } from '../api/agents';

interface VitalsData {
  temp: string;
  bp: string;
  hr: string;
  rr: string;
  spo2: string;
}

interface FormData {
  chief_complaint: string;
  vitals: VitalsData;
  symptoms: string;
  exam_findings: string;
  history: string;
}

const initialFormData: FormData = {
  chief_complaint: '',
  vitals: { temp: '', bp: '', hr: '', rr: '', spo2: '' },
  symptoms: '',
  exam_findings: '',
  history: ''
};

export const SOAPGeneratorPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [soapNote, setSoapNote] = useState('');
  const [icdCodes, setIcdCodes] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [generationTime, setGenerationTime] = useState<number | null>(null);
  const [formData, setFormData] = useState<FormData>(initialFormData);

  const handleVitalsChange = (field: keyof VitalsData, value: string) => {
    setFormData(prev => ({
      ...prev,
      vitals: { ...prev.vitals, [field]: value }
    }));
  };

  const handleGenerate = async () => {
    if (!formData.chief_complaint.trim()) {
      setError('Chief complaint is required');
      return;
    }

    setLoading(true);
    setError('');
    const startTime = Date.now();

    try {
      const request: SOAPRequest = {
        chief_complaint: formData.chief_complaint,
        vitals: formData.vitals,
        symptoms: formData.symptoms.split(',').map(s => s.trim()).filter(Boolean),
        exam_findings: formData.exam_findings
      };

      const response: SOAPResponse = await agentsAPI.generateSOAP(request);
      
      setSoapNote(response.soap_note);
      setIcdCodes(response.icd_codes || []);
      setGenerationTime((Date.now() - startTime) / 1000);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to generate SOAP note';
      setError(errorMessage);
      console.error('SOAP generation error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setFormData(initialFormData);
    setSoapNote('');
    setIcdCodes([]);
    setError('');
    setGenerationTime(null);
  };

  const loadSampleData = () => {
    setFormData({
      chief_complaint: 'Cough and fever for 3 days',
      vitals: {
        temp: '101.2F',
        bp: '120/80',
        hr: '88',
        rr: '18',
        spo2: '96%'
      },
      symptoms: 'cough, fever, fatigue, shortness of breath',
      exam_findings: 'Crackles in right lower lung field. Decreased breath sounds at right base. No wheezes. Regular heart rhythm.',
      history: 'Non-smoker. No recent travel. No sick contacts known.'
    });
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(soapNote);
    // Could add a toast notification here
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>🩺 AI SOAP Note Generator</h1>
          <p style={styles.subtitle}>
            Generate structured clinical documentation using Claude AI • Powered by ScribeAgent
          </p>
        </div>
        <button onClick={() => navigate('/dashboard')} style={styles.backButton}>
          ← Back to Dashboard
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div style={styles.errorBox}>
          <strong>⚠️ Error:</strong> {error}
        </div>
      )}

      {/* Main Content */}
      <div style={styles.mainGrid}>
        {/* Input Form */}
        <div style={styles.formSection}>
          <div style={styles.sectionHeader}>
            <h2 style={styles.sectionTitle}>Patient Encounter Data</h2>
            <button onClick={loadSampleData} style={styles.sampleButton}>
              📋 Load Sample Data
            </button>
          </div>

          {/* Chief Complaint */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Chief Complaint *</label>
            <input
              type="text"
              placeholder="e.g., Cough and fever for 3 days"
              value={formData.chief_complaint}
              onChange={(e) => setFormData(prev => ({ ...prev, chief_complaint: e.target.value }))}
              style={styles.input}
            />
          </div>

          {/* Vital Signs */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Vital Signs</label>
            <div style={styles.vitalsGrid}>
              <div style={styles.vitalInput}>
                <span style={styles.vitalLabel}>Temp</span>
                <input
                  type="text"
                  placeholder="101.2F"
                  value={formData.vitals.temp}
                  onChange={(e) => handleVitalsChange('temp', e.target.value)}
                  style={styles.input}
                />
              </div>
              <div style={styles.vitalInput}>
                <span style={styles.vitalLabel}>BP</span>
                <input
                  type="text"
                  placeholder="120/80"
                  value={formData.vitals.bp}
                  onChange={(e) => handleVitalsChange('bp', e.target.value)}
                  style={styles.input}
                />
              </div>
              <div style={styles.vitalInput}>
                <span style={styles.vitalLabel}>HR</span>
                <input
                  type="text"
                  placeholder="88"
                  value={formData.vitals.hr}
                  onChange={(e) => handleVitalsChange('hr', e.target.value)}
                  style={styles.input}
                />
              </div>
              <div style={styles.vitalInput}>
                <span style={styles.vitalLabel}>RR</span>
                <input
                  type="text"
                  placeholder="18"
                  value={formData.vitals.rr}
                  onChange={(e) => handleVitalsChange('rr', e.target.value)}
                  style={styles.input}
                />
              </div>
              <div style={styles.vitalInput}>
                <span style={styles.vitalLabel}>SpO2</span>
                <input
                  type="text"
                  placeholder="96%"
                  value={formData.vitals.spo2}
                  onChange={(e) => handleVitalsChange('spo2', e.target.value)}
                  style={styles.input}
                />
              </div>
            </div>
          </div>

          {/* Symptoms */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Symptoms (comma-separated)</label>
            <input
              type="text"
              placeholder="e.g., cough, fever, fatigue, shortness of breath"
              value={formData.symptoms}
              onChange={(e) => setFormData(prev => ({ ...prev, symptoms: e.target.value }))}
              style={styles.input}
            />
          </div>

          {/* Physical Exam */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Physical Exam Findings</label>
            <textarea
              placeholder="e.g., Crackles in right lower lung field. Decreased breath sounds..."
              value={formData.exam_findings}
              onChange={(e) => setFormData(prev => ({ ...prev, exam_findings: e.target.value }))}
              rows={4}
              style={styles.textarea}
            />
          </div>

          {/* History */}
          <div style={styles.formGroup}>
            <label style={styles.label}>Relevant History (optional)</label>
            <textarea
              placeholder="e.g., Non-smoker. No recent travel..."
              value={formData.history}
              onChange={(e) => setFormData(prev => ({ ...prev, history: e.target.value }))}
              rows={2}
              style={styles.textarea}
            />
          </div>

          {/* Action Buttons */}
          <div style={styles.buttonGroup}>
            <button
              onClick={handleGenerate}
              disabled={loading || !formData.chief_complaint.trim()}
              style={{
                ...styles.primaryButton,
                ...(loading || !formData.chief_complaint.trim() ? styles.disabledButton : {})
              }}
            >
              {loading ? (
                <>
                  <span style={styles.spinner}>⏳</span> Generating...
                </>
              ) : (
                <>🤖 Generate SOAP Note</>
              )}
            </button>
            <button onClick={handleClear} disabled={loading} style={styles.secondaryButton}>
              🗑️ Clear All
            </button>
          </div>
        </div>

        {/* Output Display */}
        <div style={styles.outputSection}>
          <div style={styles.sectionHeader}>
            <h2 style={styles.sectionTitle}>Generated SOAP Note</h2>
            {generationTime !== null && (
              <span style={styles.timeLabel}>Generated in {generationTime.toFixed(1)}s</span>
            )}
          </div>

          {soapNote ? (
            <>
              <div style={styles.soapOutput}>
                <div style={styles.soapHeader}>
                  <span style={styles.soapBadge}>AI Generated</span>
                  <button onClick={copyToClipboard} style={styles.copyButton}>
                    📋 Copy
                  </button>
                </div>
                <pre style={styles.soapText}>{soapNote}</pre>
              </div>

              {icdCodes.length > 0 && (
                <div style={styles.icdSection}>
                  <h3 style={styles.icdTitle}>Suggested ICD-10 Codes</h3>
                  <div style={styles.icdGrid}>
                    {icdCodes.map((code, idx) => (
                      <span key={idx} style={styles.icdCode}>
                        {code}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div style={styles.disclaimer}>
                ⚠️ <strong>Clinical Review Required:</strong> This AI-generated note is for assistance only. 
                All content must be reviewed and verified by a licensed healthcare provider before 
                being entered into the patient's medical record.
              </div>
            </>
          ) : (
            <div style={styles.placeholder}>
              <div style={styles.placeholderIcon}>📝</div>
              <p style={styles.placeholderText}>SOAP note will appear here after generation</p>
              <p style={styles.placeholderHint}>
                Fill in the encounter details on the left and click "Generate SOAP Note"
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Footer Info */}
      <div style={styles.footer}>
        <div style={styles.footerItem}>🔒 HIPAA Compliant</div>
        <div style={styles.footerItem}>🤖 Powered by Claude Sonnet 4</div>
        <div style={styles.footerItem}>📊 Auto ICD-10 Coding</div>
      </div>
    </div>
  );
};

// Styles
const styles: { [key: string]: React.CSSProperties } = {
  container: {
    maxWidth: '1400px',
    margin: '0 auto',
    padding: '24px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '24px'
  },
  title: {
    fontSize: '28px',
    fontWeight: 700,
    margin: 0,
    color: '#1a365d'
  },
  subtitle: {
    fontSize: '14px',
    color: '#64748b',
    margin: '4px 0 0 0'
  },
  backButton: {
    padding: '8px 16px',
    backgroundColor: 'transparent',
    color: '#3b82f6',
    border: '1px solid #3b82f6',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '14px'
  },
  errorBox: {
    padding: '12px 16px',
    backgroundColor: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '8px',
    color: '#dc2626',
    marginBottom: '20px'
  },
  mainGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '32px'
  },
  formSection: {
    backgroundColor: '#ffffff',
    padding: '24px',
    borderRadius: '12px',
    border: '1px solid #e2e8f0',
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
  },
  outputSection: {
    backgroundColor: '#ffffff',
    padding: '24px',
    borderRadius: '12px',
    border: '1px solid #e2e8f0',
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
  },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px'
  },
  sectionTitle: {
    fontSize: '18px',
    fontWeight: 600,
    margin: 0,
    color: '#1e293b'
  },
  sampleButton: {
    padding: '6px 12px',
    backgroundColor: '#f0f9ff',
    color: '#0369a1',
    border: '1px solid #bae6fd',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '13px'
  },
  timeLabel: {
    fontSize: '13px',
    color: '#22c55e',
    fontWeight: 500
  },
  formGroup: {
    marginBottom: '16px'
  },
  label: {
    display: 'block',
    marginBottom: '6px',
    fontWeight: 500,
    fontSize: '14px',
    color: '#374151'
  },
  input: {
    width: '100%',
    padding: '10px 12px',
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    fontSize: '14px',
    boxSizing: 'border-box' as const,
    transition: 'border-color 0.2s'
  },
  textarea: {
    width: '100%',
    padding: '10px 12px',
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    fontSize: '14px',
    fontFamily: 'inherit',
    resize: 'vertical' as const,
    boxSizing: 'border-box' as const
  },
  vitalsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(5, 1fr)',
    gap: '12px'
  },
  vitalInput: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '4px'
  },
  vitalLabel: {
    fontSize: '12px',
    color: '#6b7280',
    fontWeight: 500
  },
  buttonGroup: {
    display: 'flex',
    gap: '12px',
    marginTop: '20px'
  },
  primaryButton: {
    flex: 1,
    padding: '12px 20px',
    backgroundColor: '#2563eb',
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '15px',
    fontWeight: 600,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px'
  },
  secondaryButton: {
    padding: '12px 20px',
    backgroundColor: '#f1f5f9',
    color: '#475569',
    border: '1px solid #e2e8f0',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '14px'
  },
  disabledButton: {
    backgroundColor: '#94a3b8',
    cursor: 'not-allowed'
  },
  spinner: {
    animation: 'spin 1s linear infinite'
  },
  soapOutput: {
    backgroundColor: '#f8fafc',
    borderRadius: '8px',
    border: '1px solid #e2e8f0',
    marginBottom: '16px'
  },
  soapHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 16px',
    borderBottom: '1px solid #e2e8f0',
    backgroundColor: '#f1f5f9'
  },
  soapBadge: {
    fontSize: '12px',
    padding: '4px 8px',
    backgroundColor: '#dbeafe',
    color: '#1d4ed8',
    borderRadius: '4px',
    fontWeight: 500
  },
  copyButton: {
    padding: '4px 10px',
    backgroundColor: 'transparent',
    color: '#64748b',
    border: '1px solid #cbd5e1',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '13px'
  },
  soapText: {
    padding: '16px',
    margin: 0,
    whiteSpace: 'pre-wrap' as const,
    fontFamily: '"SF Mono", "Consolas", monospace',
    fontSize: '13px',
    lineHeight: 1.6,
    maxHeight: '400px',
    overflowY: 'auto' as const,
    color: '#1e293b'
  },
  icdSection: {
    marginBottom: '16px'
  },
  icdTitle: {
    fontSize: '14px',
    fontWeight: 600,
    marginBottom: '12px',
    color: '#374151'
  },
  icdGrid: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: '8px'
  },
  icdCode: {
    padding: '6px 14px',
    backgroundColor: '#ecfdf5',
    color: '#047857',
    borderRadius: '20px',
    fontSize: '13px',
    fontWeight: 600,
    border: '1px solid #a7f3d0'
  },
  disclaimer: {
    padding: '12px 16px',
    backgroundColor: '#fffbeb',
    border: '1px solid #fcd34d',
    borderRadius: '8px',
    fontSize: '13px',
    color: '#92400e',
    lineHeight: 1.5
  },
  placeholder: {
    textAlign: 'center' as const,
    padding: '60px 20px',
    border: '2px dashed #e2e8f0',
    borderRadius: '8px',
    backgroundColor: '#f8fafc'
  },
  placeholderIcon: {
    fontSize: '48px',
    marginBottom: '16px'
  },
  placeholderText: {
    fontSize: '16px',
    color: '#64748b',
    margin: '0 0 8px 0'
  },
  placeholderHint: {
    fontSize: '14px',
    color: '#94a3b8',
    margin: 0
  },
  footer: {
    display: 'flex',
    justifyContent: 'center',
    gap: '32px',
    marginTop: '32px',
    padding: '16px',
    borderTop: '1px solid #e2e8f0'
  },
  footerItem: {
    fontSize: '13px',
    color: '#64748b'
  }
};

export default SOAPGeneratorPage;
