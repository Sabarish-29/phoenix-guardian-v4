/**
 * Phoenix Guardian Mobile - Week 23-24
 * ApprovalScreen: Final approval and EHR submission interface.
 * 
 * Features:
 * - Complete SOAP note preview
 * - Final review before submission
 * - One-tap EHR write
 * - Signature capture (optional)
 * - Confirmation with audit trail
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  Modal,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';

// Types
interface SOAPSection {
  key: 'subjective' | 'objective' | 'assessment' | 'plan';
  title: string;
  content: string;
}

interface EncounterSummary {
  encounterId: string;
  patientId: string;
  patientName: string;
  patientMRN: string;
  encounterDate: string;
  encounterType: string;
  sections: SOAPSection[];
  wordCount: number;
  aiConfidence: number;
  physicianEdits: number;
  duration: string;
}

interface SubmissionResult {
  success: boolean;
  ehrConfirmationId?: string;
  timestamp?: string;
  message?: string;
}

type RootStackParamList = {
  Approval: { encounterId: string };
  EncounterList: undefined;
  Review: { encounterId: string };
};

type ApprovalScreenNavigationProp = NativeStackNavigationProp<RootStackParamList, 'Approval'>;
type ApprovalScreenRouteProp = RouteProp<RootStackParamList, 'Approval'>;

// Confirmation Modal Component
interface ConfirmationModalProps {
  visible: boolean;
  result: SubmissionResult | null;
  onClose: () => void;
}

const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  visible,
  result,
  onClose,
}) => {
  if (!result) return null;

  return (
    <Modal visible={visible} transparent animationType="fade">
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          {result.success ? (
            <>
              <View style={styles.successIcon}>
                <Text style={styles.successIconText}>✓</Text>
              </View>
              <Text style={styles.modalTitle}>Submitted to EHR</Text>
              <Text style={styles.modalMessage}>
                The SOAP note has been successfully submitted to the patient's medical record.
              </Text>
              <View style={styles.confirmationDetails}>
                <View style={styles.confirmationRow}>
                  <Text style={styles.confirmationLabel}>Confirmation ID</Text>
                  <Text style={styles.confirmationValue}>{result.ehrConfirmationId}</Text>
                </View>
                <View style={styles.confirmationRow}>
                  <Text style={styles.confirmationLabel}>Submitted At</Text>
                  <Text style={styles.confirmationValue}>
                    {result.timestamp ? new Date(result.timestamp).toLocaleString() : 'N/A'}
                  </Text>
                </View>
              </View>
            </>
          ) : (
            <>
              <View style={styles.errorIcon}>
                <Text style={styles.errorIconText}>!</Text>
              </View>
              <Text style={styles.modalTitle}>Submission Failed</Text>
              <Text style={styles.modalMessage}>
                {result.message || 'Failed to submit to EHR. Please try again.'}
              </Text>
            </>
          )}
          <TouchableOpacity style={styles.modalButton} onPress={onClose}>
            <Text style={styles.modalButtonText}>
              {result.success ? 'Done' : 'Try Again'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
};

// Main ApprovalScreen Component
const ApprovalScreen: React.FC = () => {
  const navigation = useNavigation<ApprovalScreenNavigationProp>();
  const route = useRoute<ApprovalScreenRouteProp>();
  const { encounterId } = route.params;

  const [encounter, setEncounter] = useState<EncounterSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [submissionResult, setSubmissionResult] = useState<SubmissionResult | null>(null);
  const [attestationChecked, setAttestationChecked] = useState(false);

  // Load encounter data
  useEffect(() => {
    loadEncounter();
  }, [encounterId]);

  const loadEncounter = async () => {
    setIsLoading(true);
    try {
      // In production, fetch from API
      await new Promise(resolve => setTimeout(resolve, 500));

      const mockEncounter: EncounterSummary = {
        encounterId,
        patientId: 'P12345',
        patientName: 'John Smith',
        patientMRN: 'MRN-2024-12345',
        encounterDate: new Date().toISOString(),
        encounterType: 'Office Visit',
        wordCount: 342,
        aiConfidence: 0.93,
        physicianEdits: 2,
        duration: '4:32',
        sections: [
          {
            key: 'subjective',
            title: 'Subjective',
            content: 'Patient presents with chief complaint of persistent cough for 5 days. Reports associated symptoms of mild fever, fatigue, and body aches. Denies shortness of breath, chest pain, or hemoptysis. No known sick contacts. No recent travel.',
          },
          {
            key: 'objective',
            title: 'Objective',
            content: 'Vitals: T 100.4°F, HR 82, BP 128/78, RR 16, SpO2 97% on RA\nGeneral: Alert, oriented, mild fatigue\nHEENT: Mild pharyngeal erythema, no exudates\nLungs: Scattered rhonchi bilateral, no wheezing\nCardiac: RRR, no murmurs',
          },
          {
            key: 'assessment',
            title: 'Assessment',
            content: '1. Acute upper respiratory infection, likely viral\n2. Low-grade fever, resolving\n3. Rule out early pneumonia given persistent symptoms',
          },
          {
            key: 'plan',
            title: 'Plan',
            content: '1. Supportive care with rest and hydration\n2. OTC antipyretics PRN for fever\n3. Cough suppressant as needed\n4. Return if symptoms worsen or persist >7 days\n5. Consider chest X-ray if no improvement in 48-72 hours',
          },
        ],
      };

      setEncounter(mockEncounter);
    } catch (error) {
      console.error('Failed to load encounter:', error);
      Alert.alert('Error', 'Failed to load encounter data.');
    } finally {
      setIsLoading(false);
    }
  };

  // Submit to EHR
  const submitToEHR = useCallback(async () => {
    if (!encounter) return;

    if (!attestationChecked) {
      Alert.alert(
        'Attestation Required',
        'Please confirm you have reviewed and approve this documentation.',
        [{ text: 'OK' }]
      );
      return;
    }

    setIsSubmitting(true);
    try {
      // In production, call API to submit to EHR
      await new Promise(resolve => setTimeout(resolve, 1500));

      // Simulate successful submission
      const result: SubmissionResult = {
        success: true,
        ehrConfirmationId: `EHR-${Date.now().toString(36).toUpperCase()}`,
        timestamp: new Date().toISOString(),
      };

      setSubmissionResult(result);
      setShowConfirmation(true);
    } catch (error) {
      console.error('Failed to submit to EHR:', error);
      setSubmissionResult({
        success: false,
        message: 'Network error. Please check your connection and try again.',
      });
      setShowConfirmation(true);
    } finally {
      setIsSubmitting(false);
    }
  }, [encounter, attestationChecked]);

  // Handle confirmation modal close
  const handleConfirmationClose = useCallback(() => {
    setShowConfirmation(false);
    if (submissionResult?.success) {
      navigation.navigate('EncounterList');
    }
  }, [submissionResult, navigation]);

  // Calculate confidence display
  const getConfidenceLevel = (confidence: number): { label: string; color: string } => {
    if (confidence >= 0.9) return { label: 'High', color: '#22C55E' };
    if (confidence >= 0.7) return { label: 'Medium', color: '#F59E0B' };
    return { label: 'Low', color: '#EF4444' };
  };

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#3B82F6" />
        <Text style={styles.loadingText}>Loading encounter...</Text>
      </View>
    );
  }

  if (!encounter) {
    return (
      <View style={styles.errorContainer}>
        <Text style={styles.errorText}>Failed to load encounter</Text>
        <TouchableOpacity style={styles.retryButton} onPress={loadEncounter}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const confidenceInfo = getConfidenceLevel(encounter.aiConfidence);

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backButton}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Approve & Submit</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent}>
        {/* Patient Info Card */}
        <View style={styles.patientCard}>
          <View style={styles.patientHeader}>
            <Text style={styles.patientName}>{encounter.patientName}</Text>
            <Text style={styles.patientMRN}>{encounter.patientMRN}</Text>
          </View>
          <View style={styles.patientDetails}>
            <View style={styles.detailItem}>
              <Text style={styles.detailLabel}>Encounter Type</Text>
              <Text style={styles.detailValue}>{encounter.encounterType}</Text>
            </View>
            <View style={styles.detailItem}>
              <Text style={styles.detailLabel}>Date</Text>
              <Text style={styles.detailValue}>
                {new Date(encounter.encounterDate).toLocaleDateString()}
              </Text>
            </View>
          </View>
        </View>

        {/* Stats Card */}
        <View style={styles.statsCard}>
          <View style={styles.statItem}>
            <Text style={styles.statValue}>{encounter.wordCount}</Text>
            <Text style={styles.statLabel}>Words</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <View style={styles.confidenceBadge}>
              <View
                style={[styles.confidenceDot, { backgroundColor: confidenceInfo.color }]}
              />
              <Text style={[styles.statValue, { color: confidenceInfo.color }]}>
                {Math.round(encounter.aiConfidence * 100)}%
              </Text>
            </View>
            <Text style={styles.statLabel}>AI Confidence</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={styles.statValue}>{encounter.physicianEdits}</Text>
            <Text style={styles.statLabel}>Edits Made</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={styles.statValue}>{encounter.duration}</Text>
            <Text style={styles.statLabel}>Duration</Text>
          </View>
        </View>

        {/* SOAP Note Preview */}
        <View style={styles.soapPreview}>
          <View style={styles.soapHeader}>
            <Text style={styles.soapTitle}>SOAP Note Preview</Text>
            <TouchableOpacity
              onPress={() => navigation.navigate('Review', { encounterId })}
            >
              <Text style={styles.editLink}>Edit</Text>
            </TouchableOpacity>
          </View>
          {encounter.sections.map(section => (
            <View key={section.key} style={styles.soapSection}>
              <Text style={styles.soapSectionTitle}>{section.title}</Text>
              <Text style={styles.soapSectionContent}>{section.content}</Text>
            </View>
          ))}
        </View>

        {/* Attestation */}
        <View style={styles.attestationCard}>
          <TouchableOpacity
            style={styles.attestationRow}
            onPress={() => setAttestationChecked(!attestationChecked)}
          >
            <View
              style={[
                styles.checkbox,
                attestationChecked && styles.checkboxChecked,
              ]}
            >
              {attestationChecked && <Text style={styles.checkmark}>✓</Text>}
            </View>
            <Text style={styles.attestationText}>
              I have reviewed this documentation and attest that it accurately 
              reflects the patient encounter. I approve submission to the 
              electronic health record.
            </Text>
          </TouchableOpacity>
        </View>

        {/* Legal Notice */}
        <Text style={styles.legalNotice}>
          By submitting, you confirm that this documentation complies with 
          your institution's policies and applicable healthcare regulations.
        </Text>
      </ScrollView>

      {/* Footer Actions */}
      <View style={styles.footer}>
        <TouchableOpacity
          style={styles.cancelButton}
          onPress={() => navigation.goBack()}
        >
          <Text style={styles.cancelButtonText}>Cancel</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[
            styles.submitButton,
            !attestationChecked && styles.submitButtonDisabled,
          ]}
          onPress={submitToEHR}
          disabled={isSubmitting || !attestationChecked}
        >
          {isSubmitting ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={styles.submitButtonText}>Submit to EHR</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Confirmation Modal */}
      <ConfirmationModal
        visible={showConfirmation}
        result={submissionResult}
        onClose={handleConfirmationClose}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F3F4F6',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#6B7280',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
  },
  errorText: {
    fontSize: 16,
    color: '#EF4444',
    marginBottom: 16,
  },
  retryButton: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: '#3B82F6',
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backButton: {
    fontSize: 16,
    color: '#3B82F6',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1F2937',
  },
  headerSpacer: {
    width: 60,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
  },
  patientCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  patientHeader: {
    marginBottom: 12,
  },
  patientName: {
    fontSize: 20,
    fontWeight: '600',
    color: '#1F2937',
  },
  patientMRN: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
  patientDetails: {
    flexDirection: 'row',
  },
  detailItem: {
    marginRight: 24,
  },
  detailLabel: {
    fontSize: 12,
    color: '#9CA3AF',
    marginBottom: 2,
  },
  detailValue: {
    fontSize: 14,
    color: '#1F2937',
    fontWeight: '500',
  },
  statsCard: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#1F2937',
  },
  statLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 4,
  },
  statDivider: {
    width: 1,
    backgroundColor: '#E5E7EB',
    marginHorizontal: 8,
  },
  confidenceBadge: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  confidenceDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  soapPreview: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  soapHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  soapTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1F2937',
  },
  editLink: {
    fontSize: 14,
    color: '#3B82F6',
    fontWeight: '500',
  },
  soapSection: {
    marginBottom: 16,
  },
  soapSectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#4B5563',
    marginBottom: 6,
  },
  soapSectionContent: {
    fontSize: 14,
    color: '#374151',
    lineHeight: 20,
  },
  attestationCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  attestationRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#D1D5DB',
    marginRight: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkboxChecked: {
    backgroundColor: '#3B82F6',
    borderColor: '#3B82F6',
  },
  checkmark: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
  },
  attestationText: {
    flex: 1,
    fontSize: 14,
    color: '#374151',
    lineHeight: 20,
  },
  legalNotice: {
    fontSize: 12,
    color: '#9CA3AF',
    textAlign: 'center',
    marginTop: 8,
    marginBottom: 16,
    paddingHorizontal: 16,
  },
  footer: {
    flexDirection: 'row',
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  cancelButton: {
    flex: 1,
    paddingVertical: 14,
    marginRight: 8,
    backgroundColor: '#F3F4F6',
    borderRadius: 8,
    alignItems: 'center',
  },
  cancelButtonText: {
    fontSize: 16,
    color: '#6B7280',
    fontWeight: '600',
  },
  submitButton: {
    flex: 2,
    paddingVertical: 14,
    marginLeft: 8,
    backgroundColor: '#22C55E',
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  submitButtonDisabled: {
    backgroundColor: '#9CA3AF',
  },
  submitButtonText: {
    fontSize: 16,
    color: '#FFFFFF',
    fontWeight: '600',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 24,
    width: '100%',
    maxWidth: 320,
    alignItems: 'center',
  },
  successIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#D1FAE5',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  successIconText: {
    fontSize: 32,
    color: '#22C55E',
  },
  errorIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#FEE2E2',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  errorIconText: {
    fontSize: 32,
    color: '#EF4444',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#1F2937',
    marginBottom: 8,
    textAlign: 'center',
  },
  modalMessage: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
    marginBottom: 16,
    lineHeight: 20,
  },
  confirmationDetails: {
    width: '100%',
    backgroundColor: '#F9FAFB',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  confirmationRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  confirmationLabel: {
    fontSize: 12,
    color: '#6B7280',
  },
  confirmationValue: {
    fontSize: 12,
    color: '#1F2937',
    fontWeight: '600',
  },
  modalButton: {
    width: '100%',
    paddingVertical: 12,
    backgroundColor: '#3B82F6',
    borderRadius: 8,
    alignItems: 'center',
  },
  modalButtonText: {
    fontSize: 16,
    color: '#FFFFFF',
    fontWeight: '600',
  },
});

export default ApprovalScreen;
