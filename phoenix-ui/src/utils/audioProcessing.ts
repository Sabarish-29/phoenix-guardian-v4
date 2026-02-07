/**
 * Audio Processing Utilities for Phoenix Guardian.
 *
 * Provides volume metering, waveform analysis, noise detection,
 * and quality scoring — all using the native Web Audio API.
 */

/* ─── Volume / RMS ─── */

/**
 * Compute RMS (root-mean-square) volume from audio analyser data.
 * Returns a value between 0 and 1.
 */
export function computeRMS(dataArray: Uint8Array): number {
  let sum = 0;
  for (let i = 0; i < dataArray.length; i++) {
    const v = (dataArray[i] - 128) / 128; // normalise to -1…1
    sum += v * v;
  }
  return Math.sqrt(sum / dataArray.length);
}

/**
 * Convert RMS to decibels (dBFS).  Clamped to −100…0.
 */
export function rmsToDecibels(rms: number): number {
  if (rms <= 0) return -100;
  const db = 20 * Math.log10(rms);
  return Math.max(-100, Math.min(0, db));
}

/* ─── Waveform Data ─── */

/**
 * Extract a normalised waveform (0…1) from a time-domain analyser buffer.
 * Returns an array of `bars` values suitable for canvas rendering.
 */
export function extractWaveform(
  dataArray: Uint8Array,
  bars: number = 64
): number[] {
  const step = Math.floor(dataArray.length / bars);
  const waveform: number[] = [];
  for (let i = 0; i < bars; i++) {
    let max = 0;
    for (let j = 0; j < step; j++) {
      const v = Math.abs((dataArray[i * step + j] - 128) / 128);
      if (v > max) max = v;
    }
    waveform.push(max);
  }
  return waveform;
}

/* ─── Noise Level ─── */

/**
 * Estimate a noise-floor level from a frequency-domain analyser snapshot.
 * Returns 0 (silent) … 1 (very noisy).
 */
export function estimateNoiseLevel(frequencyData: Uint8Array): number {
  // High-frequency energy (> ½ Nyquist) is mostly noise
  const halfLen = Math.floor(frequencyData.length / 2);
  let noiseSum = 0;
  let signalSum = 0;
  for (let i = 0; i < halfLen; i++) {
    signalSum += frequencyData[i];
  }
  for (let i = halfLen; i < frequencyData.length; i++) {
    noiseSum += frequencyData[i];
  }
  const total = signalSum + noiseSum;
  if (total === 0) return 0;
  return noiseSum / total;
}

/* ─── Clipping Detection ─── */

/**
 * Detect whether audio is clipping (values hitting ±1).
 * Returns fraction of samples that are clipping (0…1).
 */
export function detectClipping(dataArray: Uint8Array, threshold = 250): number {
  let clipped = 0;
  for (let i = 0; i < dataArray.length; i++) {
    if (dataArray[i] >= threshold || dataArray[i] <= 255 - threshold) {
      clipped++;
    }
  }
  return clipped / dataArray.length;
}

/* ─── Quality Score ─── */

export interface QualityMetrics {
  score: number;        // 0–100
  volume: number;       // RMS 0–1
  volumeDb: number;     // dBFS
  noiseLevel: number;   // 0–1
  clippingRate: number; // 0–1
  issues: string[];
}

/**
 * Compute an overall audio quality score from analyser buffers.
 */
export function assessQuality(
  timeDomainData: Uint8Array,
  frequencyData: Uint8Array
): QualityMetrics {
  const volume = computeRMS(timeDomainData);
  const volumeDb = rmsToDecibels(volume);
  const noiseLevel = estimateNoiseLevel(frequencyData);
  const clippingRate = detectClipping(timeDomainData);

  let score = 100;
  const issues: string[] = [];

  // Volume too low
  if (volume < 0.02) {
    score -= 30;
    issues.push('Volume too low — speak closer to the microphone');
  } else if (volume < 0.05) {
    score -= 10;
    issues.push('Volume is a bit low');
  }

  // Clipping
  if (clippingRate > 0.05) {
    score -= 25;
    issues.push('Audio clipping detected — reduce volume or move back');
  } else if (clippingRate > 0.01) {
    score -= 10;
    issues.push('Slight clipping detected');
  }

  // Noise
  if (noiseLevel > 0.5) {
    score -= 30;
    issues.push('High background noise — move to a quieter area');
  } else if (noiseLevel > 0.35) {
    score -= 15;
    issues.push('Moderate background noise detected');
  }

  return {
    score: Math.max(0, score),
    volume,
    volumeDb,
    noiseLevel,
    clippingRate,
    issues,
  };
}

/* ─── Format Helpers ─── */

/** Format seconds → "MM:SS" */
export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

/** Format bytes → human-readable */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ─── Browser Support ─── */

/** Check whether the browser supports the Web Speech API. */
export function isSpeechRecognitionSupported(): boolean {
  return !!(
    (window as any).SpeechRecognition ||
    (window as any).webkitSpeechRecognition
  );
}

/** Return the SpeechRecognition constructor (vendor-prefixed). */
export function getSpeechRecognition(): (new () => SpeechRecognition) | null {
  return (
    (window as any).SpeechRecognition ||
    (window as any).webkitSpeechRecognition ||
    null
  );
}

/** Check MediaRecorder support */
export function isMediaRecorderSupported(): boolean {
  return typeof MediaRecorder !== 'undefined';
}

/** Preferred MIME for MediaRecorder */
export function getPreferredMimeType(): string {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ];
  for (const t of types) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return '';
}
