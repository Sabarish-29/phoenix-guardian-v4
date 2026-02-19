-- =============================================================================
-- Phoenix Guardian V5 — Demo Patient Seed Data
-- =============================================================================
-- Seeds 4 demo patients that exercise each new V5 agent:
--   1) Priya Sharma   → ZebraHunterAgent  (rare disease candidate)
--   2) Arjun Nair     → Ghost Protocol    (cluster detection)
--   3) Lakshmi Devi   → SilentVoiceAgent  (ICU vitals, pain distress)
--   4) Rajesh Kumar   → TreatmentShadow   (metformin side-effect watch)
--
-- Safe to re-run: uses ON CONFLICT DO NOTHING where possible.
-- Requires: V5 migration tables already created.
--
-- Usage:
--   psql -U postgres -d phoenix_guardian -f data/mock/v5_demo_patients_seed.sql
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Fixed UUIDs for reproducible demo data
-- ---------------------------------------------------------------------------
-- Patient UUIDs
-- Priya Sharma  : a1b2c3d4-0001-4000-8000-000000000001
-- Arjun Nair    : a1b2c3d4-0002-4000-8000-000000000002
-- Lakshmi Devi  : a1b2c3d4-0003-4000-8000-000000000003
-- Rajesh Kumar  : a1b2c3d4-0004-4000-8000-000000000004

-- Analysis / record UUIDs
-- zebra analysis  : b1000000-0001-4000-8000-000000000001
-- zebra clue #1   : b2000000-0001-4000-8000-000000000001
-- zebra clue #2   : b2000000-0002-4000-8000-000000000002
-- ghost case      : c1000000-0001-4000-8000-000000000001
-- patient baseline: d1000000-0001-4000-8000-000000000001
-- silent alert    : d2000000-0001-4000-8000-000000000001
-- treatment shadow: e1000000-0001-4000-8000-000000000001


-- ═══════════════════════════════════════════════════════════════════════════
-- 1. PRIYA SHARMA — ZebraHunterAgent
--    Scenario: 7 ER visits over 3 years, joint pain + rash + fatigue
--    Suspected rare disease: Ehlers-Danlos syndrome (ORPHA:287)
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO zebra_analyses (
    id, patient_id, status, symptoms_found, top_disease, top_disease_code,
    confidence_score, years_lost, total_visits, recommendation,
    full_result, created_by
) VALUES (
    'b1000000-0001-4000-8000-000000000001',
    'a1b2c3d4-0001-4000-8000-000000000001',
    'zebra_found',
    '["chronic joint hypermobility", "recurrent skin fragility", "easy bruising", "chronic fatigue", "GI dysmotility"]'::jsonb,
    'Ehlers-Danlos syndrome, hypermobility type',
    'ORPHA:287',
    0.82,
    3.2,
    7,
    'Refer to genetics clinic for formal Beighton scoring and genetic panel. Consider echocardiogram to rule out vascular subtype.',
    '{"differential": [
        {"disease": "Ehlers-Danlos syndrome, hypermobility type", "code": "ORPHA:287", "confidence": 0.82},
        {"disease": "Marfan syndrome", "code": "ORPHA:558", "confidence": 0.31},
        {"disease": "Fibromyalgia", "code": null, "confidence": 0.25}
    ], "symptom_overlap_pct": 0.78}'::jsonb,
    'demo_seed'
) ON CONFLICT (id) DO NOTHING;

-- Missed clue visit #3: joint pain dismissed as "anxiety"
INSERT INTO zebra_missed_clues (
    id, analysis_id, patient_id, visit_number, visit_date,
    diagnosis_given, was_diagnosable, missed_clues, confidence, reason
) VALUES (
    'b2000000-0001-4000-8000-000000000001',
    'b1000000-0001-4000-8000-000000000001',
    'a1b2c3d4-0001-4000-8000-000000000001',
    3,
    '2024-03-15',
    'Generalized anxiety disorder',
    true,
    '["joint hypermobility noted but not investigated", "skin elasticity abnormal on exam"]'::jsonb,
    0.72,
    'Beighton score >= 5 at this visit; joint laxity attributed to anxiety-related somatization.'
) ON CONFLICT (id) DO NOTHING;

