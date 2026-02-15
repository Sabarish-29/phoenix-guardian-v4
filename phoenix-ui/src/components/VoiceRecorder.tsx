/**
 * VoiceRecorder — Medical-grade voice recorder with real-time transcription.
 *
 * Features:
 *  • High-quality audio capture (48 kHz, mono, noise suppression)
 *  • Live waveform & volume meter
 *  • Real-time speech-to-text via Web Speech API
 *  • Pause / resume / stop controls
 *  • Audio quality scoring with live warnings
 *  • Speaker toggle (Doctor / Patient)
 *  • Medical term highlighting in live transcript
 *  • Error recovery with clear user guidance
 */

import React, { useCallback, useMemo } from 'react';
import { useMedicalTranscription } from '../hooks/useMedicalTranscription';
import { isMedicalTerm } from '../utils/medicalDictionary';
import type { TranscriptSegment, SpeakerLabel } from '../types/transcription';

/* ─── Props ─── */
export interface VoiceRecorderProps {
  /** Called whenever the accumulated transcript changes. */
  onTranscriptUpdate: (text: string, segments: TranscriptSegment[]) => void;
  /** Called when recording is stopped and finalised. */
  onRecordingComplete: (audioBlob: Blob | null, transcript: string, segments: TranscriptSegment[]) => void;
  /** Max recording duration in ms (default 30 min). */
  maxDuration?: number;
  /** Disable the whole recorder. */
  disabled?: boolean;
}

