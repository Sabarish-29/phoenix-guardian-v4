-- =============================================================================
-- Phoenix Guardian V5 Phase 2 — SilentVoice Supporting Tables
-- =============================================================================
-- Creates tables needed by SilentVoiceAgent that don't yet exist:
--   patients, admissions, vitals, medication_administrations
-- Then seeds Patient C (Lakshmi Devi) demo data.
--
-- Safe to re-run: uses IF NOT EXISTS and ON CONFLICT DO NOTHING.
-- =============================================================================

BEGIN;

-- ─── 1. patients table ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patients (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(200) NOT NULL,
    age         INTEGER,
    sex         VARCHAR(20),
    mrn         VARCHAR(50),
    bed         VARCHAR(50),
    ward        VARCHAR(100),
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_patients_name ON patients (name);
CREATE INDEX IF NOT EXISTS idx_patients_mrn ON patients (mrn);

-- ─── 2. admissions table ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS admissions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id    UUID NOT NULL REFERENCES patients(id),
    admitted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    discharged_at TIMESTAMPTZ,
    ward          VARCHAR(100),
    bed           VARCHAR(50),
    diagnosis     TEXT,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admissions_patient_id ON admissions (patient_id);
CREATE INDEX IF NOT EXISTS idx_admissions_discharged ON admissions (discharged_at);

-- ─── 3. vitals table ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vitals (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id  UUID NOT NULL REFERENCES patients(id),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    hr          DOUBLE PRECISION,  -- heart rate bpm
    bp_sys      DOUBLE PRECISION,  -- systolic BP mmHg
    bp_dia      DOUBLE PRECISION,  -- diastolic BP mmHg
    spo2        DOUBLE PRECISION,  -- oxygen saturation %
    rr          DOUBLE PRECISION,  -- respiratory rate /min
    hrv         DOUBLE PRECISION,  -- heart rate variability ms
    temp        DOUBLE PRECISION,  -- temperature (optional)
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_vitals_patient_id ON vitals (patient_id);
CREATE INDEX IF NOT EXISTS idx_vitals_recorded_at ON vitals (recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_vitals_patient_time ON vitals (patient_id, recorded_at);

-- ─── 4. medication_administrations table ─────────────────────────────────
CREATE TABLE IF NOT EXISTS medication_administrations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id        UUID NOT NULL REFERENCES patients(id),
    medication_name   VARCHAR(200) NOT NULL,
    medication_type   VARCHAR(100),          -- analgesic, antibiotic, etc.
    dose              VARCHAR(100),
    route             VARCHAR(50),           -- IV, PO, IM
    administered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    administered_by   VARCHAR(200),
    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_med_admin_patient ON medication_administrations (patient_id);
CREATE INDEX IF NOT EXISTS idx_med_admin_type ON medication_administrations (medication_type);

-- ═══════════════════════════════════════════════════════════════════════════
-- SEED: Patient C — Lakshmi Devi (SilentVoice demo patient)
-- ═══════════════════════════════════════════════════════════════════════════

-- Insert patient record
INSERT INTO patients (id, name, age, sex, mrn, bed, ward) VALUES
    ('a1b2c3d4-0003-4000-8000-000000000003',
     'Lakshmi Devi', 72, 'Female', 'MRN-2025-0003', 'ICU-3', 'ICU')
ON CONFLICT (id) DO NOTHING;

-- Active admission (no discharge)
INSERT INTO admissions (id, patient_id, admitted_at, discharged_at, ward, bed, diagnosis) VALUES
    ('f1000000-0003-4000-8000-000000000001',
     'a1b2c3d4-0003-4000-8000-000000000003',
     NOW() - INTERVAL '6 hours',
     NULL,
     'ICU', 'ICU-3',
     'Post-operative hip replacement — Day 2')
ON CONFLICT (id) DO NOTHING;

-- ─── Vitals: Baseline period (first 2 hours — readings every 15 min) ────
-- These form the personal baseline: HR ~72, BP ~128/78, SpO2 ~98, RR ~16, HRV ~52
INSERT INTO vitals (patient_id, recorded_at, hr, bp_sys, bp_dia, spo2, rr, hrv) VALUES
    -- Hour 0:00 to 2:00 — stable baseline (8 readings)
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '360 minutes', 70, 126, 76, 98, 15, 54),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '345 minutes', 72, 128, 78, 98, 16, 52),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '330 minutes', 71, 124, 77, 97, 16, 50),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '315 minutes', 73, 130, 80, 98, 15, 53),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '300 minutes', 72, 128, 78, 98, 17, 51),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '285 minutes', 74, 126, 76, 99, 16, 55),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '270 minutes', 71, 130, 79, 97, 16, 49),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '255 minutes', 73, 128, 78, 98, 15, 52),

    -- Hour 2:00 to 4:00 — still stable, mild normal variation
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '240 minutes', 72, 126, 77, 98, 16, 51),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '225 minutes', 74, 128, 78, 97, 16, 50),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '210 minutes', 73, 130, 79, 98, 17, 48),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '195 minutes', 72, 126, 78, 98, 16, 52),

    -- Hour 4:00 to 5:00 — subtle drift begins (HR starts rising, HRV dropping)
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '120 minutes', 78, 130, 80, 97, 18, 46),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '105 minutes', 82, 132, 82, 97, 19, 42),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '90 minutes',  85, 134, 82, 97, 20, 40),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '75 minutes',  88, 132, 84, 96, 20, 38),

    -- Hour 5:00 to 5:30 — clear distress pattern (HR elevated, HRV tanking)
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '60 minutes',  90, 134, 84, 97, 21, 36),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '45 minutes',  92, 136, 86, 96, 21, 35),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '30 minutes',  93, 136, 84, 97, 22, 34),

    -- Most recent readings — distress active
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '15 minutes',  94, 138, 86, 97, 22, 34),
    ('a1b2c3d4-0003-4000-8000-000000000003', NOW() - INTERVAL '5 minutes',   94, 128, 84, 97, 22, 34);

