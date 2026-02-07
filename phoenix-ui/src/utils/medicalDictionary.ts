/**
 * Medical Terminology Dictionary for Phoenix Guardian.
 *
 * Used by the voice transcription system to identify medical terms
 * in real-time, highlight them for review, and flag potential errors.
 */

/* ─── Vital Signs ─── */
const VITALS = [
  'blood pressure', 'bp', 'systolic', 'diastolic',
  'heart rate', 'hr', 'pulse', 'bpm',
  'respiratory rate', 'rr', 'respirations',
  'temperature', 'temp', 'fever', 'afebrile', 'febrile',
  'oxygen saturation', 'spo2', 'o2 sat', 'pulse ox',
  'weight', 'height', 'bmi',
];

/* ─── Common Conditions ─── */
const CONDITIONS = [
  'hypertension', 'hypotension', 'diabetes', 'diabetic',
  'type 1', 'type 2', 'asthma', 'copd',
  'pneumonia', 'bronchitis', 'influenza', 'covid',
  'heart failure', 'chf', 'congestive',
  'atrial fibrillation', 'afib', 'a-fib',
  'coronary artery disease', 'cad',
  'myocardial infarction', 'mi', 'heart attack',
  'stroke', 'cva', 'tia',
  'depression', 'anxiety', 'bipolar',
  'hypothyroidism', 'hyperthyroidism', 'thyroid',
  'anemia', 'iron deficiency',
  'arthritis', 'osteoarthritis', 'rheumatoid',
  'gerd', 'reflux', 'gastritis',
  'urinary tract infection', 'uti',
  'kidney disease', 'renal failure', 'ckd',
  'liver disease', 'hepatitis', 'cirrhosis',
  'cancer', 'carcinoma', 'tumor', 'malignant', 'benign',
  'sepsis', 'infection', 'cellulitis',
  'dvt', 'deep vein thrombosis', 'pulmonary embolism', 'pe',
  'epilepsy', 'seizure',
  'migraine', 'headache', 'cephalgia',
  'obesity', 'overweight',
  'hyperlipidemia', 'cholesterol', 'dyslipidemia',
  'osteoporosis',
];

/* ─── Top Medications ─── */
const MEDICATIONS = [
  'lisinopril', 'losartan', 'amlodipine', 'metoprolol',
  'atenolol', 'carvedilol', 'valsartan', 'hydrochlorothiazide',
  'metformin', 'glipizide', 'sitagliptin', 'insulin',
  'lantus', 'humalog', 'novolog',
  'atorvastatin', 'rosuvastatin', 'simvastatin', 'pravastatin',
  'omeprazole', 'pantoprazole', 'lansoprazole', 'famotidine',
  'albuterol', 'fluticasone', 'montelukast', 'prednisone',
  'prednisolone', 'dexamethasone',
  'gabapentin', 'pregabalin', 'duloxetine',
  'sertraline', 'fluoxetine', 'escitalopram', 'citalopram',
  'venlafaxine', 'bupropion', 'trazodone', 'amitriptyline',
  'furosemide', 'spironolactone', 'chlorthalidone',
  'warfarin', 'apixaban', 'rivaroxaban', 'eliquis', 'xarelto',
  'aspirin', 'clopidogrel', 'plavix',
  'levothyroxine', 'synthroid',
  'amoxicillin', 'azithromycin', 'ciprofloxacin', 'doxycycline',
  'cephalexin', 'metronidazole', 'clindamycin',
  'ibuprofen', 'acetaminophen', 'naproxen', 'tylenol', 'advil',
  'tramadol', 'oxycodone', 'hydrocodone', 'morphine',
  'alprazolam', 'lorazepam', 'diazepam', 'clonazepam',
  'zolpidem', 'melatonin',
  'cyclobenzaprine', 'methocarbamol',
  'tamsulosin', 'finasteride',
  'montelukast', 'cetirizine', 'loratadine', 'diphenhydramine',
  'ondansetron', 'promethazine', 'metoclopramide',
  'potassium', 'magnesium', 'calcium', 'vitamin d',
];

