/**
 * useMedicalTranscription – React hook for medical-grade voice transcription.
 *
 * Uses the Web Speech API (SpeechRecognition) for real-time speech-to-text,
 * MediaRecorder for raw audio capture, and Web Audio API for quality metering.
 *
 * Designed for HIPAA-compliant clinical encounters.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  RecordingStatus,
  TranscriptSegment,
  TranscriptionError,
  SpeakerLabel,
} from '../types/transcription';
import {
  assessQuality,
  getSpeechRecognition,
  isSpeechRecognitionSupported,
  getPreferredMimeType,
  formatDuration,
  type QualityMetrics,
} from '../utils/audioProcessing';
import { MEDICAL_TERMS_SET } from '../utils/medicalDictionary';

/* ─── Default config ─── */
const DEFAULT_MAX_DURATION = 30 * 60 * 1000; // 30 minutes
const QUALITY_POLL_MS = 500;
const SEGMENT_COUNTER_START = 1;

/* ─── Hook ─── */

export interface UseMedicalTranscriptionOptions {
  maxDuration?: number;              // ms
  language?: string;                 // BCP-47, e.g. 'en-US'
  continuous?: boolean;
  interimResults?: boolean;
}

export interface UseMedicalTranscriptionReturn {
  /* state */
  status: RecordingStatus;
  transcript: string;
  interimText: string;
  segments: TranscriptSegment[];
  duration: number;                  // seconds elapsed
  formattedDuration: string;
  quality: QualityMetrics | null;
  audioBlob: Blob | null;
  error: TranscriptionError | null;
  /* actions */
  startRecording: () => Promise<void>;
  pauseRecording: () => void;
  resumeRecording: () => void;
  stopRecording: () => void;
  resetRecording: () => void;
  setSpeaker: (speaker: SpeakerLabel) => void;
  /* waveform */
  waveformData: number[];
}

