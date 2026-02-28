/**
 * VoiceRecorder — Medical-grade voice recorder with AI transcription.
 *
 * Features:
 *  • High-quality audio capture (48 kHz, mono, noise suppression)
 *  • Live waveform & volume meter
 *  • AI-powered transcription via Groq Whisper
 *  • Pause / resume / stop controls
 *  • Audio quality scoring with live warnings
 *  • Speaker toggle (Doctor / Patient)
 *  • Medical term highlighting in transcript
 *  • Works offline with demo transcript fallback
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
          <span key={i} className="rounded px-0.5 font-medium" style={{ background: 'var(--watching-bg)', color: 'var(--watching-text)' }} title="Medical term">
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
    const isNetworkError = error.code === 'NETWORK_ERROR';
    return (
      <div
        className="rounded-xl p-6"
        style={{
          background: 'var(--critical-bg)',
          border: '2px solid var(--critical-border)',
        }}
      >
        <div className="flex items-start gap-3">
          <span className="text-2xl">🚫</span>
          <div className="flex-1">
            <h3 className="font-semibold" style={{ color: 'var(--critical-text)' }}>
              {error.code.replace(/_/g, ' ')}
            </h3>
            <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
              {isNetworkError
                ? 'Could not reach the transcription server. Please check your connection and try again.'
                : error.message}
            </p>
            {error.details && (
              <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{error.details}</p>
            )}
            {error.recoverable && (
              <button
                onClick={handleReset}
                className="mt-3 px-4 py-2 rounded-lg text-sm font-medium transition"
                style={{
                  background: 'var(--critical-border)',
                  color: '#fff',
                }}
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
      <div
        className="rounded-xl p-8 text-center transition"
        style={{
          border: '2px dashed var(--border-muted)',
          background: 'var(--bg-surface)',
        }}
      >
        <div className="text-5xl mb-4">🎤</div>
        <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>Voice Recording</h3>
        <p className="text-sm mb-6 max-w-md mx-auto" style={{ color: 'var(--text-muted)' }}>
          Record the doctor-patient conversation. Your audio will be transcribed
          using AI (Groq Whisper) after you stop recording.
        </p>
        <button
          onClick={handleStart}
          disabled={disabled}
          className="btn-primary px-6 py-3 rounded-xl font-medium flex items-center gap-2 mx-auto
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
          Start Recording
        </button>
        <p className="text-xs mt-3" style={{ color: 'var(--text-muted)' }}>
          Requires microphone permission • Audio transcribed via Groq Whisper AI
        </p>
      </div>
    );
  }

  /* Recording / Paused / Processing / Completed */
  const isActive = status === 'recording' || status === 'paused';
  const isRecording = status === 'recording';

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        border: '2px solid var(--border-muted)',
        background: 'var(--bg-surface)',
      }}
    >
      {/* ── Header Bar ── */}
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{
          background: isRecording
            ? 'var(--critical-bg)'
            : status === 'paused'
              ? 'var(--warning-bg)'
              : 'var(--watching-bg)',
        }}
      >
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

          <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
            {isRecording ? 'Recording' : status === 'paused' ? 'Paused' : status === 'processing' ? 'Processing…' : 'Complete'}
          </span>
          <span className="text-sm font-mono" style={{ color: 'var(--text-secondary)' }}>{formattedDuration}</span>
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
        <div
          className="px-4 py-3"
          style={{ background: 'var(--bg-elevated)', borderBottom: '1px solid var(--border-subtle)' }}
        >
          <div className="flex items-end justify-center gap-[2px] h-12">
            {(waveformData.length > 0 ? waveformData : new Array(48).fill(0)).map((v, i) => (
              <div
                key={i}
                className="w-1 rounded-full transition-all duration-75"
                style={{
                  background: isRecording ? 'var(--voice-primary)' : 'var(--border-muted)',
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
        <div
          className="px-4 py-2"
          style={{ background: 'var(--warning-bg)', borderBottom: '1px solid var(--warning-border)' }}
        >
          {quality.issues.map((issue, i) => (
            <p key={i} className="text-xs flex items-center gap-1" style={{ color: 'var(--warning-text)' }}>
              <span>⚠️</span> {issue}
            </p>
          ))}
        </div>
      )}

      {/* ── Speaker Toggle ── */}
      {isActive && (
        <div
          className="px-4 py-2 flex items-center gap-2"
          style={{ borderBottom: '1px solid var(--border-subtle)' }}
        >
          <span className="text-xs mr-1" style={{ color: 'var(--text-muted)' }}>Speaker:</span>
          {(['doctor', 'patient'] as SpeakerLabel[]).map((s) => (
            <button
              key={s}
              onClick={() => setSpeaker(s)}
              className="px-3 py-1 text-xs rounded-full font-medium transition"
              style={{
                background: s === 'doctor' ? 'var(--watching-bg)' : 'var(--success-bg)',
                color: s === 'doctor' ? 'var(--watching-text)' : 'var(--success-text)',
                border: `1px solid ${s === 'doctor' ? 'var(--watching-border)' : 'var(--success-border)'}`,
              }}
            >
              {s === 'doctor' ? '🩺 Doctor' : '🧑 Patient'}
            </button>
          ))}
        </div>
      )}

      {/* ── Live Transcript ── */}
      <div className="px-4 py-4">
        <div className="text-xs mb-2 flex items-center justify-between" style={{ color: 'var(--text-muted)' }}>
          <span>Live Transcript</span>
          {segments.length > 0 && (
            <span>{segments.length} segment{segments.length !== 1 ? 's' : ''}</span>
          )}
        </div>
        <div
          className="min-h-[120px] max-h-[250px] overflow-y-auto text-sm leading-relaxed rounded-lg p-3"
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
        >
          {highlightedTranscript ? (
            <div className="whitespace-pre-wrap">
              {highlightedTranscript}
              {interimText && (
                <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}> {interimText}</span>
              )}
            </div>
          ) : status === 'processing' ? (
            <div className="flex flex-col items-center justify-center h-full py-4">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 mb-3" style={{ borderColor: 'var(--accent-primary)' }}></div>
              <p style={{ color: 'var(--accent-primary)', fontWeight: 500, fontSize: '0.875rem' }}>
                Refining transcription with AI…
              </p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                Using Groq Whisper for accurate medical transcription
              </p>
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
              {isRecording
                ? 'Listening… your words will appear in a few seconds.'
                : status === 'paused'
                  ? 'Recording paused. Resume to continue or stop to finalize.'
                  : 'No transcript yet.'}
            </p>
          )}
        </div>
      </div>

      {/* ── Controls ── */}
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{ background: 'var(--bg-elevated)', borderTop: '1px solid var(--border-subtle)' }}
      >
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
            className="btn-ghost px-4 py-2 rounded-lg text-sm font-medium transition"
          >
            New Recording
          </button>
        )}

        {/* Word count */}
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {transcript.split(/\s+/).filter(Boolean).length} words
        </div>
      </div>
    </div>
  );
};

export default VoiceRecorder;