-- Missed clue visit #5: bruising dismissed as "clumsy"
INSERT INTO zebra_missed_clues (
    id, analysis_id, patient_id, visit_number, visit_date,
    diagnosis_given, was_diagnosable, missed_clues, confidence, reason
) VALUES (
    'b2000000-0002-4000-8000-000000000002',
    'b1000000-0001-4000-8000-000000000001',
    'a1b2c3d4-0001-4000-8000-000000000001',
    5,
    '2024-09-22',
    'Contusion, unspecified',
    true,
    '["extensive bruising disproportionate to reported trauma", "family history of hypermobility not explored"]'::jsonb,
    0.65,
    'Bruising pattern consistent with connective tissue disorder. No coag panel was ordered.'
) ON CONFLICT (id) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════════
-- 2. ARJUN NAIR — Ghost Protocol
--    Scenario: Cluster of 3 patients in same ward with identical GI symptoms
--    within 48 hours → possible undetected norovirus outbreak.
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO ghost_cases (
    id, ghost_id, symptom_hash, symptom_signature, patient_count,
    patient_ids, status, notes
) VALUES (
    'c1000000-0001-4000-8000-000000000001',
    'GHOST-2025-0042',
    'sha256:ab3f91c7d2e8',
    '["acute watery diarrhea", "nausea", "low-grade fever 37.9C", "abdominal cramping"]'::jsonb,
    3,
    '["a1b2c3d4-0002-4000-8000-000000000002", "a1b2c3d4-ffff-4000-8000-000000000010", "a1b2c3d4-ffff-4000-8000-000000000011"]'::jsonb,
    'alert_fired',
    'Three patients in Ward 4B presented within 48h with near-identical GI symptoms. Environmental services notified. Stool samples pending norovirus PCR.'
) ON CONFLICT (id) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════════
-- 3. LAKSHMI DEVI — SilentVoiceAgent
--    Scenario: Post-op hip replacement, ICU day 2. Vitals show subtle
--    distress pattern (rising HR, dropping SpO2) despite patient not
--    pressing call button. Agent detects possible unreported pain.
-- ═══════════════════════════════════════════════════════════════════════════

-- Baseline vitals established over first 120 min of ICU stay
INSERT INTO patient_baselines (
    id, patient_id, baseline_window_min, vitals_count,
    hr_mean, hr_std, hr_min, hr_max,
    bp_sys_mean, bp_sys_std, bp_dia_mean, bp_dia_std,
    spo2_mean, spo2_std,
    rr_mean, rr_std,
    hrv_mean, hrv_std
) VALUES (
    'd1000000-0001-4000-8000-000000000001',
    'a1b2c3d4-0003-4000-8000-000000000003',
    120,
    48,
    72.5, 4.2, 64.0, 82.0,          -- HR baseline
    128.0, 6.5, 78.0, 4.1,          -- BP baseline
    97.8, 0.6,                       -- SpO2 baseline
    16.0, 1.8,                       -- RR baseline
    45.0, 5.2                        -- HRV baseline
) ON CONFLICT (id) DO NOTHING;

