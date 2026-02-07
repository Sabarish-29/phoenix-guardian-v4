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
  const confidenceColor = (c: number) => {
    if (c >= 0.95) return 'bg-green-100 text-green-800';
    if (c >= 0.80) return 'bg-yellow-100 text-yellow-800';
    return 'bg-red-100 text-red-800';
  };

  const confidenceBorder = (c: number) => {
    if (c >= 0.95) return 'border-l-green-500';
    if (c >= 0.80) return 'border-l-yellow-500';
    return 'border-l-red-500';
  };

  /* ─── Speaker icon ─── */
  const speakerBadge = (speaker: string) => {
    if (speaker === 'doctor') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
          🩺 Doctor
        </span>
      );
    }
    if (speaker === 'patient') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
          🧑 Patient
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
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
              className="bg-blue-50 text-blue-800 border-b-2 border-blue-400 rounded px-0.5 cursor-help"
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
    <div className="border rounded-xl overflow-hidden bg-white shadow-sm">
      {/* ── Header ── */}
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-gray-800 text-sm">Transcript Editor</h3>
          {stats.avgConfidence > 0 && (
            <span
              className={`text-xs font-medium px-2 py-0.5 rounded-full ${confidenceColor(
                stats.avgConfidence
              )}`}
            >
              {(stats.avgConfidence * 100).toFixed(0)}% confidence
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSegments(!showSegments)}
            className="text-xs text-gray-500 hover:text-gray-700 transition"
          >
            {showSegments ? 'Full Text' : 'Segments'}
          </button>

          {!readOnly && !isEditing && (
            <button
              onClick={() => setIsEditing(true)}
              className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
            >
              ✏️ Edit
            </button>
          )}
        </div>
      </div>

      {/* ── Segment view ── */}
      {showSegments && segments.length > 0 && !isEditing && (
        <div className="max-h-[400px] overflow-y-auto divide-y divide-gray-50">
          {segments.map((seg) => (
            <div
              key={seg.id}
              className={`px-4 py-3 border-l-4 ${confidenceBorder(seg.confidence)} hover:bg-gray-50 transition`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  {speakerBadge(seg.speaker)}
                  <span className="text-xs text-gray-400">
                    {seg.startTime.toFixed(1)}s – {seg.endTime.toFixed(1)}s
                  </span>
                </div>
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full ${confidenceColor(
                    seg.confidence
                  )}`}
                >
                  {(seg.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-sm text-gray-800 leading-relaxed">
                {renderHighlightedText(seg.text)}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* ── Full text view (read-only with highlights) ── */}
      {(!showSegments || segments.length === 0) && !isEditing && (
        <div className="px-4 py-4 max-h-[400px] overflow-y-auto">
          <div className="text-sm leading-relaxed whitespace-pre-wrap">
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
            className="w-full min-h-[300px] text-sm font-mono border border-gray-300 rounded-lg p-3
                       focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition"
            placeholder="Edit the transcript here…"
          />
          <div className="mt-3 flex items-center justify-between">
            <div className="text-xs text-gray-500">
              Corrections are tracked for HIPAA audit compliance.
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setEditedText(transcript);
                  setIsEditing(false);
                }}
                className="px-4 py-2 text-sm text-gray-600 rounded-lg border border-gray-300
                           hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg
                           hover:bg-blue-700 transition"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Footer: Stats & Medical Terms ── */}
      <div className="px-4 py-3 bg-gray-50 border-t border-gray-100">
        {/* Stats row */}
        <div className="flex items-center gap-4 text-xs text-gray-500 mb-2">
          <span>{stats.wordCount} words</span>
          <span>{stats.charCount} chars</span>
          <span>{stats.segmentCount} segments</span>
          {stats.correctionCount > 0 && (
            <span className="text-amber-600">{stats.correctionCount} correction(s)</span>
          )}
        </div>

        {/* Medical terms */}
        {detectedTerms.length > 0 && (
          <div>
            <div className="text-xs text-gray-500 mb-1">
              Medical terms detected ({detectedTerms.length}):
            </div>
            <div className="flex flex-wrap gap-1">
              {detectedTerms.slice(0, 20).map((term, i) => (
                <span
                  key={i}
                  className="inline-block px-2 py-0.5 text-xs bg-blue-50 text-blue-700
                             border border-blue-200 rounded-full"
                >
                  {term}
                </span>
              ))}
              {detectedTerms.length > 20 && (
                <span className="text-xs text-gray-400 self-center">
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
