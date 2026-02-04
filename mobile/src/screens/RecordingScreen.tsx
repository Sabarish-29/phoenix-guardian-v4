/**
 * Recording screen for bedside encounter capture.
 * 
 * Features:
 * - One-tap start/stop recording
 * - Real-time transcript display
 * - Real-time SOAP note streaming
 * - Visual audio level indicator
 * - Offline mode support (records locally, syncs later)
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert,
  Animated,
  SafeAreaView,
  StatusBar,
} from 'react-native';
import { Audio } from 'expo-av';
import { useDispatch, useSelector } from 'react-redux';
import WebSocketService from '../services/WebSocketService';
import OfflineService from '../services/OfflineService';
import NetworkDetector from '../utils/networkDetector';
import {
  startRecording as startRecordingAction,
  stopRecording as stopRecordingAction,
  updateSOAPSection,
  setRecordingPaused,
} from '../store/encounterSlice';
import { selectIsOnline } from '../store/offlineSlice';

// =============================================================================
// TYPES
// =============================================================================

interface RecordingScreenProps {
  navigation: any;
  route: {
    params: {
      patientId: string;
      encounterId: string;
      patientName?: string;
    };
  };
}

type RecordingState = 'idle' | 'recording' | 'paused' | 'processing' | 'complete';

interface SOAPNote {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
}

interface WebSocketEvent {
  type: string;
  text?: string;
  section?: keyof SOAPNote;
  message?: string;
  encounter_id?: string;
  soap_note?: SOAPNote;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const AUDIO_CHUNK_INTERVAL = 1000; // 1 second
const AUDIO_LEVEL_BARS = 16;
const MAX_RECORDING_DURATION = 60 * 60 * 1000; // 1 hour max

// =============================================================================
// COMPONENT
// =============================================================================

const RecordingScreen: React.FC<RecordingScreenProps> = ({ navigation, route }) => {
  const { patientId, encounterId, patientName } = route.params;
  const dispatch = useDispatch();
  
  // =============================================================================
  // STATE
  // =============================================================================
  
  const [recordingState, setRecordingState] = useState<RecordingState>('idle');
  const [transcript, setTranscript] = useState<string>('');
  const [soapNote, setSoapNote] = useState<SOAPNote>({
    subjective: '',
    objective: '',
    assessment: '',
    plan: '',
  });
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [recordingDuration, setRecordingDuration] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  
  // Animation values
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const levelAnims = useRef(
    Array.from({ length: AUDIO_LEVEL_BARS }, () => new Animated.Value(0))
  ).current;
  
  // =============================================================================
  // REFS
  // =============================================================================
  
  const audioRecording = useRef<Audio.Recording | null>(null);
  const wsService = useRef(WebSocketService.getInstance());
  const recordingInterval = useRef<NodeJS.Timer | null>(null);
  const durationInterval = useRef<NodeJS.Timer | null>(null);
  const transcriptScrollRef = useRef<ScrollView>(null);
  const soapScrollRef = useRef<ScrollView>(null);
  
  // =============================================================================
  // EFFECTS
  // =============================================================================
  
  // Network detection
  useEffect(() => {
    const checkNetwork = async () => {
      const online = await NetworkDetector.isOnline();
      setIsOnline(online);
    };
    
    checkNetwork();
    
    const unsubscribe = NetworkDetector.onChange((online) => {
      setIsOnline(online);
      if (!online && recordingState === 'recording') {
        // Show offline notification but keep recording
        Alert.alert(
          'Offline Mode',
          'Recording will continue. Your encounter will sync when you\'re back online.'
        );
      }
    });
    
    return unsubscribe;
  }, [recordingState]);
  
  // WebSocket event listeners
  useEffect(() => {
    if (!isOnline) return;
    
    const unsubscribe = wsService.current.on((event: WebSocketEvent) => {
      switch (event.type) {
        case 'transcript_update':
          if (event.text) {
            setTranscript(prev => {
              const newTranscript = prev ? `${prev} ${event.text}` : event.text!;
              // Auto-scroll to bottom
              setTimeout(() => {
                transcriptScrollRef.current?.scrollToEnd({ animated: true });
              }, 100);
              return newTranscript;
            });
          }
          break;
          
        case 'soap_section_ready':
          if (event.section && event.text) {
            setSoapNote(prev => ({
              ...prev,
              [event.section!]: event.text,
            }));
            dispatch(updateSOAPSection({
              section: event.section,
              content: event.text,
            }));
            // Auto-scroll SOAP view
            setTimeout(() => {
              soapScrollRef.current?.scrollToEnd({ animated: true });
            }, 100);
          }
          break;
          
        case 'soap_complete':
          setRecordingState('complete');
          if (event.soap_note) {
            setSoapNote(event.soap_note);
          }
          // Navigate to review screen
          navigation.navigate('Review', {
            encounterId,
            soapNote: event.soap_note || soapNote,
            transcript,
          });
          break;
          
        case 'error':
          setError(event.message || 'An error occurred');
          Alert.alert('Error', event.message || 'An error occurred');
          setRecordingState('idle');
          break;
      }
    });
    
    return unsubscribe;
  }, [isOnline, encounterId, soapNote, transcript, navigation, dispatch]);
  
  // Pulse animation for recording indicator
  useEffect(() => {
    if (recordingState === 'recording') {
      const pulse = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.2,
            duration: 500,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 500,
            useNativeDriver: true,
          }),
        ])
      );
      pulse.start();
      
      return () => pulse.stop();
    }
  }, [recordingState, pulseAnim]);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recordingInterval.current) {
        clearInterval(recordingInterval.current);
      }
      if (durationInterval.current) {
        clearInterval(durationInterval.current);
      }
      if (audioRecording.current) {
        audioRecording.current.stopAndUnloadAsync();
      }
    };
  }, []);
  
  // =============================================================================
  // HANDLERS
  // =============================================================================
  
  /**
   * Start recording audio.
   */
  const startRecording = useCallback(async () => {
    try {
      setError(null);
      
      // Request microphone permission
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) {
        Alert.alert(
          'Permission Required',
          'Microphone access is required for recording. Please enable it in Settings.',
          [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Settings', onPress: () => {/* Open settings */} },
          ]
        );
        return;
      }
      
      // Configure audio mode for recording
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
        staysActiveInBackground: true,
        shouldDuckAndroid: true,
        playThroughEarpieceAndroid: false,
      });
      
      // Create and start recording
      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync({
        ...Audio.RecordingOptionsPresets.HIGH_QUALITY,
        android: {
          extension: '.m4a',
          outputFormat: Audio.AndroidOutputFormat.MPEG_4,
          audioEncoder: Audio.AndroidAudioEncoder.AAC,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 64000,
        },
        ios: {
          extension: '.m4a',
          audioQuality: Audio.IOSAudioQuality.HIGH,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 64000,
          linearPCMBitDepth: 16,
          linearPCMIsBigEndian: false,
          linearPCMIsFloat: false,
        },
      });
      
      await recording.startAsync();
      audioRecording.current = recording;
      setRecordingState('recording');
      setRecordingDuration(0);
      
      // Start duration timer
      durationInterval.current = setInterval(() => {
        setRecordingDuration(prev => {
          if (prev >= MAX_RECORDING_DURATION) {
            stopRecording();
            return prev;
          }
          return prev + 1000;
        });
      }, 1000);
      
      // Dispatch Redux action
      dispatch(startRecordingAction({ encounterId, patientId }));
      
      // If online, connect WebSocket and start encounter
      if (isOnline) {
        await wsService.current.connect();
        wsService.current.startEncounter(patientId, encounterId);
        
        // Start streaming audio chunks
        startAudioStreaming(recording);
      } else {
        console.log('Recording offline - will sync later');
      }
      
    } catch (error) {
      console.error('Failed to start recording:', error);
      setError('Failed to start recording');
      Alert.alert('Error', 'Failed to start recording. Please try again.');
    }
  }, [isOnline, encounterId, patientId, dispatch]);
  
  /**
   * Stream audio chunks to server via WebSocket.
   */
  const startAudioStreaming = useCallback((recording: Audio.Recording) => {
    recordingInterval.current = setInterval(async () => {
      if (recordingState !== 'recording' || !audioRecording.current) {
        if (recordingInterval.current) {
          clearInterval(recordingInterval.current);
        }
        return;
      }
      
      try {
        const status = await recording.getStatusAsync();
        if (status.isRecording) {
          // Get audio level for visual indicator (normalized from dB)
          const metering = status.metering ?? -160;
          const normalizedLevel = Math.max(0, (metering + 160) / 160);
          setAudioLevel(normalizedLevel);
          
          // Animate level bars
          animateAudioLevels(normalizedLevel);
          
          // In production, extract and stream audio chunk here
          // const audioChunk = await extractAudioChunk(recording);
          // wsService.current.sendAudioChunk(audioChunk);
        }
      } catch (error) {
        console.error('Audio streaming error:', error);
      }
    }, AUDIO_CHUNK_INTERVAL);
  }, [recordingState]);
  
  /**
   * Animate audio level bars.
   */
  const animateAudioLevels = useCallback((level: number) => {
    const activeBars = Math.floor(level * AUDIO_LEVEL_BARS);
    
    levelAnims.forEach((anim, index) => {
      Animated.timing(anim, {
        toValue: index < activeBars ? 1 : 0,
        duration: 100,
        useNativeDriver: false,
      }).start();
    });
  }, [levelAnims]);
  
  /**
   * Pause recording.
   */
  const pauseRecording = useCallback(async () => {
    try {
      if (!audioRecording.current) return;
      
      await audioRecording.current.pauseAsync();
      setRecordingState('paused');
      dispatch(setRecordingPaused(true));
      
      if (durationInterval.current) {
        clearInterval(durationInterval.current);
      }
    } catch (error) {
      console.error('Failed to pause recording:', error);
    }
  }, [dispatch]);
  
  /**
   * Resume recording.
   */
  const resumeRecording = useCallback(async () => {
    try {
      if (!audioRecording.current) return;
      
      await audioRecording.current.startAsync();
      setRecordingState('recording');
      dispatch(setRecordingPaused(false));
      
      // Resume duration timer
      durationInterval.current = setInterval(() => {
        setRecordingDuration(prev => prev + 1000);
      }, 1000);
    } catch (error) {
      console.error('Failed to resume recording:', error);
    }
  }, [dispatch]);
  
  /**
   * Stop recording audio.
   */
  const stopRecording = useCallback(async () => {
    try {
      if (!audioRecording.current) return;
      
      // Clear intervals
      if (recordingInterval.current) {
        clearInterval(recordingInterval.current);
      }
      if (durationInterval.current) {
        clearInterval(durationInterval.current);
      }
      
      setRecordingState('processing');
      
      // Stop and unload recording
      await audioRecording.current.stopAndUnloadAsync();
      const uri = audioRecording.current.getURI();
      
      // Dispatch Redux action
      dispatch(stopRecordingAction({ encounterId }));
      
      if (isOnline && uri) {
        // Online: signal end of encounter to WebSocket
        wsService.current.stopEncounter();
        // Server will process and generate SOAP note
        
      } else if (uri) {
        // Offline: save to local queue
        await OfflineService.saveEncounter({
          encounterId,
          patientId,
          audioUri: uri,
          timestamp: new Date().toISOString(),
        });
        
        Alert.alert(
          'Saved Offline',
          'Encounter saved locally. Will sync automatically when you\'re back online.',
          [
            {
              text: 'OK',
              onPress: () => navigation.goBack(),
            },
          ]
        );
        setRecordingState('idle');
      }
      
      audioRecording.current = null;
      
    } catch (error) {
      console.error('Failed to stop recording:', error);
      setError('Failed to stop recording');
      Alert.alert('Error', 'Failed to stop recording. Please try again.');
      setRecordingState('idle');
    }
  }, [isOnline, encounterId, patientId, navigation, dispatch]);
  
  /**
   * Cancel recording.
   */
  const cancelRecording = useCallback(() => {
    Alert.alert(
      'Cancel Recording',
      'Are you sure you want to cancel this recording? All data will be lost.',
      [
        { text: 'No', style: 'cancel' },
        {
          text: 'Yes, Cancel',
          style: 'destructive',
          onPress: async () => {
            if (recordingInterval.current) {
              clearInterval(recordingInterval.current);
            }
            if (durationInterval.current) {
              clearInterval(durationInterval.current);
            }
            
            if (audioRecording.current) {
              await audioRecording.current.stopAndUnloadAsync();
              audioRecording.current = null;
            }
            
            wsService.current.disconnect();
            navigation.goBack();
          },
        },
      ]
    );
  }, [navigation]);
  
  /**
   * Format duration as MM:SS.
   */
  const formatDuration = useCallback((ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }, []);
  
  // =============================================================================
  // RENDER HELPERS
  // =============================================================================
  
  /**
   * Render audio level indicator.
   */
  const renderAudioLevel = () => (
    <View style={styles.audioLevelContainer}>
      {levelAnims.map((anim, i) => (
        <Animated.View
          key={i}
          style={[
            styles.audioLevelBar,
            {
              backgroundColor: anim.interpolate({
                inputRange: [0, 1],
                outputRange: ['#E2E8F0', i < 10 ? '#48BB78' : i < 14 ? '#ECC94B' : '#E53E3E'],
              }),
              height: anim.interpolate({
                inputRange: [0, 1],
                outputRange: [10, 20 + i * 2],
              }),
            },
          ]}
        />
      ))}
    </View>
  );
  
  /**
   * Render recording controls based on state.
   */
  const renderRecordingControls = () => {
    switch (recordingState) {
      case 'idle':
        return (
          <TouchableOpacity
            style={styles.recordButton}
            onPress={startRecording}
            accessibilityLabel="Start Recording"
            accessibilityRole="button"
          >
            <View style={styles.recordButtonInner}>
              <Text style={styles.recordButtonIcon}>🎤</Text>
              <Text style={styles.recordButtonText}>Start Recording</Text>
            </View>
          </TouchableOpacity>
        );
        
      case 'recording':
        return (
          <>
            {renderAudioLevel()}
            
            <Animated.View style={{ transform: [{ scale: pulseAnim }] }}>
              <View style={styles.recordingIndicator}>
                <View style={styles.recordingDot} />
                <Text style={styles.recordingTimer}>{formatDuration(recordingDuration)}</Text>
              </View>
            </Animated.View>
            
            <View style={styles.recordingButtonsRow}>
              <TouchableOpacity
                style={[styles.controlButton, styles.pauseButton]}
                onPress={pauseRecording}
                accessibilityLabel="Pause Recording"
              >
                <Text style={styles.controlButtonText}>⏸ Pause</Text>
              </TouchableOpacity>
              
              <TouchableOpacity
                style={[styles.controlButton, styles.stopButton]}
                onPress={stopRecording}
                accessibilityLabel="Stop Recording"
              >
                <Text style={styles.controlButtonText}>⏹ Stop</Text>
              </TouchableOpacity>
            </View>
            
            <TouchableOpacity
              style={styles.cancelLink}
              onPress={cancelRecording}
            >
              <Text style={styles.cancelLinkText}>Cancel Recording</Text>
            </TouchableOpacity>
          </>
        );
        
      case 'paused':
        return (
          <>
            <View style={styles.pausedIndicator}>
              <Text style={styles.pausedText}>⏸ PAUSED</Text>
              <Text style={styles.recordingTimer}>{formatDuration(recordingDuration)}</Text>
            </View>
            
            <View style={styles.recordingButtonsRow}>
              <TouchableOpacity
                style={[styles.controlButton, styles.resumeButton]}
                onPress={resumeRecording}
                accessibilityLabel="Resume Recording"
              >
                <Text style={styles.controlButtonText}>▶ Resume</Text>
              </TouchableOpacity>
              
              <TouchableOpacity
                style={[styles.controlButton, styles.stopButton]}
                onPress={stopRecording}
                accessibilityLabel="Stop Recording"
              >
                <Text style={styles.controlButtonText}>⏹ Stop</Text>
              </TouchableOpacity>
            </View>
          </>
        );
        
      case 'processing':
        return (
          <View style={styles.processingContainer}>
            <ActivityIndicator size="large" color="#3182CE" />
            <Text style={styles.processingText}>Generating SOAP note...</Text>
            <Text style={styles.processingSubtext}>This may take a moment</Text>
          </View>
        );
        
      default:
        return null;
    }
  };
  
  /**
   * Render SOAP section.
   */
  const renderSOAPSection = (label: string, content: string, isStreaming: boolean) => {
    if (!content) return null;
    
    return (
      <View style={styles.soapSection}>
        <View style={styles.soapSectionHeader}>
          <Text style={styles.soapSectionLabel}>{label}</Text>
          {isStreaming && (
            <ActivityIndicator size="small" color="#3182CE" style={styles.streamingIndicator} />
          )}
        </View>
        <Text style={styles.soapSectionText}>{content}</Text>
      </View>
    );
  };
  
  // =============================================================================
  // RENDER
  // =============================================================================
  
  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" backgroundColor="#F7FAFC" />
      
      <View style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <TouchableOpacity
              onPress={() => {
                if (recordingState === 'recording' || recordingState === 'paused') {
                  cancelRecording();
                } else {
                  navigation.goBack();
                }
              }}
              style={styles.backButton}
            >
              <Text style={styles.backButtonText}>← Back</Text>
            </TouchableOpacity>
            <Text style={styles.title}>Recording Encounter</Text>
            {patientName && (
              <Text style={styles.patientName}>{patientName}</Text>
            )}
          </View>
          
          {!isOnline && (
            <View style={styles.offlineBadge}>
              <Text style={styles.offlineBadgeText}>📡 Offline</Text>
            </View>
          )}
        </View>
        
        {/* Error Banner */}
        {error && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorBannerText}>⚠️ {error}</Text>
          </View>
        )}
        
        {/* Recording Controls */}
        <View style={styles.recordingControls}>
          {renderRecordingControls()}
        </View>
        
        {/* Real-time Transcript */}
        {transcript && (
          <View style={styles.transcriptContainer}>
            <Text style={styles.sectionLabel}>📝 LIVE TRANSCRIPT</Text>
            <ScrollView
              ref={transcriptScrollRef}
              style={styles.transcriptScroll}
              showsVerticalScrollIndicator={true}
            >
              <Text style={styles.transcriptText}>{transcript}</Text>
            </ScrollView>
          </View>
        )}
        
        {/* Real-time SOAP Note Streaming */}
        {Object.values(soapNote).some(section => section) && (
          <View style={styles.soapContainer}>
            <Text style={styles.sectionLabel}>
              📋 SOAP NOTE {recordingState === 'processing' ? '(Generating...)' : ''}
            </Text>
            <ScrollView
              ref={soapScrollRef}
              style={styles.soapScroll}
              showsVerticalScrollIndicator={true}
            >
              {renderSOAPSection('SUBJECTIVE', soapNote.subjective, recordingState === 'processing')}
              {renderSOAPSection('OBJECTIVE', soapNote.objective, recordingState === 'processing')}
              {renderSOAPSection('ASSESSMENT', soapNote.assessment, recordingState === 'processing')}
              {renderSOAPSection('PLAN', soapNote.plan, recordingState === 'processing')}
            </ScrollView>
          </View>
        )}
        
        {/* Tips when idle */}
        {recordingState === 'idle' && !transcript && (
          <View style={styles.tipsContainer}>
            <Text style={styles.tipsTitle}>Recording Tips</Text>
            <Text style={styles.tipItem}>• Speak clearly and at a normal pace</Text>
            <Text style={styles.tipItem}>• Minimize background noise</Text>
            <Text style={styles.tipItem}>• Hold device 6-12 inches from speaker</Text>
            <Text style={styles.tipItem}>• Include patient history and symptoms</Text>
          </View>
        )}
      </View>
    </SafeAreaView>
  );
};

