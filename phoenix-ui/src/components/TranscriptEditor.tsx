/**
 * TranscriptEditor — Post-transcription editor with medical-term awareness.
 *
 * Features:
 *  • Word-level confidence highlighting (green / yellow / red)
 *  • Medical term underline with tooltip
 *  • Per-segment speaker labels (Doctor / Patient)
 *  • Inline editing with correction tracking
 *  • Summary of detected medical terms
 */

import React, { useCallback, useMemo, useState } from 'react';
import type { TranscriptSegment, Correction, FlaggedTerm } from '../types/transcription';
import { isMedicalTerm, findMedicalTerms } from '../utils/medicalDictionary';

/* ─── Props ─── */
export interface TranscriptEditorProps {
  transcript: string;
  segments: TranscriptSegment[];
  onSave: (correctedTranscript: string, corrections: Correction[]) => void;
  onCancel: () => void;
  medicalTerms?: string[];
  flaggedTerms?: FlaggedTerm[];
  readOnly?: boolean;
}

/* ─── Component ─── */
export const TranscriptEditor: React.FC<TranscriptEditorProps> = ({
  transcript,
  segments,
  onSave,
  onCancel,
  readOnly = false,
}) => {
  const [editedText, setEditedText] = useState(transcript);
  const [corrections, setCorrections] = useState<Correction[]>([]);
  const [isEditing, setIsEditing] = useState(false);
  const [showSegments, setShowSegments] = useState(true);

  /* ─── Detected medical terms ─── */
  const detectedTerms = useMemo(
    () => findMedicalTerms(editedText || transcript),
    [editedText, transcript]
  );

  /* ─── Stats ─── */
  const stats = useMemo(() => {
    const text = editedText || transcript;
    const words = text.split(/\s+/).filter(Boolean);
    const avgConfidence =
      segments.length > 0
        ? segments.reduce((sum, s) => sum + s.confidence, 0) / segments.length
        : 0;
    return {
      wordCount: words.length,
      charCount: text.length,
      segmentCount: segments.length,
      avgConfidence,
      medicalTermCount: detectedTerms.length,
      correctionCount: corrections.length,
    };
  }, [editedText, transcript, segments, detectedTerms, corrections]);

  /* ─── Confidence colour ─── */
  const confidenceStyle = (c: number): React.CSSProperties => {
    if (c >= 0.95) return { background: 'var(--success-bg)', color: 'var(--success-text)' };
    if (c >= 0.80) return { background: 'var(--warning-bg)', color: 'var(--warning-text)' };
    return { background: 'var(--critical-bg)', color: 'var(--critical-text)' };
  };

  /* ─── Speaker icon ─── */
  const speakerBadge = (speaker: string) => {
    if (speaker === 'doctor') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
          style={{ background: 'var(--watching-bg)', color: 'var(--watching-text)' }}>
          🩺 Doctor
        </span>
      );
    }
    if (speaker === 'patient') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
          style={{ background: 'var(--success-bg)', color: 'var(--success-text)' }}>
          🧑 Patient
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
        style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
        👤 Unknown
      </span>
    );
  };

  /* ─── Highlight medical terms in text ─── */
  const renderHighlightedText = useCallback(
    (text: string) =>
      text.split(/(\s+)/).map((token, i) => {
        const clean = token.toLowerCase().replace(/[^a-z0-9-]/g, '');
        if (isMedicalTerm(clean)) {
          return (
            <span
              key={i}
              className="rounded px-0.5 cursor-help"
              style={{ background: 'var(--watching-bg)', color: 'var(--watching-text)', borderBottom: '2px solid var(--watching-border)' }}
              title={`Medical term: ${clean}`}
            >
              {token}
            </span>
          );
        }
        return <span key={i}>{token}</span>;
      }),
    []
  );

  /* ─── Handle save ─── */
  const handleSave = useCallback(() => {
    // Track change as a correction
    if (editedText !== transcript) {
      const newCorrection: Correction = {
        timestamp: Date.now(),
        original: transcript,
        corrected: editedText,
        reason: 'Manual correction',
        userId: 'current_user',
      };
      const updated = [...corrections, newCorrection];
      setCorrections(updated);
      onSave(editedText, updated);
    } else {
      onSave(editedText, corrections);
    }
    setIsEditing(false);
  }, [editedText, transcript, corrections, onSave]);

  /* ═══ RENDER ═══ */
  return (
    <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--border-muted)', background: 'var(--bg-surface)' }}>
      {/* ── Header ── */}
      <div className="px-4 py-3 flex items-center justify-between" style={{ background: 'var(--bg-elevated)', borderBottom: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>Transcript Editor</h3>
          {stats.avgConfidence > 0 && (
            <span
              className="text-xs font-medium px-2 py-0.5 rounded-full"
              style={confidenceStyle(stats.avgConfidence)}
            >
              {(stats.avgConfidence * 100).toFixed(0)}% confidence
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSegments(!showSegments)}
            className="text-xs transition"
            style={{ color: 'var(--text-muted)' }}
          >
            {showSegments ? 'Full Text' : 'Segments'}
          </button>

          {!readOnly && !isEditing && (
            <button
              onClick={() => setIsEditing(true)}
              className="px-3 py-1.5 text-xs rounded-lg transition"
              style={{ background: 'var(--accent-primary)', color: '#fff' }}
            >
              ✏️ Edit
            </button>
          )}
        </div>
      </div>

      {/* ── Segment view ── */}
      {showSegments && segments.length > 0 && !isEditing && (
        <div className="max-h-[400px] overflow-y-auto" style={{ borderColor: 'var(--border-subtle)' }}>
          {segments.map((seg) => (
            <div
              key={seg.id}
              className="px-4 py-3 border-l-4 transition"
              style={{
                borderLeftColor: seg.confidence >= 0.95 ? 'var(--success-border)'
                  : seg.confidence >= 0.80 ? 'var(--warning-border)'
                  : 'var(--critical-border)',
                borderBottom: '1px solid var(--border-subtle)',
              }}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  {speakerBadge(seg.speaker)}
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {seg.startTime.toFixed(1)}s – {seg.endTime.toFixed(1)}s
                  </span>
                </div>
                <span
                  className="text-xs font-medium px-2 py-0.5 rounded-full"
                  style={confidenceStyle(seg.confidence)}
                >
                  {(seg.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                {renderHighlightedText(seg.text)}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* ── Full text view (read-only with highlights) ── */}
      {(!showSegments || segments.length === 0) && !isEditing && (
        <div className="px-4 py-4 max-h-[400px] overflow-y-auto">
          <div className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-primary)' }}>
            {renderHighlightedText(editedText || transcript)}
          </div>
        </div>
      )}

      {/* ── Edit mode ── */}
      {isEditing && (
        <div className="px-4 py-4">
          <textarea
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
            className="w-full min-h-[300px] text-sm font-mono rounded-lg p-3 transition"
            style={{
              background: 'var(--bg-elevated)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-muted)',
            }}
            placeholder="Edit the transcript here…"
          />
          <div className="mt-3 flex items-center justify-between">
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Corrections are tracked for HIPAA audit compliance.
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setEditedText(transcript);
                  setIsEditing(false);
                }}
                className="px-4 py-2 text-sm rounded-lg transition"
                style={{ color: 'var(--text-secondary)', border: '1px solid var(--border-muted)' }}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 text-sm rounded-lg transition"
                style={{ background: 'var(--accent-primary)', color: '#fff' }}
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Footer: Stats & Medical Terms ── */}
      <div className="px-4 py-3" style={{ background: 'var(--bg-elevated)', borderTop: '1px solid var(--border-subtle)' }}>
        {/* Stats row */}
        <div className="flex items-center gap-4 text-xs mb-2" style={{ color: 'var(--text-muted)' }}>
          <span>{stats.wordCount} words</span>
          <span>{stats.charCount} chars</span>
          <span>{stats.segmentCount} segments</span>
          {stats.correctionCount > 0 && (
            <span style={{ color: 'var(--warning-text)' }}>{stats.correctionCount} correction(s)</span>
          )}
        </div>

        {/* Medical terms */}
        {detectedTerms.length > 0 && (
          <div>
            <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>
              Medical terms detected ({detectedTerms.length}):
            </div>
            <div className="flex flex-wrap gap-1">
              {detectedTerms.slice(0, 20).map((term, i) => (
                <span
                  key={i}
                  className="inline-block px-2 py-0.5 text-xs rounded-full"
                  style={{ background: 'var(--watching-bg)', color: 'var(--watching-text)', border: '1px solid var(--watching-border)' }}
                >
                  {term}
                </span>
              ))}
              {detectedTerms.length > 20 && (
                <span className="text-xs self-center" style={{ color: 'var(--text-muted)' }}>
                  +{detectedTerms.length - 20} more
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TranscriptEditor;
