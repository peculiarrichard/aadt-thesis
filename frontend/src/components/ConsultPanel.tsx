import { useState } from 'react'
import { api, type ConsultResult } from '../api'
import { dispositionBadgeClass, dispositionLabel } from '../dispositionDisplay'
import type { DispositionClass } from '../types'
import { DoctorReport } from './DoctorReport'
import { TwinThoughtProcess } from './TwinThoughtProcess'

const DISPOSITION_OPTIONS = ['self-care advice', 'scheduled appointment', 'urgent referral']

// Phase O: ad-hoc consult (free text, not tied to an existing case) plus
// rate/correct -- a CORRECTED verdict folds back into precedent memory so
// the next consult sees it.
export function ConsultPanel() {
  const [caseText, setCaseText] = useState('')
  const [patientReference, setPatientReference] = useState('')
  const [patientAge, setPatientAge] = useState('')
  const [patientSex, setPatientSex] = useState('')
  const [temperature, setTemperature] = useState('')
  const [bloodPressure, setBloodPressure] = useState('')
  const [pulseRate, setPulseRate] = useState('')
  const [respiratoryRate, setRespiratoryRate] = useState('')
  const [oxygenSaturation, setOxygenSaturation] = useState('')
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
      const response = await api.consultTheTwin(caseText, {
        patientReference,
        patientAge,
        patientSex,
        temperature,
        bloodPressure,
        pulseRate,
        respiratoryRate,
        oxygenSaturation,
      })
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
        <p className="field-note">
          Clerical entries are for the report layout only -- use a reference label, never a real
          patient name or hospital number.
        </p>
        <div className="clerical-fields">
          <div className="field">
            <label htmlFor="patient-reference">Patient reference</label>
            <input
              id="patient-reference"
              type="text"
              value={patientReference}
              onChange={(e) => setPatientReference(e.target.value)}
              placeholder="e.g. Patient A"
            />
          </div>
          <div className="field">
            <label htmlFor="patient-age">Age</label>
            <input
              id="patient-age"
              type="text"
              value={patientAge}
              onChange={(e) => setPatientAge(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="patient-sex">Sex</label>
            <input
              id="patient-sex"
              type="text"
              value={patientSex}
              onChange={(e) => setPatientSex(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="temperature">Temperature</label>
            <input
              id="temperature"
              type="text"
              value={temperature}
              onChange={(e) => setTemperature(e.target.value)}
              placeholder="e.g. 37.2 C"
            />
          </div>
          <div className="field">
            <label htmlFor="blood-pressure">Blood pressure</label>
            <input
              id="blood-pressure"
              type="text"
              value={bloodPressure}
              onChange={(e) => setBloodPressure(e.target.value)}
              placeholder="e.g. 120/80 mmHg"
            />
          </div>
          <div className="field">
            <label htmlFor="pulse-rate">Pulse rate</label>
            <input
              id="pulse-rate"
              type="text"
              value={pulseRate}
              onChange={(e) => setPulseRate(e.target.value)}
              placeholder="e.g. 88 bpm"
            />
          </div>
          <div className="field">
            <label htmlFor="respiratory-rate">Respiratory rate</label>
            <input
              id="respiratory-rate"
              type="text"
              value={respiratoryRate}
              onChange={(e) => setRespiratoryRate(e.target.value)}
              placeholder="e.g. 18/min"
            />
          </div>
          <div className="field">
            <label htmlFor="oxygen-saturation">Oxygen saturation</label>
            <input
              id="oxygen-saturation"
              type="text"
              value={oxygenSaturation}
              onChange={(e) => setOxygenSaturation(e.target.value)}
              placeholder="e.g. 97%"
            />
          </div>
        </div>
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
                Confidence: {(result.confidence * 100).toFixed(0)}% -- too low to show a direct
                answer; a person should review this case instead.
              </span>
            </div>
          ) : (
            <div className="result-panel" role="status">
              <span className={dispositionBadgeClass(result.disposition as DispositionClass)}>
                {dispositionLabel(result.disposition as DispositionClass)}
              </span>
              <span className="confidence">Confidence: {(result.confidence * 100).toFixed(0)}%</span>
            </div>
          )}

          <TwinThoughtProcess result={result} />

          <DoctorReport report={result.report} />

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