/* ─── Component ─── */
export const VoiceRecorder: React.FC<VoiceRecorderProps> = ({
  onTranscriptUpdate,
  onRecordingComplete,
  maxDuration,
  disabled = false,
}) => {
  const {
    status,
    transcript,
    interimText,
    segments,
    formattedDuration,
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
  } = useMedicalTranscription({ maxDuration });

  /* Notify parent on transcript changes */
  React.useEffect(() => {
    if (transcript) {
      onTranscriptUpdate(transcript, segments);
    }
  }, [transcript, segments, onTranscriptUpdate]);

  /* Notify parent on completion */
  React.useEffect(() => {
    if (status === 'completed') {
      onRecordingComplete(audioBlob, transcript, segments);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  /* ─── Handlers ─── */
  const handleStart = useCallback(() => {
    if (!disabled) startRecording();
  }, [disabled, startRecording]);

  const handleStop = useCallback(() => {
    stopRecording();
  }, [stopRecording]);

  const handlePause = useCallback(() => {
    pauseRecording();
  }, [pauseRecording]);

  const handleResume = useCallback(() => {
    resumeRecording();
  }, [resumeRecording]);

  const handleReset = useCallback(() => {
    resetRecording();
  }, [resetRecording]);

  /* ─── Quality colour ─── */
  const qualityColor = useMemo(() => {
    if (!quality) return 'text-gray-400';
    if (quality.score >= 80) return 'text-green-600';
    if (quality.score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  }, [quality]);

  const qualityBg = useMemo(() => {
    if (!quality) return 'bg-gray-200';
    if (quality.score >= 80) return 'bg-green-500';
    if (quality.score >= 60) return 'bg-yellow-500';
    return 'bg-red-500';
  }, [quality]);

  /* ─── Highlighted live transcript ─── */
  const highlightedTranscript = useMemo(() => {
    const full = transcript + (interimText ? ` ${interimText}` : '');
    if (!full.trim()) return null;

    return full.split(/(\s+)/).map((token, i) => {
      const clean = token.toLowerCase().replace(/[^a-z0-9-]/g, '');
      if (isMedicalTerm(clean)) {
        return (
          <span key={i} className="bg-blue-100 text-blue-800 rounded px-0.5 font-medium" title="Medical term">
            {token}
          </span>
        );
      }
      return <span key={i}>{token}</span>;
    });
  }, [transcript, interimText]);

  /* ═══════════════════ RENDER ═══════════════════ */

  /* Error State */
  if (error) {
    return (
      <div className="border-2 border-red-200 rounded-xl p-6 bg-red-50">
        <div className="flex items-start gap-3">
          <span className="text-2xl">🚫</span>
          <div className="flex-1">
            <h3 className="font-semibold text-red-800">{error.code.replace(/_/g, ' ')}</h3>
            <p className="text-red-700 text-sm mt-1">{error.message}</p>
            {error.details && (
              <p className="text-red-500 text-xs mt-1">{error.details}</p>
            )}
            {error.recoverable && (
              <button
                onClick={handleReset}
                className="mt-3 px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 transition"
              >
                Try Again
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  /* Idle State */
  if (status === 'idle') {
    return (
      <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-400 transition">
        <div className="text-5xl mb-4">🎤</div>
        <h3 className="text-lg font-semibold text-gray-800 mb-2">Voice Recording</h3>
        <p className="text-sm text-gray-500 mb-6 max-w-md mx-auto">
          Record the doctor-patient conversation. Speech will be transcribed in real-time
          using medical-grade recognition.
        </p>
        <button
          onClick={handleStart}
          disabled={disabled}
          className="px-6 py-3 bg-blue-600 text-white rounded-xl font-medium
                     hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
                     transition shadow-lg shadow-blue-600/25 flex items-center gap-2 mx-auto"
        >
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
          Start Recording
        </button>
        <p className="text-xs text-gray-400 mt-3">
          Requires microphone permission • Works best in Chrome or Edge
        </p>
      </div>
    );
  }

  /* Recording / Paused / Processing / Completed */
  const isActive = status === 'recording' || status === 'paused';
  const isRecording = status === 'recording';

  return (
    <div className="border-2 border-blue-200 rounded-xl overflow-hidden bg-white shadow-sm">
      {/* ── Header Bar ── */}
      <div className={`px-4 py-3 flex items-center justify-between ${
        isRecording ? 'bg-red-50' : status === 'paused' ? 'bg-yellow-50' : 'bg-blue-50'
      }`}>
        <div className="flex items-center gap-3">
          {/* Pulsing recording dot */}
          {isRecording && (
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
            </span>
          )}
          {status === 'paused' && (
            <span className="h-3 w-3 rounded-sm bg-yellow-500"></span>
          )}
          {(status === 'processing' || status === 'completed') && (
            <span className="h-3 w-3 rounded-full bg-green-500"></span>
          )}

          <span className="font-semibold text-sm">
            {isRecording ? 'Recording' : status === 'paused' ? 'Paused' : status === 'processing' ? 'Processing…' : 'Complete'}
          </span>
          <span className="text-sm font-mono text-gray-600">{formattedDuration}</span>
        </div>

        {/* Quality badge */}
        {quality && isActive && (
          <div className="flex items-center gap-2">
            <span className={`text-xs font-medium ${qualityColor}`}>
              Quality: {quality.score}%
            </span>
            <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${qualityBg}`}
                style={{ width: `${quality.score}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* ── Waveform ── */}
      {isActive && (
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-100">
          <div className="flex items-end justify-center gap-[2px] h-12">
            {(waveformData.length > 0 ? waveformData : new Array(48).fill(0)).map((v, i) => (
              <div
                key={i}
                className={`w-1 rounded-full transition-all duration-75 ${
                  isRecording ? 'bg-blue-500' : 'bg-gray-300'
                }`}
                style={{
                  height: `${Math.max(2, v * 48)}px`,
                  opacity: isRecording ? 0.6 + v * 0.4 : 0.4,
                }}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Quality Warnings ── */}
      {quality && quality.issues.length > 0 && isActive && (
        <div className="px-4 py-2 bg-yellow-50 border-b border-yellow-100">
          {quality.issues.map((issue, i) => (
            <p key={i} className="text-xs text-yellow-700 flex items-center gap-1">
              <span>⚠️</span> {issue}
            </p>
          ))}
        </div>
      )}

      {/* ── Speaker Toggle ── */}
      {isActive && (
        <div className="px-4 py-2 border-b border-gray-100 flex items-center gap-2">
          <span className="text-xs text-gray-500 mr-1">Speaker:</span>
          {(['doctor', 'patient'] as SpeakerLabel[]).map((s) => (
            <button
              key={s}
              onClick={() => setSpeaker(s)}
              className={`px-3 py-1 text-xs rounded-full font-medium transition ${
                s === 'doctor'
                  ? 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                  : 'bg-green-100 text-green-700 hover:bg-green-200'
              }`}
            >
              {s === 'doctor' ? '🩺 Doctor' : '🧑 Patient'}
            </button>
          ))}
        </div>
      )}

      {/* ── Live Transcript ── */}
      <div className="px-4 py-4">
        <div className="text-xs text-gray-500 mb-2 flex items-center justify-between">
          <span>Live Transcript</span>
          {segments.length > 0 && (
            <span>{segments.length} segment{segments.length !== 1 ? 's' : ''}</span>
          )}
        </div>
        <div
          className="min-h-[120px] max-h-[250px] overflow-y-auto text-sm leading-relaxed
                     bg-gray-50 rounded-lg p-3 border border-gray-200"
        >
          {highlightedTranscript ? (
            <div className="whitespace-pre-wrap">
              {highlightedTranscript}
              {interimText && (
                <span className="text-gray-400 italic"> {interimText}</span>
              )}
            </div>
          ) : (
            <p className="text-gray-400 italic">
              {isRecording
                ? 'Listening… start speaking and your words will appear here.'
                : status === 'paused'
                  ? 'Recording paused. Resume to continue transcription.'
                  : 'No transcript yet.'}
            </p>
          )}
        </div>
      </div>

      {/* ── Controls ── */}
      <div className="px-4 py-3 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isRecording && (
            <button
              onClick={handlePause}
              className="px-4 py-2 bg-yellow-500 text-white rounded-lg text-sm font-medium
                         hover:bg-yellow-600 transition flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
              </svg>
              Pause
            </button>
          )}
          {status === 'paused' && (
            <button
              onClick={handleResume}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium
                         hover:bg-green-700 transition flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
              Resume
            </button>
          )}
          {isActive && (
            <button
              onClick={handleStop}
              className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium
                         hover:bg-red-700 transition flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <rect x="6" y="6" width="12" height="12" rx="1" />
              </svg>
              Stop & Finish
            </button>
          )}
        </div>

        {/* Reset / New recording */}
        {(status === 'completed' || status === 'processing') && (
          <button
            onClick={handleReset}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm font-medium
                       hover:bg-gray-300 transition"
          >
            New Recording
          </button>
        )}

        {/* Word count */}
        <div className="text-xs text-gray-500">
          {transcript.split(/\s+/).filter(Boolean).length} words
        </div>
      </div>
    </div>
  );
};

export default VoiceRecorder;