// =============================================================================
// STYLES
// =============================================================================

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#F7FAFC',
  },
  container: {
    flex: 1,
    padding: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 24,
  },
  headerLeft: {
    flex: 1,
  },
  backButton: {
    marginBottom: 8,
  },
  backButtonText: {
    color: '#3182CE',
    fontSize: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#2D3748',
  },
  patientName: {
    fontSize: 16,
    color: '#718096',
    marginTop: 4,
  },
  offlineBadge: {
    backgroundColor: '#FED7D7',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  offlineBadgeText: {
    color: '#C53030',
    fontSize: 12,
    fontWeight: '600',
  },
  errorBanner: {
    backgroundColor: '#FED7D7',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
  },
  errorBannerText: {
    color: '#C53030',
    fontSize: 14,
    textAlign: 'center',
  },
  recordingControls: {
    alignItems: 'center',
    marginBottom: 24,
    minHeight: 150,
    justifyContent: 'center',
  },
  recordButton: {
    backgroundColor: '#3182CE',
    paddingHorizontal: 40,
    paddingVertical: 20,
    borderRadius: 12,
    minWidth: 220,
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
  recordButtonInner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  recordButtonIcon: {
    fontSize: 24,
    marginRight: 8,
  },
  recordButtonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: '600',
  },
  audioLevelContainer: {
    flexDirection: 'row',
    height: 60,
    alignItems: 'center',
    marginBottom: 16,
  },
  audioLevelBar: {
    width: 8,
    marginHorizontal: 2,
    borderRadius: 4,
  },
  recordingIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  recordingDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#E53E3E',
    marginRight: 8,
  },
  recordingTimer: {
    fontSize: 24,
    fontWeight: '600',
    color: '#2D3748',
    fontVariant: ['tabular-nums'],
  },
  pausedIndicator: {
    alignItems: 'center',
    marginBottom: 16,
  },
  pausedText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#D69E2E',
    marginBottom: 8,
  },
  recordingButtonsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 16,
  },
  controlButton: {
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 8,
    minWidth: 120,
    alignItems: 'center',
  },
  pauseButton: {
    backgroundColor: '#D69E2E',
  },
  resumeButton: {
    backgroundColor: '#48BB78',
  },
  stopButton: {
    backgroundColor: '#E53E3E',
  },
  controlButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  cancelLink: {
    marginTop: 16,
    padding: 8,
  },
  cancelLinkText: {
    color: '#718096',
    fontSize: 14,
    textDecorationLine: 'underline',
  },
  processingContainer: {
    alignItems: 'center',
    padding: 20,
  },
  processingText: {
    marginTop: 16,
    fontSize: 18,
    fontWeight: '600',
    color: '#2D3748',
  },
  processingSubtext: {
    marginTop: 8,
    fontSize: 14,
    color: '#718096',
  },
  transcriptContainer: {
    flex: 1,
    marginBottom: 16,
    maxHeight: 150,
  },
  sectionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#718096',
    marginBottom: 8,
  },
  transcriptScroll: {
    backgroundColor: 'white',
    borderRadius: 8,
    padding: 16,
    flex: 1,
    elevation: 1,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  transcriptText: {
    fontSize: 14,
    lineHeight: 22,
    color: '#2D3748',
  },
  soapContainer: {
    flex: 2,
  },
  soapScroll: {
    backgroundColor: 'white',
    borderRadius: 8,
    padding: 16,
    flex: 1,
    elevation: 1,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  soapSection: {
    marginBottom: 16,
  },
  soapSectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  soapSectionLabel: {
    fontSize: 14,
    fontWeight: '700',
    color: '#2D3748',
  },
  streamingIndicator: {
    marginLeft: 8,
  },
  soapSectionText: {
    fontSize: 14,
    lineHeight: 22,
    color: '#4A5568',
  },
  tipsContainer: {
    backgroundColor: '#EBF8FF',
    borderRadius: 8,
    padding: 16,
    marginTop: 'auto',
  },
  tipsTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#2B6CB0',
    marginBottom: 12,
  },
  tipItem: {
    fontSize: 14,
    color: '#2C5282',
    marginBottom: 6,
    lineHeight: 20,
  },
});

export default RecordingScreen;
