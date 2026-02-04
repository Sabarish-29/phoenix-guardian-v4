/**
 * Phoenix Guardian Mobile - Week 23-24
 * ReviewScreen: SOAP note review and editing interface.
 * 
 * Features:
 * - Section-by-section SOAP display
 * - Inline editing with diff highlighting
 * - AI confidence indicators
 * - Voice-to-text additions
 * - Save draft functionality
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';

// Types
interface SOAPSection {
  key: 'subjective' | 'objective' | 'assessment' | 'plan';
  title: string;
  content: string;
  originalContent: string;
  isEditing: boolean;
  confidence: number;
  suggestions?: string[];
}

interface SOAPNote {
  encounterId: string;
  patientId: string;
  patientName: string;
  encounterDate: string;
  sections: SOAPSection[];
  status: 'draft' | 'reviewed' | 'approved';
  lastModified: string;
}

type RootStackParamList = {
  Review: { encounterId: string };
  Approval: { encounterId: string };
  EncounterList: undefined;
};

type ReviewScreenNavigationProp = NativeStackNavigationProp<RootStackParamList, 'Review'>;
type ReviewScreenRouteProp = RouteProp<RootStackParamList, 'Review'>;

// Section Header Component
interface SectionHeaderProps {
  title: string;
  confidence: number;
  isEditing: boolean;
  onEditToggle: () => void;
  hasChanges: boolean;
}

const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  confidence,
  isEditing,
  onEditToggle,
  hasChanges,
}) => {
  const getConfidenceColor = (conf: number): string => {
    if (conf >= 0.9) return '#22C55E';
    if (conf >= 0.7) return '#F59E0B';
    return '#EF4444';
  };

  return (
    <View style={styles.sectionHeader}>
      <View style={styles.sectionTitleRow}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {hasChanges && (
          <View style={styles.changedBadge}>
            <Text style={styles.changedBadgeText}>Modified</Text>
          </View>
        )}
      </View>
      <View style={styles.sectionActions}>
        <View style={styles.confidenceContainer}>
          <View
            style={[
              styles.confidenceDot,
              { backgroundColor: getConfidenceColor(confidence) },
            ]}
          />
          <Text style={styles.confidenceText}>
            {Math.round(confidence * 100)}%
          </Text>
        </View>
        <TouchableOpacity
          style={[styles.editButton, isEditing && styles.editButtonActive]}
          onPress={onEditToggle}
        >
          <Text style={[styles.editButtonText, isEditing && styles.editButtonTextActive]}>
            {isEditing ? 'Done' : 'Edit'}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

// Diff Viewer Component
interface DiffViewerProps {
  original: string;
  current: string;
}

const DiffViewer: React.FC<DiffViewerProps> = ({ original, current }) => {
  if (original === current) {
    return null;
  }

  return (
    <View style={styles.diffContainer}>
      <Text style={styles.diffLabel}>Original:</Text>
      <Text style={styles.diffOriginal}>{original}</Text>
    </View>
  );
};

// Section Editor Component
interface SectionEditorProps {
  section: SOAPSection;
  onContentChange: (content: string) => void;
  onRevert: () => void;
}

const SectionEditor: React.FC<SectionEditorProps> = ({
  section,
  onContentChange,
  onRevert,
}) => {
  const hasChanges = section.content !== section.originalContent;

  return (
    <View style={styles.editorContainer}>
      <TextInput
        style={styles.editorInput}
        multiline
        value={section.content}
        onChangeText={onContentChange}
        placeholder={`Enter ${section.title.toLowerCase()} notes...`}
        placeholderTextColor="#9CA3AF"
      />
      {hasChanges && (
        <View style={styles.editorActions}>
          <TouchableOpacity style={styles.revertButton} onPress={onRevert}>
            <Text style={styles.revertButtonText}>Revert to Original</Text>
          </TouchableOpacity>
          <DiffViewer original={section.originalContent} current={section.content} />
        </View>
      )}
      {section.suggestions && section.suggestions.length > 0 && (
        <View style={styles.suggestionsContainer}>
          <Text style={styles.suggestionsLabel}>AI Suggestions:</Text>
          {section.suggestions.map((suggestion, index) => (
            <TouchableOpacity
              key={index}
              style={styles.suggestionItem}
              onPress={() => onContentChange(section.content + ' ' + suggestion)}
            >
              <Text style={styles.suggestionText}>+ {suggestion}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  );
};

// Main ReviewScreen Component
const ReviewScreen: React.FC = () => {
  const navigation = useNavigation<ReviewScreenNavigationProp>();
  const route = useRoute<ReviewScreenRouteProp>();
  const { encounterId } = route.params;

  const [soapNote, setSoapNote] = useState<SOAPNote | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const scrollViewRef = useRef<ScrollView>(null);

  // Load SOAP note
  useEffect(() => {
    loadSOAPNote();
  }, [encounterId]);

  const loadSOAPNote = async () => {
    setIsLoading(true);
    try {
      // In production, this would fetch from API or local storage
      // For now, simulate loading
      await new Promise(resolve => setTimeout(resolve, 500));

      const mockNote: SOAPNote = {
        encounterId,
        patientId: 'P12345',
        patientName: 'John Smith',
        encounterDate: new Date().toISOString(),
        status: 'draft',
        lastModified: new Date().toISOString(),
        sections: [
          {
            key: 'subjective',
            title: 'Subjective',
            content: 'Patient presents with chief complaint of persistent cough for 5 days. Reports associated symptoms of mild fever, fatigue, and body aches. Denies shortness of breath, chest pain, or hemoptysis. No known sick contacts. No recent travel.',
            originalContent: 'Patient presents with chief complaint of persistent cough for 5 days. Reports associated symptoms of mild fever, fatigue, and body aches. Denies shortness of breath, chest pain, or hemoptysis. No known sick contacts. No recent travel.',
            isEditing: false,
            confidence: 0.95,
            suggestions: ['Add duration of fever', 'Include medication history'],
          },
          {
            key: 'objective',
            title: 'Objective',
            content: 'Vitals: T 100.4°F, HR 82, BP 128/78, RR 16, SpO2 97% on RA\nGeneral: Alert, oriented, mild fatigue\nHEENT: Mild pharyngeal erythema, no exudates\nLungs: Scattered rhonchi bilateral, no wheezing\nCardiac: RRR, no murmurs',
            originalContent: 'Vitals: T 100.4°F, HR 82, BP 128/78, RR 16, SpO2 97% on RA\nGeneral: Alert, oriented, mild fatigue\nHEENT: Mild pharyngeal erythema, no exudates\nLungs: Scattered rhonchi bilateral, no wheezing\nCardiac: RRR, no murmurs',
            isEditing: false,
            confidence: 0.92,
          },
          {
            key: 'assessment',
            title: 'Assessment',
            content: '1. Acute upper respiratory infection, likely viral\n2. Low-grade fever, resolving\n3. Rule out early pneumonia given persistent symptoms',
            originalContent: '1. Acute upper respiratory infection, likely viral\n2. Low-grade fever, resolving\n3. Rule out early pneumonia given persistent symptoms',
            isEditing: false,
            confidence: 0.88,
            suggestions: ['Consider COVID-19 testing', 'Add differential diagnoses'],
          },
          {
            key: 'plan',
            title: 'Plan',
            content: '1. Supportive care with rest and hydration\n2. OTC antipyretics PRN for fever\n3. Cough suppressant as needed\n4. Return if symptoms worsen or persist >7 days\n5. Consider chest X-ray if no improvement in 48-72 hours',
            originalContent: '1. Supportive care with rest and hydration\n2. OTC antipyretics PRN for fever\n3. Cough suppressant as needed\n4. Return if symptoms worsen or persist >7 days\n5. Consider chest X-ray if no improvement in 48-72 hours',
            isEditing: false,
            confidence: 0.94,
          },
        ],
      };

      setSoapNote(mockNote);
    } catch (error) {
      console.error('Failed to load SOAP note:', error);
      Alert.alert('Error', 'Failed to load encounter. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Toggle section editing
  const toggleSectionEditing = useCallback((sectionKey: string) => {
    if (!soapNote) return;

    setSoapNote(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        sections: prev.sections.map(section =>
          section.key === sectionKey
            ? { ...section, isEditing: !section.isEditing }
            : section
        ),
      };
    });
  }, [soapNote]);

  // Update section content
  const updateSectionContent = useCallback((sectionKey: string, content: string) => {
    if (!soapNote) return;

    setSoapNote(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        lastModified: new Date().toISOString(),
        sections: prev.sections.map(section =>
          section.key === sectionKey
            ? { ...section, content }
            : section
        ),
      };
    });
  }, [soapNote]);

  // Revert section to original
  const revertSection = useCallback((sectionKey: string) => {
    if (!soapNote) return;

    Alert.alert(
      'Revert Changes',
      'Are you sure you want to revert this section to the original AI-generated content?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Revert',
          style: 'destructive',
          onPress: () => {
            setSoapNote(prev => {
              if (!prev) return prev;
              return {
                ...prev,
                sections: prev.sections.map(section =>
                  section.key === sectionKey
                    ? { ...section, content: section.originalContent }
                    : section
                ),
              };
            });
          },
        },
      ]
    );
  }, [soapNote]);

  // Save draft
  const saveDraft = useCallback(async () => {
    if (!soapNote) return;

    setIsSaving(true);
    try {
      // In production, save to API and/or local storage
      await new Promise(resolve => setTimeout(resolve, 500));
      
      Alert.alert('Saved', 'Draft saved successfully.');
    } catch (error) {
      console.error('Failed to save draft:', error);
      Alert.alert('Error', 'Failed to save draft. Please try again.');
    } finally {
      setIsSaving(false);
    }
  }, [soapNote]);

  // Proceed to approval
  const proceedToApproval = useCallback(() => {
    if (!soapNote) return;

    // Check for any sections still being edited
    const editingSections = soapNote.sections.filter(s => s.isEditing);
    if (editingSections.length > 0) {
      Alert.alert(
        'Finish Editing',
        'Please finish editing all sections before proceeding to approval.',
        [{ text: 'OK' }]
      );
      return;
    }

    navigation.navigate('Approval', { encounterId: soapNote.encounterId });
  }, [soapNote, navigation]);

  // Check if there are unsaved changes
  const hasUnsavedChanges = useCallback(() => {
    if (!soapNote) return false;
    return soapNote.sections.some(s => s.content !== s.originalContent);
  }, [soapNote]);

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#3B82F6" />
        <Text style={styles.loadingText}>Loading encounter...</Text>
      </View>
    );
  }

  if (!soapNote) {
    return (
      <View style={styles.errorContainer}>
        <Text style={styles.errorText}>Failed to load encounter</Text>
        <TouchableOpacity style={styles.retryButton} onPress={loadSOAPNote}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <TouchableOpacity
            onPress={() => {
              if (hasUnsavedChanges()) {
                Alert.alert(
                  'Unsaved Changes',
                  'You have unsaved changes. Save before leaving?',
                  [
                    { text: 'Discard', style: 'destructive', onPress: () => navigation.goBack() },
                    { text: 'Save', onPress: async () => { await saveDraft(); navigation.goBack(); } },
                    { text: 'Cancel', style: 'cancel' },
                  ]
                );
              } else {
                navigation.goBack();
              }
            }}
          >
            <Text style={styles.backButton}>← Back</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle}>Review SOAP Note</Text>
          <Text style={styles.headerSubtitle}>{soapNote.patientName}</Text>
        </View>
        <View style={styles.headerRight}>
          {isSaving ? (
            <ActivityIndicator size="small" color="#3B82F6" />
          ) : (
            <TouchableOpacity onPress={saveDraft}>
              <Text style={styles.saveButton}>Save</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Status Bar */}
      <View style={styles.statusBar}>
        <View style={styles.statusItem}>
          <Text style={styles.statusLabel}>Status</Text>
          <View style={[styles.statusBadge, styles[`status_${soapNote.status}`]]}>
            <Text style={styles.statusBadgeText}>
              {soapNote.status.charAt(0).toUpperCase() + soapNote.status.slice(1)}
            </Text>
          </View>
        </View>
        <View style={styles.statusItem}>
          <Text style={styles.statusLabel}>Last Modified</Text>
          <Text style={styles.statusValue}>
            {new Date(soapNote.lastModified).toLocaleTimeString()}
          </Text>
        </View>
        {hasUnsavedChanges() && (
          <View style={styles.unsavedIndicator}>
            <Text style={styles.unsavedText}>● Unsaved changes</Text>
          </View>
        )}
      </View>

      {/* SOAP Sections */}
      <ScrollView
        ref={scrollViewRef}
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {soapNote.sections.map(section => (
          <View key={section.key} style={styles.sectionContainer}>
            <SectionHeader
              title={section.title}
              confidence={section.confidence}
              isEditing={section.isEditing}
              onEditToggle={() => toggleSectionEditing(section.key)}
              hasChanges={section.content !== section.originalContent}
            />
            {section.isEditing ? (
              <SectionEditor
                section={section}
                onContentChange={(content) => updateSectionContent(section.key, content)}
                onRevert={() => revertSection(section.key)}
              />
            ) : (
              <View style={styles.sectionContent}>
                <Text style={styles.sectionText}>{section.content}</Text>
                {section.content !== section.originalContent && (
                  <DiffViewer original={section.originalContent} current={section.content} />
                )}
              </View>
            )}
          </View>
        ))}
      </ScrollView>

      {/* Footer Actions */}
      <View style={styles.footer}>
        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => navigation.goBack()}
        >
          <Text style={styles.secondaryButtonText}>Back to List</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={proceedToApproval}
        >
          <Text style={styles.primaryButtonText}>Proceed to Approval →</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
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
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  headerLeft: {
    width: 60,
  },
  backButton: {
    fontSize: 16,
    color: '#3B82F6',
  },
  headerCenter: {
    flex: 1,
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1F2937',
  },
  headerSubtitle: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
  headerRight: {
    width: 60,
    alignItems: 'flex-end',
  },
  saveButton: {
    fontSize: 16,
    color: '#3B82F6',
    fontWeight: '600',
  },
  statusBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  statusItem: {
    marginRight: 24,
  },
  statusLabel: {
    fontSize: 12,
    color: '#9CA3AF',
    marginBottom: 2,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  status_draft: {
    backgroundColor: '#FEF3C7',
  },
  status_reviewed: {
    backgroundColor: '#DBEAFE',
  },
  status_approved: {
    backgroundColor: '#D1FAE5',
  },
  statusBadgeText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#1F2937',
  },
  statusValue: {
    fontSize: 14,
    color: '#1F2937',
  },
  unsavedIndicator: {
    marginLeft: 'auto',
  },
  unsavedText: {
    fontSize: 12,
    color: '#F59E0B',
    fontWeight: '600',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
  },
  sectionContainer: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    marginBottom: 16,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#F9FAFB',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  sectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1F2937',
  },
  changedBadge: {
    marginLeft: 8,
    paddingHorizontal: 6,
    paddingVertical: 2,
    backgroundColor: '#FEF3C7',
    borderRadius: 4,
  },
  changedBadgeText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#92400E',
  },
  sectionActions: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  confidenceContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 12,
  },
  confidenceDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 4,
  },
  confidenceText: {
    fontSize: 12,
    color: '#6B7280',
  },
  editButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#3B82F6',
  },
  editButtonActive: {
    backgroundColor: '#3B82F6',
  },
  editButtonText: {
    fontSize: 14,
    color: '#3B82F6',
    fontWeight: '500',
  },
  editButtonTextActive: {
    color: '#FFFFFF',
  },
  sectionContent: {
    padding: 16,
  },
  sectionText: {
    fontSize: 15,
    color: '#374151',
    lineHeight: 22,
  },
  editorContainer: {
    padding: 16,
  },
  editorInput: {
    fontSize: 15,
    color: '#374151',
    lineHeight: 22,
    padding: 12,
    backgroundColor: '#F9FAFB',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    minHeight: 120,
    textAlignVertical: 'top',
  },
  editorActions: {
    marginTop: 12,
  },
  revertButton: {
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: '#FEE2E2',
    borderRadius: 6,
  },
  revertButtonText: {
    fontSize: 12,
    color: '#DC2626',
    fontWeight: '500',
  },
  diffContainer: {
    marginTop: 12,
    padding: 12,
    backgroundColor: '#FEF3C7',
    borderRadius: 8,
  },
  diffLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#92400E',
    marginBottom: 4,
  },
  diffOriginal: {
    fontSize: 13,
    color: '#92400E',
    fontStyle: 'italic',
  },
  suggestionsContainer: {
    marginTop: 12,
    padding: 12,
    backgroundColor: '#EEF2FF',
    borderRadius: 8,
  },
  suggestionsLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#4338CA',
    marginBottom: 8,
  },
  suggestionItem: {
    paddingVertical: 6,
  },
  suggestionText: {
    fontSize: 13,
    color: '#4338CA',
  },
  footer: {
    flexDirection: 'row',
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  secondaryButton: {
    flex: 1,
    paddingVertical: 14,
    marginRight: 8,
    backgroundColor: '#F3F4F6',
    borderRadius: 8,
    alignItems: 'center',
  },
  secondaryButtonText: {
    fontSize: 16,
    color: '#6B7280',
    fontWeight: '600',
  },
  primaryButton: {
    flex: 2,
    paddingVertical: 14,
    marginLeft: 8,
    backgroundColor: '#3B82F6',
    borderRadius: 8,
    alignItems: 'center',
  },
  primaryButtonText: {
    fontSize: 16,
    color: '#FFFFFF',
    fontWeight: '600',
  },
});

export default ReviewScreen;
