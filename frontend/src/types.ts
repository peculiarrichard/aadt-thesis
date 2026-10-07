// Mirrors backend/src/backend/services and agents/baseline_agent.py shapes.
export type DispositionClass = 'self_care_advice' | 'scheduled_appointment' | 'urgent_referral'

export type ClinicianAction = 'pending' | 'approved' | 'corrected' | 'escalated_review'

export interface Explanation {
  matchedConditions: string[]
  guidelineEvidence: string[]
  constraintRulesTriggered: string[]
  reasoningSummary: string
}

// Mirrors ActResult: disposition is null when escalated (Section 9).
export interface AgentResult {
  disposition: DispositionClass | null
  escalated: boolean
  confidence: number
  explanation: Explanation
}

export interface CaseInput {
  caseId: string
  label: string
  presentingComplaint: string
  history: string
  examinationFindings: string
}

export interface MockCase {
  input: CaseInput
  result: AgentResult
}

// Mirrors interaction_log (Section 7).
export interface ReviewQueueItem {
  interactionId: string
  caseLabel: string
  result: AgentResult
  clinicianAction: ClinicianAction
}
