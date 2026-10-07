import { useState } from 'react'
import type { CaseFormFields } from '../api'

// Shared structured-case form: Phase K's one-by-one entry and Phase M's
// review-before-save draft editor both use this -- one form, two callers,
// matching the backend's single shared field list (case_upload_parsing.py).
const DISPOSITION_OPTIONS = ['self-care advice', 'scheduled appointment', 'urgent referral']

interface CaseFormProps {
  initial?: Partial<CaseFormFields>
  submitLabel: string
  onSubmit: (fields: CaseFormFields) => Promise<void>
  extraNote?: string
  // Privacy option 3: shown only at the actual save step (DraftReview), not
  // on the initial entry form before anything has been scanned -- scanning
  // doesn't save, so there's nothing yet to attest to at that point.
  requireAttestation?: boolean
}

export function CaseForm({
  initial,
  submitLabel,
  onSubmit,
  extraNote,
  requireAttestation = false,
}: CaseFormProps) {
  const [caseText, setCaseText] = useState(initial?.caseText ?? '')
  const [initialImpression, setInitialImpression] = useState(initial?.initialImpression ?? '')
  const [questionsToAsk, setQuestionsToAsk] = useState((initial?.questionsToAsk ?? []).join('\n'))
  const [examinationOrChecks, setExaminationOrChecks] = useState(initial?.examinationOrChecks ?? '')
  const [factorsTowardReferral, setFactorsTowardReferral] = useState(
    initial?.factorsTowardReferral ?? '',
  )
  const [factorsAgainstReferral, setFactorsAgainstReferral] = useState(
    initial?.factorsAgainstReferral ?? '',
  )
  const [flipUp, setFlipUp] = useState(initial?.flipUp ?? '')
  const [flipDown, setFlipDown] = useState(initial?.flipDown ?? '')
  const [redFlags, setRedFlags] = useState(initial?.redFlags ?? '')
  const [confidence, setConfidence] = useState(initial?.confidence ?? '')
  const [generalRule, setGeneralRule] = useState(initial?.generalRule ?? '')
  const [disposition, setDisposition] = useState(initial?.disposition ?? '')
  const [dispositionReason, setDispositionReason] = useState(initial?.dispositionReason ?? '')

  const [attestationChecked, setAttestationChecked] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit({
        caseId: initial?.caseId,
        caseText,
        initialImpression: initialImpression || undefined,
        questionsToAsk: questionsToAsk
          .split('\n')
          .map((q) => q.trim())
          .filter(Boolean),
        examinationOrChecks: examinationOrChecks || undefined,
        factorsTowardReferral: factorsTowardReferral || undefined,
        factorsAgainstReferral: factorsAgainstReferral || undefined,
        flipUp: flipUp || undefined,
        flipDown: flipDown || undefined,
        redFlags: redFlags || undefined,
        confidence: confidence || undefined,
        generalRule: generalRule || undefined,
        disposition,
        dispositionReason: dispositionReason || undefined,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save this case.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="case-form">
      {extraNote && <p className="record-hint">{extraNote}</p>}

      <div className="field">
        <label htmlFor="case-text">Case / presentation</label>
        <textarea
          id="case-text"
          value={caseText}
          onChange={(e) => setCaseText(e.target.value)}
          required
          rows={3}
        />
      </div>

      <div className="field">
        <label htmlFor="initial-impression">Initial impression</label>
        <textarea
          id="initial-impression"
          value={initialImpression}
          onChange={(e) => setInitialImpression(e.target.value)}
          rows={2}
        />
      </div>

      <div className="field">
        <label htmlFor="questions-to-ask">Questions to ask (one per line)</label>
        <textarea
          id="questions-to-ask"
          value={questionsToAsk}
          onChange={(e) => setQuestionsToAsk(e.target.value)}
          rows={3}
        />
      </div>

      <div className="field">
        <label htmlFor="examination">Examination or checks</label>
        <textarea
          id="examination"
          value={examinationOrChecks}
          onChange={(e) => setExaminationOrChecks(e.target.value)}
          rows={2}
        />
      </div>

      <div className="field">
        <label htmlFor="factors-toward">Factors toward referral</label>
        <textarea
          id="factors-toward"
          value={factorsTowardReferral}
          onChange={(e) => setFactorsTowardReferral(e.target.value)}
          rows={2}
        />
      </div>

      <div className="field">
        <label htmlFor="factors-against">Factors against referral</label>
        <textarea
          id="factors-against"
          value={factorsAgainstReferral}
          onChange={(e) => setFactorsAgainstReferral(e.target.value)}
          rows={2}
        />
      </div>

      <div className="field">
        <label htmlFor="flip-up">What would flip this up (more urgent)</label>
        <textarea
          id="flip-up"
          value={flipUp}
          onChange={(e) => setFlipUp(e.target.value)}
          rows={2}
        />
      </div>

      <div className="field">
        <label htmlFor="flip-down">What would flip this down (less urgent)</label>
        <textarea
          id="flip-down"
          value={flipDown}
          onChange={(e) => setFlipDown(e.target.value)}
          rows={2}
        />
      </div>

      <div className="field">
        <label htmlFor="red-flags">Red flags</label>
        <textarea
          id="red-flags"
          value={redFlags}
          onChange={(e) => setRedFlags(e.target.value)}
          rows={2}
        />
      </div>

      <div className="field">
        <label htmlFor="confidence">Your confidence</label>
        <textarea
          id="confidence"
          value={confidence}
          onChange={(e) => setConfidence(e.target.value)}
          rows={2}
        />
      </div>

      <div className="field">
        <label htmlFor="general-rule">General rule this illustrates</label>
        <textarea
          id="general-rule"
          value={generalRule}
          onChange={(e) => setGeneralRule(e.target.value)}
          rows={2}
        />
      </div>

      <div className="field">
        <label htmlFor="disposition">Disposition</label>
        <select
          id="disposition"
          value={disposition}
          onChange={(e) => setDisposition(e.target.value)}
          required
        >
          <option value="" disabled>
            Select a disposition
          </option>
          {DISPOSITION_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label htmlFor="disposition-reason">Disposition reason</label>
        <textarea
          id="disposition-reason"
          value={dispositionReason}
          onChange={(e) => setDispositionReason(e.target.value)}
          rows={2}
        />
      </div>

      {requireAttestation && (
        <div className="field attestation-field">
          <label htmlFor="attestation">
            <input
              id="attestation"
              type="checkbox"
              checked={attestationChecked}
              onChange={(e) => setAttestationChecked(e.target.checked)}
            />{' '}
            I confirm this case does not reference a real, identifiable patient.
          </label>
        </div>
      )}

      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={submitting || (requireAttestation && !attestationChecked)}>
        {submitting ? 'Saving...' : submitLabel}
      </button>
    </form>
  )
}
