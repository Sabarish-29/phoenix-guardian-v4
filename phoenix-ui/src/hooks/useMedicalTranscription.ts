/**
 * useMedicalTranscription – React hook for medical-grade voice transcription.
 *
 * Hybrid approach:
 *  1. Web Speech API for **live preview** during recording (best-effort, silent fail)
 *  2. Groq Whisper via backend for **accurate final transcription** after stop
 *
 * Uses Web Audio API for real-time waveform visualization and quality metering.
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
  getPreferredMimeType,
  formatDuration,
  type QualityMetrics,
} from '../utils/audioProcessing';
import { MEDICAL_TERMS_SET } from '../utils/medicalDictionary';

/* ─── Config ─── */
const DEFAULT_MAX_DURATION = 30 * 60 * 1000; // 30 minutes
const QUALITY_POLL_MS = 500;
const SEGMENT_COUNTER_START = 1;
const API_BASE = process.env.REACT_APP_API_URL || '/api/v1';
const PERIODIC_WHISPER_INTERVAL_MS = 5_000; // live preview every 5 seconds

/* ─── Hook ─── */

export interface UseMedicalTranscriptionOptions {
  maxDuration?: number;
  language?: string;
  continuous?: boolean;
  interimResults?: boolean;
}

export interface UseMedicalTranscriptionReturn {
  status: RecordingStatus;
  transcript: string;
  interimText: string;
  segments: TranscriptSegment[];
  duration: number;
  formattedDuration: string;
  quality: QualityMetrics | null;
  audioBlob: Blob | null;
  error: TranscriptionError | null;
  startRecording: () => Promise<void>;
  pauseRecording: () => void;
  resumeRecording: () => void;
  stopRecording: () => void;
  resetRecording: () => void;
  setSpeaker: (speaker: SpeakerLabel) => void;
  waveformData: number[];
}

