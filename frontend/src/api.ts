// Fetch client for the FastAPI backend (Phase F). Session-cookie-aware
// (credentials: 'include') for the Google-login-gated console routes.
const API_BASE_URL =
  (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ??
  'http://localhost:8000'

export interface ClinicianSession {
  clinicianId: string
  name: string
  email: string
  consentStatus: string
}

export interface ConsoleCase {
  caseId: string
  externalCaseRef: string | null
  presentingSummary: string
  doctorDisposition: string | null
  sourceType: string
}

export interface PerClassSummary {
  disposition: string
  support: number
  correct: number
  accuracy: number
}

export interface ConfigSummary {
  configLabel: string
  n: number
  concordance: number
  kappa: number
  meanSeverityWeightedError: number
  perClass: PerClassSummary[]
}

export interface ExplanationResult {
  matchedConditions: string[]
  guidelineEvidence: string[]
  constraintRulesTriggered: string[]
  reasoningSummary: string
}

export interface CaseResult {
  configLabel: string
  draftDisposition: string
  disposition: string | null
  confidence: number
  escalated: boolean
  escalationReasons: string[]
  precedentCaseRefs: string[]
  explanation: ExplanationResult
}

export type ConsentSubjectType =
  'clinician' | 'patient_data_batch' | 'walkthrough_recording' | 'patient_recording_session'

export interface StructuredDraft {
  caseId?: string | null
  caseText: string
  initialImpression: string | null
  questionsToAsk: string[]
  examinationOrChecks: string | null
  factorsTowardReferral: string | null
  factorsAgainstReferral: string | null
  flipUp: string | null
  flipDown: string | null
  redFlags: string | null
  confidence: string | null
  generalRule: string | null
  disposition: string | null
  dispositionReason: string | null
  redactionSummary: Record<string, number>
  llmFlagged: boolean
  llmFlagDetails: string | null
  rawTranscript?: string
}

export interface TwinStatus {
  qualifyingCaseCount: number
  minCasesRequired: number
  readyToBuild: boolean
  alreadyBuilt: boolean
}

export interface ConsultResult {
  interactionId: string
  configLabel: string
  draftDisposition: string
  disposition: string | null
  confidence: number
  escalated: boolean
  escalationReasons: string[]
  precedentCaseRefs: string[]
  explanation: ExplanationResult
}

function loginUrl(): string {
  return `${API_BASE_URL}/auth/google/login`
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...init,
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail ?? `${path} failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return fetchJson<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

interface StructuredDraftBody {
  case_id?: string | null
  case_text: string
  initial_impression: string | null
  questions_to_ask: string[]
  examination_or_checks: string | null
  factors_toward_referral: string | null
  factors_against_referral: string | null
  flip_up: string | null
  flip_down: string | null
  red_flags: string | null
  confidence: string | null
  general_rule: string | null
  disposition: string | null
  disposition_reason: string | null
  redaction_summary: Record<string, number>
  llm_flagged: boolean
  llm_flag_details: string | null
  raw_transcript?: string
}

function toStructuredDraft(body: StructuredDraftBody): StructuredDraft {
  return {
    caseId: body.case_id,
    caseText: body.case_text,
    initialImpression: body.initial_impression,
    questionsToAsk: body.questions_to_ask,
    examinationOrChecks: body.examination_or_checks,
    factorsTowardReferral: body.factors_toward_referral,
    factorsAgainstReferral: body.factors_against_referral,
    flipUp: body.flip_up,
    flipDown: body.flip_down,
    redFlags: body.red_flags,
    confidence: body.confidence,
    generalRule: body.general_rule,
    disposition: body.disposition,
    dispositionReason: body.disposition_reason,
    redactionSummary: body.redaction_summary,
    llmFlagged: body.llm_flagged,
    llmFlagDetails: body.llm_flag_details,
    rawTranscript: body.raw_transcript,
  }
}

export async function getCurrentClinician(): Promise<ClinicianSession | null> {
  try {
    const body = await fetchJson<{
      clinician_id: string
      name: string
      email: string
      consent_status: string
    }>('/auth/google/me')
    return {
      clinicianId: body.clinician_id,
      name: body.name,
      email: body.email,
      consentStatus: body.consent_status,
    }
  } catch {
    return null
  }
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/google/logout`, { method: 'POST', credentials: 'include' })
}