/* ─── Symptoms ─── */
const SYMPTOMS = [
  'chest pain', 'shortness of breath', 'dyspnea',
  'cough', 'wheezing', 'stridor',
  'fever', 'chills', 'night sweats',
  'headache', 'dizziness', 'vertigo', 'syncope',
  'nausea', 'vomiting', 'diarrhea', 'constipation',
  'abdominal pain', 'epigastric', 'cramping',
  'fatigue', 'malaise', 'weakness', 'lethargy',
  'palpitations', 'tachycardia', 'bradycardia',
  'edema', 'swelling', 'peripheral edema',
  'rash', 'pruritus', 'itching', 'hives', 'urticaria',
  'pain', 'tenderness', 'soreness',
  'numbness', 'tingling', 'paresthesia',
  'blurred vision', 'diplopia',
  'dysuria', 'hematuria', 'polyuria', 'oliguria',
  'dysphagia', 'odynophagia',
  'insomnia', 'somnolence',
  'weight loss', 'weight gain',
  'appetite', 'anorexia',
  'hemoptysis', 'hematemesis', 'melena',
  'arthralgia', 'myalgia',
];

/* ─── Procedures & Tests ─── */
const PROCEDURES = [
  'chest x-ray', 'cxr', 'x-ray', 'xray',
  'ct scan', 'ct', 'cat scan', 'computed tomography',
  'mri', 'magnetic resonance',
  'ultrasound', 'sonogram', 'echocardiogram', 'echo',
  'ekg', 'ecg', 'electrocardiogram',
  'eeg', 'electroencephalogram',
  'blood draw', 'phlebotomy', 'venipuncture',
  'cbc', 'complete blood count',
  'bmp', 'cmp', 'metabolic panel',
  'urinalysis', 'ua', 'urine culture',
  'blood culture',
  'colonoscopy', 'endoscopy', 'egd',
  'biopsy', 'pathology',
  'spirometry', 'pulmonary function',
  'stress test', 'treadmill test',
  'catheterization', 'angiogram',
  'dialysis', 'transfusion',
  'intubation', 'ventilator',
  'lumbar puncture', 'spinal tap',
  'a1c', 'hemoglobin a1c', 'hba1c',
  'tsh', 'thyroid panel', 't3', 't4',
  'lipid panel', 'ldl', 'hdl', 'triglycerides',
  'pt', 'inr', 'ptt', 'coagulation',
  'bnp', 'troponin', 'd-dimer',
  'creatinine', 'bun', 'gfr', 'egfr',
  'liver function', 'lfts', 'ast', 'alt', 'bilirubin',
];

/* ─── Anatomy ─── */
const ANATOMY = [
  'heart', 'lungs', 'liver', 'kidneys', 'brain', 'spleen',
  'pancreas', 'gallbladder', 'bladder', 'colon', 'rectum',
  'stomach', 'esophagus', 'intestine', 'bowel',
  'chest', 'abdomen', 'pelvis', 'thorax',
  'extremities', 'upper extremity', 'lower extremity',
  'spine', 'cervical', 'thoracic', 'lumbar', 'sacral',
  'cardiovascular', 'respiratory', 'gastrointestinal',
  'musculoskeletal', 'neurological', 'genitourinary',
  'integumentary', 'endocrine', 'hematologic',
  'bilateral', 'unilateral', 'proximal', 'distal',
  'anterior', 'posterior', 'lateral', 'medial',
  'supine', 'prone',
];

/* ─── Physical Exam ─── */
const EXAM_TERMS = [
  'inspection', 'palpation', 'percussion', 'auscultation',
  'normal', 'abnormal', 'unremarkable',
  'clear to auscultation', 'cta', 'bilaterally',
  'regular rate and rhythm', 'rrr',
  'no murmurs', 'murmur', 'gallop', 'rub',
  'soft', 'non-tender', 'non-distended',
  'bowel sounds', 'normoactive', 'hypoactive', 'hyperactive',
  'alert', 'oriented', 'oriented x3',
  'cranial nerves intact', 'cn ii-xii',
  'no focal deficits',
  'range of motion', 'rom',
  'erythema', 'induration', 'crepitus',
  'point tenderness', 'rebound', 'guarding',
  'jvd', 'jugular venous distension',
];