export function useMedicalTranscription(
  opts: UseMedicalTranscriptionOptions = {}
): UseMedicalTranscriptionReturn {
  const {
    maxDuration = DEFAULT_MAX_DURATION,
    language = 'en-US',
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
  const mimeTypeRef = useRef<string>('audio/webm');
  const durationRef = useRef<number>(0);
  const liveTranscriptRef = useRef<string>('');
  const isRecordingRef = useRef<boolean>(false);
  const periodicIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const periodicInFlightRef = useRef<boolean>(false);

  /* ── Helpers ── */

  /** Build TranscriptSegments from full text (for Whisper result) */
  const makeSegmentsFromText = useCallback(
    (fullText: string, totalDuration: number): TranscriptSegment[] => {
      const sentences = fullText.match(/[^.!?]+[.!?]+/g) || [fullText];
      const segs: TranscriptSegment[] = [];
      let counter = SEGMENT_COUNTER_START;
      const timePerSentence = totalDuration / Math.max(sentences.length, 1);

      for (let i = 0; i < sentences.length; i++) {
        const text = sentences[i].trim();
        if (!text) continue;

        const words = text.split(/\s+/);
        const containsMedical = words.some(w =>
          MEDICAL_TERMS_SET.has(w.toLowerCase().replace(/[^a-z0-9-]/g, ''))
        );

        let speaker: SpeakerLabel = currentSpeaker;
        if (/^(doctor|dr\.?)\s*:/i.test(text)) speaker = 'doctor';
        else if (/^patient\s*:/i.test(text)) speaker = 'patient';

        segs.push({
          id: `seg-${counter++}`,
          text,
          startTime: i * timePerSentence,
          endTime: (i + 1) * timePerSentence,
          confidence: 0.95,
          speaker,
          isFinal: true,
          isMedicalTerm: containsMedical,
          alternatives: [],
          words: words.map(w => ({
            word: w,
            startTime: 0,
            endTime: 0,
            confidence: 0.95,
            isMedical: MEDICAL_TERMS_SET.has(w.toLowerCase().replace(/[^a-z0-9-]/g, '')),
          })),
        });
      }
      return segs;
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
    isRecordingRef.current = false;
    // Stop periodic Whisper live preview
    if (periodicIntervalRef.current) {
      clearInterval(periodicIntervalRef.current);
      periodicIntervalRef.current = null;
    }
    periodicInFlightRef.current = false;
    // Stop MediaRecorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try { mediaRecorderRef.current.stop(); } catch { /* noop */ }
    }
    mediaRecorderRef.current = null;
    // Stop media stream
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
    if (durationIntervalRef.current) clearInterval(durationIntervalRef.current);
    if (qualityIntervalRef.current) clearInterval(qualityIntervalRef.current);
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
  }, []);

  /* ── Send audio to backend Groq Whisper ── */
  const transcribeAudio = useCallback(
    async (blob: Blob): Promise<{ text: string; segments: any[]; duration: number; source: string }> => {
      const formData = new FormData();
      const ext = mimeTypeRef.current.includes('webm') ? 'webm'
        : mimeTypeRef.current.includes('ogg') ? 'ogg' : 'wav';
      formData.append('file', blob, `recording.${ext}`);

      const resp = await fetch(`${API_BASE}/transcription/transcribe-audio`, {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        throw new Error(`Transcription failed: ${resp.status}`);
      }
      return resp.json();
    },
    []
  );

  /* ── Process audio after recording stops ── */
  const processRecordedAudio = useCallback(
    async (blob: Blob) => {
      setAudioBlob(blob);
      setStatus('processing');
      setInterimText('Refining transcription with AI…');

      try {
        const result = await transcribeAudio(blob);
        const fullText = result.text || '';
        const dur = result.duration || durationRef.current;
        const segs = makeSegmentsFromText(fullText, dur);

        setTranscript(fullText);
        setSegments(segs);
        setInterimText('');
        setStatus('completed');
      } catch (err: any) {
        // If Whisper fails, keep the live transcript we have
        if (liveTranscriptRef.current) {
          console.warn('Whisper failed, keeping live transcript:', err);
          setInterimText('');
          setStatus('completed');
        } else {
          console.warn('Backend transcription failed:', err);
          setError({
            code: 'TRANSCRIPTION_FAILED',
            message: 'Could not transcribe audio. Please check your connection or use the Type tab.',
            details: err.message,
            recoverable: true,
          });
          setInterimText('');
          setStatus('error');
        }
      }
    },
    [transcribeAudio, makeSegmentsFromText]
  );

  /* ────────────────────────────────────────────────── */
  /*  START                                             */
  /* ────────────────────────────────────────────────── */
  const startRecording = useCallback(async () => {
    setError(null);
    setStatus('requesting_permission');

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
    isRecordingRef.current = true;

    /* ── Audio Context + Analyser (waveform + quality) ── */
    const audioCtx = new AudioContext({ sampleRate: 48000 });
    audioContextRef.current = audioCtx;
    const source = audioCtx.createMediaStreamSource(stream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);
    analyserRef.current = analyser;

    /* ── MediaRecorder (captures audio for Whisper) ── */
    const mimeType = getPreferredMimeType();
    mimeTypeRef.current = mimeType || 'audio/webm';
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    chunksRef.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current });
      processRecordedAudio(blob);
    };

    recorder.start(1000);
    mediaRecorderRef.current = recorder;

    /* ── Periodic Whisper for live preview (works in ALL browsers) ── */
    periodicInFlightRef.current = false;
    periodicIntervalRef.current = setInterval(async () => {
      // Skip if already processing a periodic request, or no chunks yet
      if (periodicInFlightRef.current || chunksRef.current.length === 0) return;
      if (!isRecordingRef.current) return;

      periodicInFlightRef.current = true;
      try {
        const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current });
        if (blob.size < 1000) { periodicInFlightRef.current = false; return; } // too small
        const result = await transcribeAudio(blob);
        const text = result.text || '';
        if (text && isRecordingRef.current) {
          liveTranscriptRef.current = text;
          setTranscript(text);
          const dur = result.duration || durationRef.current;
          setSegments(makeSegmentsFromText(text, dur));
        }
      } catch (err) {
        console.debug('Periodic live preview failed (non-fatal):', err);
      } finally {
        periodicInFlightRef.current = false;
      }
    }, PERIODIC_WHISPER_INTERVAL_MS);

    /* ── Reset state ── */
    startTimeRef.current = Date.now();
    durationRef.current = 0;
    liveTranscriptRef.current = '';
    setDuration(0);
    setTranscript('');
    setInterimText('');
    setSegments([]);
    setAudioBlob(null);
    segmentCounterRef.current = SEGMENT_COUNTER_START;

    /* Duration timer */
    durationIntervalRef.current = setInterval(() => {
      const elapsed = (Date.now() - startTimeRef.current) / 1000;
      durationRef.current = elapsed;
      setDuration(elapsed);
      if (elapsed * 1000 >= maxDuration) {
        stopRecording();
      }
    }, 1000);

    /* Quality polling + waveform animation */
    startQualityPolling();
    animateWaveform();

    setStatus('recording');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    language,
    maxDuration,
    startQualityPolling,
    animateWaveform,
    processRecordedAudio,
    transcribeAudio,
    makeSegmentsFromText,
  ]);

  /* ── PAUSE ── */
  const pauseRecording = useCallback(() => {
    if (periodicIntervalRef.current) {
      clearInterval(periodicIntervalRef.current);
      periodicIntervalRef.current = null;
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
    // Restart periodic Whisper live preview
    periodicInFlightRef.current = false;
    periodicIntervalRef.current = setInterval(async () => {
      if (periodicInFlightRef.current || chunksRef.current.length === 0) return;
      if (!isRecordingRef.current) return;
      periodicInFlightRef.current = true;
      try {
        const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current });
        if (blob.size < 1000) { periodicInFlightRef.current = false; return; }
        const result = await transcribeAudio(blob);
        const text = result.text || '';
        if (text && isRecordingRef.current) {
          liveTranscriptRef.current = text;
          setTranscript(text);
          const dur = result.duration || durationRef.current;
          setSegments(makeSegmentsFromText(text, dur));
        }
      } catch { /* non-fatal */ } finally {
        periodicInFlightRef.current = false;
      }
    }, PERIODIC_WHISPER_INTERVAL_MS);
    if (mediaRecorderRef.current?.state === 'paused') {
      mediaRecorderRef.current.resume();
    }
    durationIntervalRef.current = setInterval(() => {
      const elapsed = (Date.now() - startTimeRef.current) / 1000;
      durationRef.current = elapsed;
      setDuration(elapsed);
    }, 1000);
    startQualityPolling();
    animateWaveform();
    setStatus('recording');
  }, [startQualityPolling, animateWaveform, transcribeAudio, makeSegmentsFromText]);

  /* ── STOP ── */
  const stopRecording = useCallback(() => {
    isRecordingRef.current = false;

    // Stop periodic Whisper live preview
    if (periodicIntervalRef.current) {
      clearInterval(periodicIntervalRef.current);
      periodicIntervalRef.current = null;
    }
    periodicInFlightRef.current = false;

    // Clear timers and animation
    if (durationIntervalRef.current) clearInterval(durationIntervalRef.current);
    if (qualityIntervalRef.current) clearInterval(qualityIntervalRef.current);
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

    // Stop MediaRecorder → triggers onstop → processRecordedAudio (Whisper)
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }

    // Release mic after short delay so onstop fires
    setTimeout(() => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
        audioContextRef.current = null;
      }
    }, 300);
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
    chunksRef.current = [];
    durationRef.current = 0;
    liveTranscriptRef.current = '';
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