export async function getConsoleCases(): Promise<ConsoleCase[]> {
  const body = await fetchJson<
    Array<{
      case_id: string
      external_case_ref: string | null
      presenting_summary: string
      doctor_disposition: string | null
      source_type: string
    }>
  >('/console/cases')
  return body.map((c) => ({
    caseId: c.case_id,
    externalCaseRef: c.external_case_ref,
    presentingSummary: c.presenting_summary,
    doctorDisposition: c.doctor_disposition,
    sourceType: c.source_type,
  }))
}

export async function getCaseResult(caseId: string): Promise<CaseResult> {
  const body = await fetchJson<{
    config_label: string
    draft_disposition: string
    disposition: string | null
    confidence: number
    escalated: boolean
    escalation_reasons: string[]
    precedent_case_refs: string[]
    explanation: {
      matched_conditions: string[]
      guideline_evidence: string[]
      constraint_rules_triggered: string[]
      reasoning_summary: string
    }
  }>(`/console/cases/${caseId}/result`)
  return {
    configLabel: body.config_label,
    draftDisposition: body.draft_disposition,
    disposition: body.disposition,
    confidence: body.confidence,
    escalated: body.escalated,
    escalationReasons: body.escalation_reasons,
    precedentCaseRefs: body.precedent_case_refs,
    explanation: {
      matchedConditions: body.explanation.matched_conditions,
      guidelineEvidence: body.explanation.guideline_evidence,
      constraintRulesTriggered: body.explanation.constraint_rules_triggered,
      reasoningSummary: body.explanation.reasoning_summary,
    },
  }
}

export async function getConsoleResults(): Promise<ConfigSummary[]> {
  const body = await fetchJson<
    Array<{
      config_label: string
      n: number
      concordance: number
      kappa: number
      mean_severity_weighted_error: number
      per_class: PerClassSummary[]
    }>
  >('/console/results')
  return body.map((r) => ({
    configLabel: r.config_label,
    n: r.n,
    concordance: r.concordance,
    kappa: r.kappa,
    meanSeverityWeightedError: r.mean_severity_weighted_error,
    perClass: r.per_class,
  }))
}

// --- Phase J: consent -------------------------------------------------------

export async function grantConsent(
  subjectType: ConsentSubjectType,
  scope: string,
  referenceId?: string,
): Promise<void> {
  await postJson('/console/consent', {
    subject_type: subjectType,
    scope,
    reference_id: referenceId ?? null,
  })
}

// --- Phase K: bulk/form walkthrough-case intake ------------------------------

export interface CaseFormFields {
  caseId?: string
  caseText: string
  initialImpression?: string
  questionsToAsk?: string[]
  examinationOrChecks?: string
  factorsTowardReferral?: string
  factorsAgainstReferral?: string
  flipUp?: string
  flipDown?: string
  redFlags?: string
  confidence?: string
  generalRule?: string
  disposition: string
  dispositionReason?: string
}

function caseFormFieldsToBody(fields: CaseFormFields) {
  return {
    case_id: fields.caseId ?? null,
    case_text: fields.caseText,
    initial_impression: fields.initialImpression ?? null,
    questions_to_ask: fields.questionsToAsk ?? null,
    examination_or_checks: fields.examinationOrChecks ?? null,
    factors_toward_referral: fields.factorsTowardReferral ?? null,
    factors_against_referral: fields.factorsAgainstReferral ?? null,
    flip_up: fields.flipUp ?? null,
    flip_down: fields.flipDown ?? null,
    red_flags: fields.redFlags ?? null,
    confidence: fields.confidence ?? null,
    general_rule: fields.generalRule ?? null,
    disposition: fields.disposition,
    disposition_reason: fields.dispositionReason ?? null,
  }
}

// Privacy option 4: neither of these saves anything -- both scan and return
// a draft (or list of drafts) for review. `confirmDraft` below is the only
// call that actually persists a case.

export async function scanCaseForm(fields: CaseFormFields): Promise<StructuredDraft> {
  const body = await postJson<StructuredDraftBody>(
    '/console/cases/scan',
    caseFormFieldsToBody(fields),
  )
  return toStructuredDraft(body)
}

