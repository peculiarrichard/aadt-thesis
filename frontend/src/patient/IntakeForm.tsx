import { useState } from 'react'
import { api } from '../api'

// Vitals + presenting complaint, entered by the patient before the chat
// starts (Phase W) -- same field layout/warning convention as
// ConsultPanel.tsx's clerical-fields block.
export function IntakeForm({
  clinicianId,
  onStarted,
  onCancel,
}: {
  clinicianId: string
  onStarted: (sessionId: string) => void
  onCancel: () => void
}) {
  const [presentingComplaint, setPresentingComplaint] = useState('')
  const [patientAge, setPatientAge] = useState('')
  const [patientSex, setPatientSex] = useState('')
  const [temperature, setTemperature] = useState('')
  const [bloodPressure, setBloodPressure] = useState('')
  const [pulseRate, setPulseRate] = useState('')
  const [respiratoryRate, setRespiratoryRate] = useState('')
  const [oxygenSaturation, setOxygenSaturation] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const sessionId = await api.createChatSession(clinicianId, presentingComplaint, {
        patientAge,
        patientSex,
        temperature,
        bloodPressure,
        pulseRate,
        respiratoryRate,
        oxygenSaturation,
      })
      onStarted(sessionId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the consult.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section aria-labelledby="intake-heading" className="card">
      <h2 id="intake-heading">Before you start</h2>
      <p className="field-note">
        Simulated patient only -- use made-up vitals and details, never real ones.
      </p>
      <form onSubmit={handleSubmit}>
        <div className="clerical-fields">
          <div className="field">
            <label htmlFor="intake-age">Age</label>
            <input
              id="intake-age"
              type="text"
              value={patientAge}
              onChange={(e) => setPatientAge(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="intake-sex">Sex</label>
            <input
              id="intake-sex"
              type="text"
              value={patientSex}
              onChange={(e) => setPatientSex(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="intake-temp">Temperature</label>
            <input
              id="intake-temp"
              type="text"
              value={temperature}
              onChange={(e) => setTemperature(e.target.value)}
              placeholder="e.g. 37.2 C"
            />
          </div>
          <div className="field">
            <label htmlFor="intake-bp">Blood pressure</label>
            <input
              id="intake-bp"
              type="text"
              value={bloodPressure}
              onChange={(e) => setBloodPressure(e.target.value)}
              placeholder="e.g. 120/80 mmHg"
            />
          </div>
          <div className="field">
            <label htmlFor="intake-pulse">Pulse rate</label>
            <input
              id="intake-pulse"
              type="text"
              value={pulseRate}
              onChange={(e) => setPulseRate(e.target.value)}
              placeholder="e.g. 88 bpm"
            />
          </div>
          <div className="field">
            <label htmlFor="intake-rr">Respiratory rate</label>
            <input
              id="intake-rr"
              type="text"
              value={respiratoryRate}
              onChange={(e) => setRespiratoryRate(e.target.value)}
              placeholder="e.g. 18/min"
            />
          </div>
          <div className="field">
            <label htmlFor="intake-spo2">Oxygen saturation</label>
            <input
              id="intake-spo2"
              type="text"
              value={oxygenSaturation}
              onChange={(e) => setOxygenSaturation(e.target.value)}
              placeholder="e.g. 97%"
            />
          </div>
        </div>
        <div className="field">
          <label htmlFor="intake-complaint">What&rsquo;s the (simulated) problem?</label>
          <textarea
            id="intake-complaint"
            value={presentingComplaint}
            onChange={(e) => setPresentingComplaint(e.target.value)}
            rows={3}
            required
          />
        </div>
        {error && <p role="alert">{error}</p>}
        <div className="queue-actions">
          <button type="submit" disabled={submitting}>
            {submitting ? 'Starting...' : 'Start chat'}
          </button>
          <button type="button" onClick={onCancel} disabled={submitting}>
            Back
          </button>
        </div>
      </form>
    </section>
  )
}
