-- ============================================================
-- Phoenix Guardian V5 Migration
-- Adds tables for: ZebraHunterAgent, SilentVoiceAgent,
-- TreatmentShadowAgent
-- Created: February 2026
-- Safe to run multiple times (uses IF NOT EXISTS)
-- ============================================================

BEGIN;

-- ============================================================
-- ZEBRA HUNTER AGENT TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS zebra_analyses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID NOT NULL,
    analyzed_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status              VARCHAR(20) NOT NULL
                        CHECK (status IN ('zebra_found','ghost_protocol','watching','clear')),
    symptoms_found      JSONB DEFAULT '[]',
    top_disease         VARCHAR(500),
    top_disease_code    VARCHAR(50),
    confidence_score    FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 100),
    years_lost          FLOAT DEFAULT 0,
    total_visits        INTEGER DEFAULT 0,
    recommendation      TEXT,
    full_result         JSONB,
    created_by          VARCHAR(100),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zebra_analyses_patient_id
    ON zebra_analyses(patient_id);
CREATE INDEX IF NOT EXISTS idx_zebra_analyses_status
    ON zebra_analyses(status);
CREATE INDEX IF NOT EXISTS idx_zebra_analyses_created_at
    ON zebra_analyses(created_at DESC);

-- Missed clue timeline — one row per visit per analysis
CREATE TABLE IF NOT EXISTS zebra_missed_clues (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id         UUID NOT NULL REFERENCES zebra_analyses(id) ON DELETE CASCADE,
    patient_id          UUID NOT NULL,
    visit_number        INTEGER NOT NULL,
    visit_date          DATE,
    diagnosis_given     VARCHAR(255),
    was_diagnosable     BOOLEAN DEFAULT FALSE,
    missed_clues        JSONB DEFAULT '[]',
    confidence          FLOAT DEFAULT 0,
    reason              TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zebra_missed_clues_analysis_id
    ON zebra_missed_clues(analysis_id);
CREATE INDEX IF NOT EXISTS idx_zebra_missed_clues_patient_id
    ON zebra_missed_clues(patient_id);

-- Ghost Protocol — tracks unknown symptom clusters across patients
CREATE TABLE IF NOT EXISTS ghost_cases (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ghost_id            VARCHAR(50) UNIQUE NOT NULL,
    symptom_hash        VARCHAR(255) NOT NULL,
    symptom_signature   JSONB NOT NULL DEFAULT '[]',
    patient_count       INTEGER DEFAULT 1,
    patient_ids         JSONB DEFAULT '[]',
    status              VARCHAR(20) DEFAULT 'watching'
                        CHECK (status IN ('watching','alert_fired','reported','closed')),
    alert_fired_at      TIMESTAMP WITH TIME ZONE,
    reported_to         VARCHAR(100),
    first_seen          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_ghost_cases_symptom_hash
    ON ghost_cases(symptom_hash);
CREATE INDEX IF NOT EXISTS idx_ghost_cases_status
    ON ghost_cases(status);

-- ============================================================
-- SILENT VOICE AGENT TABLES
-- ============================================================

-- Personal vital baselines per patient
CREATE TABLE IF NOT EXISTS patient_baselines (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID NOT NULL UNIQUE,
    established_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    baseline_window_min INTEGER DEFAULT 120,
    vitals_count        INTEGER DEFAULT 0,

    -- Heart Rate
    hr_mean             FLOAT,
    hr_std              FLOAT DEFAULT 1.0,
    hr_min              FLOAT,
    hr_max              FLOAT,

    -- Blood Pressure Systolic
    bp_sys_mean         FLOAT,
    bp_sys_std          FLOAT DEFAULT 1.0,

    -- Blood Pressure Diastolic
    bp_dia_mean         FLOAT,
    bp_dia_std          FLOAT DEFAULT 1.0,

    -- SpO2
    spo2_mean           FLOAT,
    spo2_std            FLOAT DEFAULT 0.5,

    -- Respiratory Rate
    rr_mean             FLOAT,
    rr_std              FLOAT DEFAULT 1.0,

    -- Heart Rate Variability
    hrv_mean            FLOAT,
    hrv_std             FLOAT DEFAULT 1.0,

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_patient_baselines_patient_id
    ON patient_baselines(patient_id);

-- SilentVoice alerts — one row per alert fired
CREATE TABLE IF NOT EXISTS silent_voice_alerts (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id                  UUID NOT NULL,
    alert_level                 VARCHAR(20) NOT NULL
                                CHECK (alert_level IN ('critical','warning','clear')),
    distress_started            TIMESTAMP WITH TIME ZONE,
    distress_duration_minutes   INTEGER DEFAULT 0,
    signals_detected            JSONB DEFAULT '[]',
    latest_vitals               JSONB,
    last_analgesic_hours        FLOAT,
    clinical_output             TEXT,
    recommended_action          TEXT,
    acknowledged                BOOLEAN DEFAULT FALSE,
    acknowledged_by             VARCHAR(100),
    acknowledged_at             TIMESTAMP WITH TIME ZONE,
    created_at                  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_silent_voice_alerts_patient_id
    ON silent_voice_alerts(patient_id);
CREATE INDEX IF NOT EXISTS idx_silent_voice_alerts_alert_level
    ON silent_voice_alerts(alert_level);
CREATE INDEX IF NOT EXISTS idx_silent_voice_alerts_acknowledged
    ON silent_voice_alerts(acknowledged);
CREATE INDEX IF NOT EXISTS idx_silent_voice_alerts_created_at
    ON silent_voice_alerts(created_at DESC);

-- ============================================================
-- TREATMENT SHADOW AGENT TABLES
-- ============================================================

-- Active shadows per patient-drug combination
CREATE TABLE IF NOT EXISTS treatment_shadows (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id              UUID NOT NULL,
    drug_name               VARCHAR(255) NOT NULL,
    drug_name_normalized    VARCHAR(255),
    shadow_type             VARCHAR(255) NOT NULL,
    watch_lab               VARCHAR(100),
    watch_started           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    watch_window_months     INTEGER DEFAULT 6,

    -- Alert status
    alert_fired             BOOLEAN DEFAULT FALSE,
    alert_fired_at          TIMESTAMP WITH TIME ZONE,
    severity                VARCHAR(20) DEFAULT 'watching'
                            CHECK (severity IN ('watching','mild','moderate',
                                               'critical','resolved')),

    -- Trend data
    lab_values              JSONB DEFAULT '[]',
    lab_dates               JSONB DEFAULT '[]',
    trend_slope             FLOAT,
    trend_pct_change        FLOAT,
    trend_direction         VARCHAR(20),
    trend_r_squared         FLOAT,

    -- Clinical output
    clinical_output         TEXT,
    harm_started_estimate   VARCHAR(100),
    current_stage           TEXT,
    projection_90_days      TEXT,
    recommended_action      TEXT,

    -- Metadata
    prescribed_since        DATE,
    dismissed               BOOLEAN DEFAULT FALSE,
    dismissed_by            VARCHAR(100),
    dismissed_at            TIMESTAMP WITH TIME ZONE,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(patient_id, drug_name_normalized, shadow_type)
);

CREATE INDEX IF NOT EXISTS idx_treatment_shadows_patient_id
    ON treatment_shadows(patient_id);
CREATE INDEX IF NOT EXISTS idx_treatment_shadows_alert_fired
    ON treatment_shadows(alert_fired);
CREATE INDEX IF NOT EXISTS idx_treatment_shadows_severity
    ON treatment_shadows(severity);

COMMIT;

-- ============================================================
-- ROLLBACK (run only if you need to undo this migration)
-- Uncomment and run manually if needed
-- ============================================================
-- BEGIN;
-- DROP TABLE IF EXISTS treatment_shadows;
-- DROP TABLE IF EXISTS silent_voice_alerts;
-- DROP TABLE IF EXISTS patient_baselines;
-- DROP TABLE IF EXISTS ghost_cases;
-- DROP TABLE IF EXISTS zebra_missed_clues;
-- DROP TABLE IF EXISTS zebra_analyses;
-- COMMIT;