-- ─── Medication: Last analgesic was ~6.2 hours ago ──────────────────────
INSERT INTO medication_administrations
    (patient_id, medication_name, medication_type, dose, route, administered_at, administered_by) VALUES
    -- Analgesic given at admission — 6+ hours ago
    ('a1b2c3d4-0003-4000-8000-000000000003',
     'Morphine Sulfate', 'analgesic', '4mg', 'IV',
     NOW() - INTERVAL '372 minutes',  -- ~6.2 hours ago
     'Nurse Priya'),
    -- Antibiotic given 3 hours ago (not an analgesic — should NOT reset the clock)
    ('a1b2c3d4-0003-4000-8000-000000000003',
     'Cefazolin', 'antibiotic', '1g', 'IV',
     NOW() - INTERVAL '180 minutes',
     'Nurse Priya'),
    -- Antiemetic given 4 hours ago (not an analgesic)
    ('a1b2c3d4-0003-4000-8000-000000000003',
     'Ondansetron', 'antiemetic', '4mg', 'IV',
     NOW() - INTERVAL '240 minutes',
     'Nurse Priya');

-- ─── Update existing silent_voice_alerts distress_started to match ──────
-- Make sure the alert fires ~35 min ago (matches vitals drift timeline)
UPDATE silent_voice_alerts
SET distress_started = NOW() - INTERVAL '35 minutes',
    distress_duration_minutes = 35
WHERE patient_id = 'a1b2c3d4-0003-4000-8000-000000000003'
  AND acknowledged = false;

-- ═══════════════════════════════════════════════════════════════════════════
-- Also seed other demo patients into the patients table for completeness
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO patients (id, name, age, sex, mrn, bed, ward) VALUES
    ('a1b2c3d4-0001-4000-8000-000000000001', 'Priya Sharma', 34, 'Female', 'MRN-2025-0001', NULL, 'Outpatient'),
    ('a1b2c3d4-0002-4000-8000-000000000002', 'Arjun Nair', 45, 'Male', 'MRN-2025-0002', '4B-2', 'Ward 4B'),
    ('a1b2c3d4-0004-4000-8000-000000000004', 'Rajesh Kumar', 58, 'Male', 'MRN-2025-0004', NULL, 'Outpatient')
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- Verify
SELECT 'patients' AS tbl, count(*) FROM patients
UNION ALL SELECT 'admissions', count(*) FROM admissions
UNION ALL SELECT 'vitals', count(*) FROM vitals
UNION ALL SELECT 'medication_administrations', count(*) FROM medication_administrations;
