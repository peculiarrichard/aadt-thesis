import { useState } from 'react'
import { api, type ConsultResult } from '../api'
import { dispositionBadgeClass, dispositionLabel } from '../dispositionDisplay'
import type { DispositionClass } from '../types'

const DISPOSITION_OPTIONS = ['self-care advice', 'scheduled appointment', 'urgent referral']

// Phase O: ad-hoc consult (free text, not tied to an existing case) plus
// rate/correct -- a CORRECTED verdict folds back into precedent memory so
// the next consult sees it.
export function ConsultPanel() {
  const [caseText, setCaseText] = useState('')
  const [result, setResult] = useState<ConsultResult | null>(null)
  const [consulting, setConsulting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [feedbackGiven, setFeedbackGiven] = useState(false)

  async function handleConsult(event: React.FormEvent) {
    event.preventDefault()
    setConsulting(true)
    setError(null)
    setResult(null)
    setFeedbackGiven(false)
    try {
      const response = await api.consultTheTwin(caseText)
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not consult your twin.')
    } finally {
      setConsulting(false)
    }
  }

  return (
    <section aria-labelledby="consult-heading" className="card">
      <h2 id="consult-heading">Consult Your Twin</h2>
      <form onSubmit={handleConsult}>
        <div className="field">
          <label htmlFor="consult-text">Describe the case</label>
          <textarea
            id="consult-text"
            value={caseText}
            onChange={(e) => setCaseText(e.target.value)}
            rows={4}
            required
          />
        </div>
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={consulting}>
          {consulting ? 'Consulting...' : 'Ask the twin'}
        </button>
      </form>

      {result && (
        <>
          <h3>Twin output</h3>
          {result.escalated ? (
            <div className="result-panel result-panel--escalated" role="status">
              <span className="badge badge--escalated">Escalated for review</span>
              <span className="confidence">
                confidence {result.confidence.toFixed(2)} -- no disposition shown as a normal output
                (Section 9)
              </span>
            </div>
          ) : (
            <div className="result-panel" role="status">
              <span className={dispositionBadgeClass(result.disposition as DispositionClass)}>
                {dispositionLabel(result.disposition as DispositionClass)}
              </span>
              <span className="confidence">confidence {result.confidence.toFixed(2)}</span>
            </div>
          )}
          <p>{result.explanation.reasoningSummary}</p>

          {!feedbackGiven && (
            <FeedbackControls
              interactionId={result.interactionId}
              caseText={caseText}
              onDone={() => setFeedbackGiven(true)}
            />
          )}
          {feedbackGiven && <p className="record-status">Thanks -- feedback recorded.</p>}
        </>
      )}
    </section>
  )
}

function FeedbackControls({
  interactionId,
  caseText,
  onDone,
}: {
  interactionId: string
  caseText: string
  onDone: () => void
}) {
  const [showCorrection, setShowCorrection] = useState(false)
  const [correctedDisposition, setCorrectedDisposition] = useState('')
  const [correctedReasoning, setCorrectedReasoning] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function approve() {
    setSubmitting(true)
    try {
      await api.giveConsultFeedback(interactionId, caseText, 'approved')
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record feedback.')
    } finally {
      setSubmitting(false)
    }
  }

  async function escalate() {
    setSubmitting(true)
    try {
      await api.giveConsultFeedback(interactionId, caseText, 'escalated_review')
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record feedback.')
    } finally {
      setSubmitting(false)
    }
  }

  async function submitCorrection(event: React.FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api.giveConsultFeedback(interactionId, caseText, 'corrected', {
        correctedDisposition,
        correctedReasoning,
      })
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record your correction.')
    } finally {
      setSubmitting(false)
    }
  }

  if (showCorrection) {
    return (
      <form onSubmit={submitCorrection} className="case-form">
        <div className="field">
          <label htmlFor="corrected-disposition">What should the disposition have been?</label>
          <select
            id="corrected-disposition"
            value={correctedDisposition}
            onChange={(e) => setCorrectedDisposition(e.target.value)}
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
          <label htmlFor="corrected-reasoning">Your reasoning</label>
          <textarea
            id="corrected-reasoning"
            value={correctedReasoning}
            onChange={(e) => setCorrectedReasoning(e.target.value)}
            rows={3}
          />
        </div>
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={submitting}>
          {submitting ? 'Saving...' : 'Submit correction'}
        </button>
      </form>
    )
  }

  return (
    <div className="queue-actions">
      <button type="button" onClick={approve} disabled={submitting}>
        Agree with the twin
      </button>
      <button type="button" onClick={() => setShowCorrection(true)} disabled={submitting}>
        Correct it
      </button>
      <button type="button" onClick={escalate} disabled={submitting}>
        Flag for review
      </button>
      {error && <p role="alert">{error}</p>}
    </div>
  )
}