-- Silent voice alert triggered at ICU hour 26
INSERT INTO silent_voice_alerts (
    id, patient_id, alert_level, distress_started,
    distress_duration_minutes, signals_detected, latest_vitals,
    last_analgesic_hours, clinical_output, recommended_action,
    acknowledged
) VALUES (
    'd2000000-0001-4000-8000-000000000001',
    'a1b2c3d4-0003-4000-8000-000000000003',
    'warning',
    NOW() - INTERVAL '35 minutes',
    35,
    '["HR z-score +2.4 (sustained 15 min)", "SpO2 z-score -1.9", "RR z-score +1.7", "HRV z-score -2.1", "no call-button press in 4h"]'::jsonb,
    '{"hr": 94, "bp_sys": 142, "bp_dia": 88, "spo2": 94.2, "rr": 22, "hrv": 28, "timestamp": "2025-02-19T14:35:00Z"}'::jsonb,
    6.5,
    'Patient Lakshmi Devi (ICU bed 12) shows a sustained distress pattern: elevated heart rate (z=+2.4), dropping oxygen saturation (z=-1.9), and reduced heart rate variability (z=-2.1). Last analgesic was administered 6.5 hours ago. Patient has NOT pressed call button. Recommend bedside pain assessment.',
    'Perform in-person pain assessment using Wong-Baker FACES scale. Consider PRN analgesic if pain confirmed. Check surgical site for signs of complication.',
    false
) ON CONFLICT (id) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════════
-- 4. RAJESH KUMAR — TreatmentShadowAgent
--    Scenario: On metformin 1000mg BID for 18 months. Labs show a slow,
--    steady decline in vitamin B12 — classic metformin side effect that
--    often goes unmonitored until neuropathy appears.
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO treatment_shadows (
    id, patient_id, drug_name, drug_name_normalized, shadow_type,
    watch_lab, watch_window_months,
    alert_fired, severity,
    lab_values, lab_dates,
    trend_slope, trend_pct_change, trend_direction, trend_r_squared,
    clinical_output,
    harm_started_estimate, current_stage, projection_90_days,
    recommended_action, prescribed_since
) VALUES (
    'e1000000-0001-4000-8000-000000000001',
    'a1b2c3d4-0004-4000-8000-000000000004',
    'Metformin 1000mg BID',
    'metformin',
    'Vitamin B12 Depletion',
    'vitamin_b12',
    18,
    true,
    'moderate',
    '[620, 540, 480, 410, 350, 310]'::jsonb,
    '["2023-08-15", "2023-11-20", "2024-02-14", "2024-06-10", "2024-10-05", "2025-01-18"]'::jsonb,
    -18.7,
    -50.0,
    'declining',
    0.97,
    'Patient Rajesh Kumar has been on Metformin 1000mg BID since August 2023. Vitamin B12 has declined from 620 pg/mL to 310 pg/mL (−50%) over 18 months with a strong linear trend (R²=0.97). Current level is below the 400 pg/mL threshold. Risk of peripheral neuropathy increases if B12 falls below 200 pg/mL.',
    '~6 months ago (approx. June 2024)',
    'Sub-clinical deficiency (B12 < 400 pg/mL). No neuropathy symptoms yet.',
    'At current trajectory, B12 projected to reach ~230 pg/mL in 90 days — approaching symptomatic deficiency.',
    'Order stat B12 level. Start B12 1000mcg PO daily or 1000mcg IM monthly. Recheck in 3 months. Consider methylmalonic acid level to assess tissue-level deficiency.',
    '2023-08-01'
) ON CONFLICT (id) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════════
-- Verification query
-- ═══════════════════════════════════════════════════════════════════════════

-- Uncomment to verify after running:
-- SELECT 'zebra_analyses' AS tbl, count(*) FROM zebra_analyses
-- UNION ALL SELECT 'zebra_missed_clues', count(*) FROM zebra_missed_clues
-- UNION ALL SELECT 'ghost_cases', count(*) FROM ghost_cases
-- UNION ALL SELECT 'patient_baselines', count(*) FROM patient_baselines
-- UNION ALL SELECT 'silent_voice_alerts', count(*) FROM silent_voice_alerts
-- UNION ALL SELECT 'treatment_shadows', count(*) FROM treatment_shadows;

COMMIT;

-- Done. Run validate_phase0.py to confirm everything is wired up.