export function useMedicalTranscription(
  opts: UseMedicalTranscriptionOptions = {}
): UseMedicalTranscriptionReturn {
  const {
    maxDuration = DEFAULT_MAX_DURATION,
    language = 'en-US',
    continuous = true,
    interimResults = true,
  } = opts;

  /* ── State ── */
  const [status, setStatus] = useState<RecordingStatus>('idle');
  const [transcript, setTranscript] = useState('');
  const [interimText, setInterimText] = useState('');
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [duration, setDuration] = useState(0);
  const [quality, setQuality] = useState<QualityMetrics | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [error, setError] = useState<TranscriptionError | null>(null);
  const [currentSpeaker, setCurrentSpeaker] = useState<SpeakerLabel>('doctor');
  const [waveformData, setWaveformData] = useState<number[]>([]);

  /* ── Refs ── */
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);
  const durationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const qualityIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const segmentCounterRef = useRef(SEGMENT_COUNTER_START);
  const animFrameRef = useRef<number>(0);
  const accumulatedTranscriptRef = useRef('');

  /* ── Helpers ── */

  const makeSegment = useCallback(
    (text: string, confidence: number, isFinal: boolean): TranscriptSegment => {
      const now = (Date.now() - startTimeRef.current) / 1000;
      const words = text.trim().split(/\s+/);
      const containsMedical = words.some(w =>
        MEDICAL_TERMS_SET.has(w.toLowerCase().replace(/[^a-z0-9-]/g, ''))
      );
      return {
        id: `seg-${segmentCounterRef.current++}`,
        text: text.trim(),
        startTime: Math.max(0, now - text.length * 0.06),
        endTime: now,
        confidence,
        speaker: currentSpeaker,
        isFinal,
        isMedicalTerm: containsMedical,
        alternatives: [],
        words: words.map(w => ({
          word: w,
          startTime: 0,
          endTime: 0,
          confidence,
          isMedical: MEDICAL_TERMS_SET.has(w.toLowerCase().replace(/[^a-z0-9-]/g, '')),
        })),
      };
    },
    [currentSpeaker]
  );

  /* ── Waveform animation loop ── */
  const animateWaveform = useCallback(() => {
    if (!analyserRef.current) return;
    const bufLen = analyserRef.current.fftSize;
    const data = new Uint8Array(bufLen);
    analyserRef.current.getByteTimeDomainData(data);

    const bars = 48;
    const step = Math.floor(bufLen / bars);
    const wave: number[] = [];
    for (let i = 0; i < bars; i++) {
      let max = 0;
      for (let j = 0; j < step; j++) {
        const v = Math.abs((data[i * step + j] - 128) / 128);
        if (v > max) max = v;
      }
      wave.push(max);
    }
    setWaveformData(wave);
    animFrameRef.current = requestAnimationFrame(animateWaveform);
  }, []);

  /* ── Quality polling ── */
  const startQualityPolling = useCallback(() => {
    qualityIntervalRef.current = setInterval(() => {
      if (!analyserRef.current) return;
      const bufLen = analyserRef.current.fftSize;
      const timeDomain = new Uint8Array(bufLen);
      const frequency = new Uint8Array(analyserRef.current.frequencyBinCount);
      analyserRef.current.getByteTimeDomainData(timeDomain);
      analyserRef.current.getByteFrequencyData(frequency);
      setQuality(assessQuality(timeDomain, frequency));
    }, QUALITY_POLL_MS);
  }, []);

  /* ── Cleanup helper ── */
  const cleanup = useCallback(() => {
    // Stop speech recognition
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch { /* noop */ }
      recognitionRef.current = null;
    }
    // Stop MediaRecorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try { mediaRecorderRef.current.stop(); } catch { /* noop */ }
    }
    mediaRecorderRef.current = null;
    // Stop media stream tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    // Close AudioContext
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    // Clear intervals
    if (durationIntervalRef.current) clearInterval(durationIntervalRef.current);
    if (qualityIntervalRef.current) clearInterval(qualityIntervalRef.current);
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
  }, []);

  /* ────────────────────────────────────────────────── */
  /*  START                                             */
  /* ────────────────────────────────────────────────── */
  const startRecording = useCallback(async () => {
    setError(null);
    setStatus('requesting_permission');

    /* Browser support check */
    if (!isSpeechRecognitionSupported()) {
      setError({
        code: 'BROWSER_NOT_SUPPORTED',
        message: 'Speech recognition is not supported in this browser. Please use Chrome or Edge.',
        recoverable: false,
      });
      setStatus('error');
      return;
    }

    /* Request microphone */
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 48000,
          channelCount: 1,
        },
      });
    } catch (err: any) {
      const isDenied = err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError';
      setError({
        code: isDenied ? 'MICROPHONE_DENIED' : 'MICROPHONE_NOT_FOUND',
        message: isDenied
          ? 'Microphone access was denied. Please allow microphone access in your browser settings and try again.'
          : 'No microphone found. Please connect a microphone and try again.',
        details: err.message,
        recoverable: true,
      });
      setStatus('error');
      return;
    }

    streamRef.current = stream;

    /* ── Audio Context + Analyser ── */
    const audioCtx = new AudioContext({ sampleRate: 48000 });
    audioContextRef.current = audioCtx;
    const source = audioCtx.createMediaStreamSource(stream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);
    analyserRef.current = analyser;

    /* ── MediaRecorder (raw audio backup) ── */
    const mimeType = getPreferredMimeType();
    if (mimeType) {
      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        setAudioBlob(blob);
      };
      recorder.start(1000); // collect chunks every second
      mediaRecorderRef.current = recorder;
    }

    /* ── SpeechRecognition ── */
    const SpeechRecognition = getSpeechRecognition()!;
    const recognition = new SpeechRecognition();
    recognition.continuous = continuous;
    recognition.interimResults = interimResults;
    recognition.lang = language;
    recognition.maxAlternatives = 3;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = '';
      let finalText = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const text = result[0].transcript;
        const confidence = result[0].confidence || 0.85;

        if (result.isFinal) {
          finalText += text;
          const segment = makeSegment(text, confidence, true);
          setSegments(prev => [...prev, segment]);
        } else {
          interim += text;
        }
      }

      if (finalText) {
        accumulatedTranscriptRef.current += finalText;
        setTranscript(accumulatedTranscriptRef.current);
      }
      setInterimText(interim);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      // 'no-speech' and 'aborted' are non-fatal
      if (event.error === 'no-speech' || event.error === 'aborted') return;

      console.error('SpeechRecognition error:', event.error);

      if (event.error === 'network') {
        setError({
          code: 'NETWORK_ERROR',
          message: 'Network error during transcription. Your audio is still being recorded.',
          recoverable: true,
        });
      }
    };

    recognition.onend = () => {
      // Auto-restart if still recording (Chrome stops after ~60 s of silence)
      if (
        status === 'recording' &&
        recognitionRef.current
      ) {
        try {
          recognitionRef.current.start();
        } catch {
          /* already started */
        }
      }
    };

    recognitionRef.current = recognition;

    /* ── Kick off ── */
    try {
      recognition.start();
    } catch (e) {
      console.warn('Recognition start failed, retrying…', e);
      setTimeout(() => {
        try { recognition.start(); } catch { /* give up silently */ }
      }, 200);
    }

    startTimeRef.current = Date.now();
    setDuration(0);
    setTranscript('');
    setInterimText('');
    setSegments([]);
    setAudioBlob(null);
    accumulatedTranscriptRef.current = '';
    segmentCounterRef.current = SEGMENT_COUNTER_START;

    /* Duration timer */
    durationIntervalRef.current = setInterval(() => {
      const elapsed = (Date.now() - startTimeRef.current) / 1000;
      setDuration(elapsed);
      if (elapsed * 1000 >= maxDuration) {
        stopRecording();
      }
    }, 1000);

    /* Quality polling + waveform anim */
    startQualityPolling();
    animateWaveform();

    setStatus('recording');
  }, [
    language,
    continuous,
    interimResults,
    maxDuration,
    makeSegment,
    startQualityPolling,
    animateWaveform,
    cleanup,
    status,
  ]);

  /* ── PAUSE ── */
  const pauseRecording = useCallback(() => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch { /* noop */ }
    }
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.pause();
    }
    if (durationIntervalRef.current) clearInterval(durationIntervalRef.current);
    if (qualityIntervalRef.current) clearInterval(qualityIntervalRef.current);
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    setStatus('paused');
  }, []);

  /* ── RESUME ── */
  const resumeRecording = useCallback(() => {
    if (recognitionRef.current) {
      try { recognitionRef.current.start(); } catch { /* noop */ }
    }
    if (mediaRecorderRef.current?.state === 'paused') {
      mediaRecorderRef.current.resume();
    }
    durationIntervalRef.current = setInterval(() => {
      const elapsed = (Date.now() - startTimeRef.current) / 1000;
      setDuration(elapsed);
    }, 1000);
    startQualityPolling();
    animateWaveform();
    setStatus('recording');
  }, [startQualityPolling, animateWaveform]);

  /* ── STOP ── */
  const stopRecording = useCallback(() => {
    setStatus('processing');
    setInterimText('');

    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch { /* noop */ }
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (durationIntervalRef.current) clearInterval(durationIntervalRef.current);
    if (qualityIntervalRef.current) clearInterval(qualityIntervalRef.current);
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

    // Keep stream alive briefly so MediaRecorder fires onstop
    setTimeout(() => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
        audioContextRef.current = null;
      }
      setStatus('completed');
    }, 500);
  }, []);

  /* ── RESET ── */
  const resetRecording = useCallback(() => {
    cleanup();
    setStatus('idle');
    setTranscript('');
    setInterimText('');
    setSegments([]);
    setDuration(0);
    setQuality(null);
    setAudioBlob(null);
    setError(null);
    setWaveformData([]);
    accumulatedTranscriptRef.current = '';
    chunksRef.current = [];
    segmentCounterRef.current = SEGMENT_COUNTER_START;
  }, [cleanup]);

  /* ── Speaker setter ── */
  const setSpeaker = useCallback((s: SpeakerLabel) => setCurrentSpeaker(s), []);

  /* ── Cleanup on unmount ── */
  useEffect(() => {
    return () => cleanup();
  }, [cleanup]);

  return {
    status,
    transcript,
    interimText,
    segments,
    duration,
    formattedDuration: formatDuration(duration),
    quality,
    audioBlob,
    error,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
    resetRecording,
    setSpeaker,
    waveformData,
  };
}
