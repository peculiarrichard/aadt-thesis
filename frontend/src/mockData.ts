import type { MockCase, ReviewQueueItem } from './types'

// Stand-ins for the service layer (task 10, not wired over HTTP -- task 11).
// Cases are drawn from backend/src/backend/fixtures/synthetic_cases.yaml.
export const MOCK_CASES: MockCase[] = [
  {
    input: {
      caseId: 'SC-001',
      label: 'SC-001 -- fever and RDT-positive malaria',
      presentingComplaint:
        'A 27-year-old man presents with fever, chills, and headache for two days.',
      history:
        'No prior chronic illness. No recent travel. No cough, no dysuria, no neck stiffness.',
      examinationFindings:
        'Temperature 38.6C. Conscious and alert, no pallor, no jaundice, no neck stiffness. RDT positive for malaria.',
    },
    result: {
      disposition: 'manage_at_primary_care',
      escalated: false,
      confidence: 0.8,
      explanation: {
        matchedConditions: ['MALARIA'],
        guidelineEvidence: ['MALARIA: Repeated vomiting', 'MALARIA: Impaired consciousness'],
        constraintRulesTriggered: [],
        reasoningSummary: 'Guideline evidence found for: MALARIA.',
      },
    },
  },
  {
    input: {
      caseId: 'SC-006',
      label: 'SC-006 -- newly elevated blood glucose',
      presentingComplaint:
        'A 52-year-old man presents with increased thirst, frequent urination, and unintentional weight loss.',
      history: 'No prior diagnosis of diabetes. Family history of diabetes in mother.',
      examinationFindings:
        'BMI 29. Random blood glucose 268 mg/dL, confirmed elevated. Feet intact, pulses present.',
    },
    result: {
      disposition: 'manage_at_primary_care',
      escalated: false,
      confidence: 0.8,
      explanation: {
        matchedConditions: ['DIABETES MELLITUS'],
        guidelineEvidence: ['DIABETES MELLITUS: Results from defects in insulin secretion'],
        constraintRulesTriggered: [],
        reasoningSummary: 'Guideline evidence found for: DIABETES MELLITUS.',
      },
    },
  },
  {
    input: {
      caseId: 'SC-012',
      label: 'SC-012 -- crushing chest pain with ST elevation',
      presentingComplaint:
        'A 57-year-old man presents with crushing central chest pain radiating to the left arm.',
      history:
        'Known hypertensive, smoker. Pain started at rest, associated with sweating and nausea.',
      examinationFindings:
        'Pulse 104/min, BP 100/64. ECG shows ST-segment elevation in the anterior leads.',
    },
    result: {
      disposition: null,
      escalated: true,
      confidence: 0.2,
      explanation: {
        matchedConditions: [],
        guidelineEvidence: [],
        constraintRulesTriggered: ['RF-003'],
        reasoningSummary:
          'Escalated: case text tripped red flag rule(s) RF-003 from the constraint checker.',
      },
    },
  },
  {
    input: {
      caseId: 'SC-004',
      label: 'SC-004 -- itching rash, no guideline match found',
      presentingComplaint:
        'A 19-year-old woman presents with itching and a rash affecting her hands and abdomen.',
      history: 'Itching worse at night. A sibling at home has a similar rash.',
      examinationFindings:
        'Burrow-like linear lesions between finger webs. No secondary infection.',
    },
    result: {
      disposition: null,
      escalated: true,
      confidence: 0.35,
      explanation: {
        matchedConditions: [],
        guidelineEvidence: [],
        constraintRulesTriggered: [],
        reasoningSummary:
          'No matching guideline condition found in the corpus for this case; baseline draft has low confidence.',
      },
    },
  },
]

export const CASE_NOTES: Record<string, string> = {
  'SC-006':
    'The doctor referred this case (refer_routine); the guideline-only baseline under-triages it to manage_at_primary_care. Expected weakness of a baseline with no persona policy or precedent memory (build_plan.md task 9).',
}

let nextInteractionId = 1

export function buildInitialReviewQueue(): ReviewQueueItem[] {
  const items: Array<[MockCase, ReviewQueueItem['clinicianAction']]> = [
    [MOCK_CASES[0], 'approved'],
    [MOCK_CASES[1], 'corrected'],
    [MOCK_CASES[2], 'escalated_review'],
    [MOCK_CASES[3], 'pending'],
  ]

  return items.map(([mockCase, clinicianAction]) => ({
    interactionId: `mock-${nextInteractionId++}`,
    caseLabel: mockCase.input.label,
    result: mockCase.result,
    clinicianAction,
  }))
}