/* ─── Clinical Abbreviations ─── */
const ABBREVIATIONS = [
  'prn', 'bid', 'tid', 'qid', 'qd', 'qhs',
  'po', 'iv', 'im', 'sq', 'subq',
  'mg', 'ml', 'mcg', 'units',
  'stat', 'asap',
  'npo', 'nkda', 'nka',
  'hpi', 'ros', 'pmh', 'psh', 'fh', 'sh',
  'a&p', 'soap',
  'wbc', 'rbc', 'plt', 'hgb', 'hct',
  'er', 'ed', 'icu', 'or',
  'f/u', 'follow-up', 'follow up',
  'w/u', 'work-up', 'workup',
  'r/o', 'rule out',
  'dx', 'ddx', 'tx', 'rx', 'sx', 'hx',
];

/* ═══ Build the master Set ═══ */

function buildTermsSet(): Set<string> {
  const allTerms = [
    ...VITALS,
    ...CONDITIONS,
    ...MEDICATIONS,
    ...SYMPTOMS,
    ...PROCEDURES,
    ...ANATOMY,
    ...EXAM_TERMS,
    ...ABBREVIATIONS,
  ];

  const set = new Set<string>();
  for (const term of allTerms) {
    // Add full term
    set.add(term.toLowerCase());
    // Also add individual words from multi-word terms
    for (const word of term.toLowerCase().split(/\s+/)) {
      if (word.length > 2) {
        set.add(word);
      }
    }
  }
  return set;
}

/** Master set of all medical terms (lowercased). */
export const MEDICAL_TERMS_SET: Set<string> = buildTermsSet();

/** Flat array of all terms for autocomplete / matching. */
export const MEDICAL_TERMS_LIST: string[] = [
  ...VITALS,
  ...CONDITIONS,
  ...MEDICATIONS,
  ...SYMPTOMS,
  ...PROCEDURES,
  ...ANATOMY,
  ...EXAM_TERMS,
  ...ABBREVIATIONS,
].map(t => t.toLowerCase());

/** Check if a word is a known medical term. */
export function isMedicalTerm(word: string): boolean {
  return MEDICAL_TERMS_SET.has(word.toLowerCase().replace(/[^a-z0-9-]/g, ''));
}

/** Find medical terms in a block of text. Returns unique terms found. */
export function findMedicalTerms(text: string): string[] {
  const lower = text.toLowerCase();
  const found = new Set<string>();

  // Check multi-word terms first (longer phrases)
  const allMultiWord = [
    ...VITALS, ...CONDITIONS, ...MEDICATIONS,
    ...SYMPTOMS, ...PROCEDURES, ...ANATOMY,
    ...EXAM_TERMS,
  ].filter(t => t.includes(' '));

  for (const term of allMultiWord) {
    if (lower.includes(term.toLowerCase())) {
      found.add(term.toLowerCase());
    }
  }

  // Check individual words
  const words = lower.split(/\s+/);
  for (const w of words) {
    const clean = w.replace(/[^a-z0-9-]/g, '');
    if (clean.length > 2 && MEDICAL_TERMS_SET.has(clean)) {
      found.add(clean);
    }
  }

  return Array.from(found);
}

/** Get autocomplete suggestions for a partial medical term. */
export function getMedicalSuggestions(partial: string, limit = 10): string[] {
  if (partial.length < 2) return [];
  const lower = partial.toLowerCase();
  return MEDICAL_TERMS_LIST
    .filter(t => t.startsWith(lower) || t.includes(lower))
    .slice(0, limit);
}

/** Categorised export for the backend verification endpoint. */
export const MEDICAL_VOCABULARY = {
  vitals: VITALS,
  conditions: CONDITIONS,
  medications: MEDICATIONS,
  symptoms: SYMPTOMS,
  procedures: PROCEDURES,
  anatomy: ANATOMY,
  examTerms: EXAM_TERMS,
  abbreviations: ABBREVIATIONS,
};
