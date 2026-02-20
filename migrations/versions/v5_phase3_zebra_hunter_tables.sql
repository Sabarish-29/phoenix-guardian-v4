-- =====================================================================
-- V5 Phase 3: ZebraHunter — patient_visits table + seed data
-- Run: psql -U postgres -d phoenix_guardian -f migrations/versions/v5_phase3_zebra_hunter_tables.sql
-- =====================================================================

-- Patient visits table: stores visit history with SOAP notes for ZebraHunter analysis
CREATE TABLE IF NOT EXISTS patient_visits (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id),
    visit_number    INTEGER NOT NULL,
    visit_date      DATE NOT NULL,
    diagnosis       VARCHAR(255),
    soap_note       TEXT,
    provider_name   VARCHAR(200),
    department      VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_patient_visits_patient_id ON patient_visits(patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_visits_visit_date ON patient_visits(patient_id, visit_date);

-- =====================================================================
-- Seed: Patient A — Priya Sharma (6 visits over 3.5 years)
-- Classic EDS presentation: fatigue, joint hypermobility, brain fog,
-- GI issues, chronic pain — each visit gets a different wrong diagnosis
-- =====================================================================

INSERT INTO patient_visits (patient_id, visit_number, visit_date, diagnosis, soap_note, provider_name, department)
VALUES
-- Visit 1 — Jan 2022
('a1b2c3d4-0001-4000-8000-000000000001', 1, '2022-01-15', 'Stress / Work-related fatigue',
 'S: 28-year-old female presents with persistent fatigue lasting 3 months, reports difficulty concentrating at work. Notes occasional joint pain in fingers and wrists, especially in the morning. States she feels "loose" in her joints. Denies trauma.
O: Vitals normal. BMI 22. Skin appears mildly translucent. Joint examination shows hypermobility in fingers — Beighton score not formally assessed. Mild tenderness at wrists bilaterally.
A: Most likely work-related stress and fatigue. Possible early repetitive strain injury.
P: Advised stress management techniques, ergonomic workstation review. Follow up in 3 months if symptoms persist. Consider B12 and thyroid panel if fatigue continues.',
 'Dr. Rao', 'General Medicine'),

-- Visit 2 — Aug 2022
('a1b2c3d4-0001-4000-8000-000000000001', 2, '2022-08-20', 'Irritable Bowel Syndrome (IBS)',
 'S: Returns with ongoing fatigue (now 9 months). New complaint of frequent abdominal bloating and alternating constipation/diarrhea for 2 months. Joint pain persists in fingers, knees, and shoulders. Reports episodes of brain fog — difficulty finding words, forgetting tasks. States joints sometimes "pop" or "click" audibly.
O: Vitals stable. Abdomen soft, mildly distended, diffuse tenderness. No guarding. Joint exam: hypermobility noted in fingers and thumbs bilaterally, mild hyperextension at elbows. Skin soft, velvety texture noted.
A: Irritable bowel syndrome — mixed type. Fatigue likely secondary. Joint complaints not alarming at this stage.
P: Low FODMAP diet trial for 6 weeks. Probiotics recommended. Reassurance regarding joint clicking — likely benign hypermobility. Follow up in 3 months.',
 'Dr. Mehta', 'Gastroenterology'),

-- Visit 3 — Mar 2023
('a1b2c3d4-0001-4000-8000-000000000001', 3, '2023-03-10', 'Generalized Anxiety Disorder',
 'S: Fatigue worsening (now 14 months). Brain fog is now constant — reports feeling "cognitively impaired." GI symptoms persist despite low FODMAP diet. New symptom: dizziness upon standing, feels lightheaded when getting out of bed. Joint pain has spread to hips and lower back. Reports that her skin bruises very easily and wounds heal slowly. Emotional distress about not getting answers.
O: Vitals: BP 112/68 sitting, 98/62 standing (orthostatic drop noted). HR 72 sitting, 94 standing. Skin shows multiple ecchymoses on arms and legs at various stages. Joint exam: generalized hypermobility, Beighton score estimated 6/9. Skin hyperextensibility observed.
A: Anxiety with somatic features. Orthostatic hypotension — likely dehydration. Bruising attributed to iron deficiency.
P: Referred to psychiatry for anxiety management. Iron studies ordered. Increase fluid and salt intake. Follow up in 2 months.',
 'Dr. Iyer', 'Internal Medicine'),

-- Visit 4 — Sep 2023
('a1b2c3d4-0001-4000-8000-000000000001', 4, '2023-09-22', 'Chronic Pain Syndrome',
 'S: All symptoms persist. Now experiencing daily headaches, described as pressure at the base of skull. Joint subluxations — reports shoulder "slipped out" while lifting grocery bags, self-reduced. Fatigue is debilitating. Orthostatic intolerance continues — cannot stand for more than 15 minutes without feeling faint. GI symptoms unchanged. Brain fog severe — has been placed on medical leave from work.
O: Vitals: orthostatic changes confirmed. Musculoskeletal: generalized joint hypermobility, positive Beighton 7/9. Shoulder exam shows mild instability. Cervical spine mildly tender. Skin: soft, translucent, multiple ecchymoses. Prior iron studies normal.
A: Chronic pain syndrome. Possible fibromyalgia. Headaches likely tension-type.
P: Referral to pain management. Trial of amitriptyline 10mg nightly. Physical therapy referral for joint stability. Follow up in 6 weeks.',
 'Dr. Patel', 'Pain Management'),

-- Visit 5 — Feb 2024
('a1b2c3d4-0001-4000-8000-000000000001', 5, '2024-02-14', 'Fibromyalgia',
 'S: Minimal improvement with amitriptyline. Pain is now widespread — tender points positive. Fatigue unchanged. GI symptoms chronic. Orthostatic intolerance interferes with daily living. Joint instability continues — knee gave out on stairs last week. Reports new symptom: dental crowding and high palate noted by dentist. Easy bruising persists. Severe brain fog and depression about diagnostic odyssey.
O: Vitals: orthostatic changes still present. Beighton score 7/9 confirmed. Widespread tender points (14/18 positive). Skin: hyperextensible, velvety. Dental exam notes high-arched palate. Multiple joint subluxation history documented.
A: Fibromyalgia with chronic fatigue syndrome overlap. High-arched palate incidental.
P: Duloxetine 30mg trial. Continue PT. Sleep hygiene counseling. Support group referral.',
 'Dr. Kapoor', 'Rheumatology'),

-- Visit 6 — TODAY (Phoenix Guardian analysis)
('a1b2c3d4-0001-4000-8000-000000000001', 6, '2026-02-19', 'PENDING — Phoenix Guardian Analysis',
 'S: Patient presents for routine follow-up. All previous symptoms persist: chronic fatigue, widespread joint pain with hypermobility, GI dysfunction, orthostatic intolerance, brain fog, easy bruising, slow wound healing, joint subluxations, high-arched palate. Has been to 5 different specialists over 4 years. No unifying diagnosis.
O: Comprehensive review of all prior visits loaded into Phoenix Guardian system. Beighton score 7/9. Orthostatic vitals confirmed. Skin hyperextensibility and translucency documented. Full symptom timeline available.
A: Phoenix Guardian ZebraHunter analysis initiated.
P: Awaiting ZebraHunter rare disease screening results.',
 'Dr. Phoenix Guardian AI', 'AI-Assisted Diagnostics');

-- =====================================================================
-- Seed: Patient B — Arjun Nair (4 visits with unusual symptom cluster)
-- No known rare disease matches → triggers Ghost Protocol
-- =====================================================================

INSERT INTO patient_visits (patient_id, visit_number, visit_date, diagnosis, soap_note, provider_name, department)
VALUES
-- Visit 1 — May 2024
('a1b2c3d4-0002-4000-8000-000000000002', 1, '2024-05-10', 'Rosacea',
 'S: 35-year-old male presents with episodic facial flushing lasting 20-30 minutes, occurring 3-4 times weekly for 2 months. No clear triggers identified — happens at rest, during exercise, and during sleep. Denies alcohol or spicy food correlation. Also notes increased bruising on arms and torso without trauma.
O: Vitals: BP 148/92 (elevated). Skin exam: mild periorbital erythema during visit, no papules or pustules. Multiple ecchymoses on bilateral upper extremities (3-5cm, various stages of healing). No petechiae.
A: Probable rosacea — erythematotelangiectatic subtype. Bruising likely incidental.
P: Trial of topical metronidazole. BP recheck in 2 weeks — possible white coat effect.',
 'Dr. Reddy', 'Dermatology'),

-- Visit 2 — Aug 2024
('a1b2c3d4-0002-4000-8000-000000000002', 2, '2024-08-15', 'Essential Hypertension',
 'S: Flushing episodes continue despite topical treatment. Bruising has worsened — now spontaneous bruising on torso and legs. BP consistently elevated at home (145-155/90-95). New complaint: joints feel "loose," particularly in thumbs and wrists. Reports thumb can bend backwards to touch forearm.
O: Vitals: BP 152/94. Skin: spontaneous bruising noted — 8 ecchymoses in various locations. Joint exam: hypermobility in thumbs bilaterally, wrists hyperextend beyond normal range. Beighton elements present but not formally scored. Flushing episode witnessed during exam — face, neck, upper chest.
A: Essential hypertension. Spontaneous bruising — platelet studies ordered. Flushing likely vasomotor.
P: Amlodipine 5mg started for BP. CBC, platelet function, coagulation panel ordered.',
 'Dr. Shah', 'Internal Medicine'),

-- Visit 3 — Nov 2024
('a1b2c3d4-0002-4000-8000-000000000002', 3, '2024-11-08', 'Unexplained Bruising — Investigation',
 'S: All symptoms persist. Platelet count and coagulation studies returned normal. BP improved on amlodipine (135/88) but still above goal. Spontaneous bruising continues — now documenting with photos, occurring every 2-3 days. Flushing episodes now include chest tightness. Joint laxity unchanged. New: episodes of unexplained sweating, predominantly at night.
O: Vitals: BP 138/86. Extensive bruising documented. Joint hypermobility confirmed. During exam, patient demonstrated thumb-to-forearm flexibility. Flushing episode with mild diaphoresis observed. All coagulation studies normal. CBC normal. ESR and CRP normal.
A: Unexplained spontaneous bruising with normal coagulation profile. Episodic flushing of unclear etiology. Joint hypermobility — benign. Unexplained hypertension in a 35-year-old.
P: Referral to hematology. 24-hour urine catecholamines to rule out pheochromocytoma. Tryptase level to evaluate for mastocytosis.',
 'Dr. Gupta', 'Hematology'),

-- Visit 4 — Feb 2025
('a1b2c3d4-0002-4000-8000-000000000002', 4, '2025-02-20', 'Undiagnosed — Multisystem Presentation',
 'S: Catecholamine studies normal — pheochromocytoma ruled out. Tryptase level borderline but inconclusive for mastocytosis. All symptoms continue: episodic facial flushing, spontaneous bruising, unexplained hypertension despite treatment, joint laxity. Night sweats persist. New symptom: intermittent numbness and tingling in fingertips, worse during flushing episodes. Patient frustrated with lack of diagnosis.
O: Vitals: BP 140/88. Comprehensive exam: episodic flushing (witnessed), spontaneous ecchymoses (documented), joint hypermobility (confirmed), hypertension (documented), peripheral paresthesias (reported). All standard workup negative. This constellation does not fit any single recognized diagnosis.
A: Undiagnosed multisystem presentation. Symptom constellation: episodic flushing + spontaneous bruising + unexplained hypertension + joint laxity + paresthesias. No known syndrome matches this exact profile.
P: Genetic testing panel ordered. Consideration for NIH Undiagnosed Diseases Program referral. Phoenix Guardian AI analysis requested.',
 'Dr. Nair (no relation)', 'Medical Genetics');