export async function bulkUploadCases(file: File): Promise<StructuredDraft[]> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${API_BASE_URL}/console/cases/bulk-upload`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail ?? `bulk upload failed: ${response.status}`)
  }
  const body = (await response.json()) as { drafts: StructuredDraftBody[] }
  return body.drafts.map(toStructuredDraft)
}

export function jsonTemplateUrl(): string {
  return `${API_BASE_URL}/console/cases/template`
}

export function xlsxTemplateUrl(): string {
  return `${API_BASE_URL}/console/cases/template.xlsx`
}

// --- Phase M: recording + de-identified upload + confirm --------------------

export async function uploadRecording(
  audio: Blob,
  kind: 'walkthrough' | 'patient_consultation',
  sessionReferenceId?: string,
): Promise<StructuredDraft> {
  const formData = new FormData()
  formData.append('audio', audio, 'recording.webm')
  formData.append('kind', kind)
  if (sessionReferenceId) formData.append('session_reference_id', sessionReferenceId)
  const response = await fetch(`${API_BASE_URL}/console/cases/recordings`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail ?? `recording upload failed: ${response.status}`)
  }
  return toStructuredDraft(await response.json())
}

export async function uploadDeidentifiedText(text: string): Promise<StructuredDraft> {
  const body = await postJson<StructuredDraftBody>('/console/cases/from-deidentified-text', {
    text,
  })
  return toStructuredDraft(body)
}

export async function confirmDraft(
  draft: CaseFormFields,
  sourceType: 'walkthrough' | 'real_consultation',
  attestationConfirmed: boolean,
): Promise<{ caseId: string; redactionSummary: Record<string, number> }> {
  const body = await postJson<{ case_id: string; redaction_summary: Record<string, number> }>(
    '/console/cases/confirm-draft',
    {
      ...caseFormFieldsToBody(draft),
      source_type: sourceType,
      attestation_confirmed: attestationConfirmed,
    },
  )
  return { caseId: body.case_id, redactionSummary: body.redaction_summary }
}

// --- Phase N: twin build ------------------------------------------------------

export async function getTwinStatus(): Promise<TwinStatus> {
  const body = await fetchJson<{
    qualifying_case_count: number
    min_cases_required: number
    ready_to_build: boolean
    already_built: boolean
  }>('/console/twin/status')
  return {
    qualifyingCaseCount: body.qualifying_case_count,
    minCasesRequired: body.min_cases_required,
    readyToBuild: body.ready_to_build,
    alreadyBuilt: body.already_built,
  }
}

export async function buildTwin(): Promise<{ embeddedCount: number }> {
  const body = await postJson<{ embedded_count: number }>('/console/twin/build', {})
  return { embeddedCount: body.embedded_count }
}

// --- Phase O: consult + feedback ----------------------------------------------

export async function consultTheTwin(caseText: string): Promise<ConsultResult> {
  const body = await postJson<{
    interaction_id: string
    config_label: string
    draft_disposition: string
    disposition: string | null
    confidence: number
    escalated: boolean
    escalation_reasons: string[]
    precedent_case_refs: string[]
    explanation: {
      matched_conditions: string[]
      guideline_evidence: string[]
      constraint_rules_triggered: string[]
      reasoning_summary: string
    }
  }>('/console/consult', { case_text: caseText })
  return {
    interactionId: body.interaction_id,
    configLabel: body.config_label,
    draftDisposition: body.draft_disposition,
    disposition: body.disposition,
    confidence: body.confidence,
    escalated: body.escalated,
    escalationReasons: body.escalation_reasons,
    precedentCaseRefs: body.precedent_case_refs,
    explanation: {
      matchedConditions: body.explanation.matched_conditions,
      guidelineEvidence: body.explanation.guideline_evidence,
      constraintRulesTriggered: body.explanation.constraint_rules_triggered,
      reasoningSummary: body.explanation.reasoning_summary,
    },
  }
}

export async function giveConsultFeedback(
  interactionId: string,
  caseText: string,
  action: 'approved' | 'corrected' | 'escalated_review',
  options?: { correctedDisposition?: string; correctedReasoning?: string; notes?: string },
): Promise<{ newCaseId: string | null }> {
  const body = await postJson<{ logged: boolean; new_case_id: string | null }>(
    `/console/consult/${interactionId}/feedback`,
    {
      action,
      case_text: caseText,
      corrected_disposition: options?.correctedDisposition ?? null,
      corrected_reasoning: options?.correctedReasoning ?? null,
      correction_notes: options?.notes ?? null,
    },
  )
  return { newCaseId: body.new_case_id }
}

export const api = {
  loginUrl,
  getCurrentClinician,
  logout,
  getConsoleCases,
  getCaseResult,
  getConsoleResults,
  grantConsent,
  scanCaseForm,
  bulkUploadCases,
  jsonTemplateUrl,
  xlsxTemplateUrl,
  uploadRecording,
  uploadDeidentifiedText,
  confirmDraft,
  getTwinStatus,
  buildTwin,
  consultTheTwin,
  giveConsultFeedback,
}
