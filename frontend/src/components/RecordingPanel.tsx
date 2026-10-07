import { useState } from 'react'
import { api, type StructuredDraft } from '../api'
import { ConsentGate } from './ConsentGate'
import { DraftReview } from './DraftReview'
import { PushToRecordButton } from './PushToRecordButton'

// Phase M: two deliberately separate recording entry points. Walkthrough
// narration needs only the clinician's own consent; a patient consultation
// additionally needs a fresh per-session consent every time, since each
// session's consent is a distinct event, not a standing grant.
export function WalkthroughRecordingPanel() {
  return (
    <section aria-labelledby="walkthrough-recording-heading" className="card">
      <h2 id="walkthrough-recording-heading">Record a Walkthrough Session</h2>
      <p className="record-hint">No patient is involved -- you're narrating your own reasoning.</p>
      <ConsentGate
        subjectType="walkthrough_recording"
        title="Consent to recording yourself"
        description="I consent to this walkthrough narration being recorded, transcribed, and used to build my digital twin."
      >
        <RecordAndReview kind="walkthrough" sourceType="walkthrough" />
      </ConsentGate>
    </section>
  )
}

export function PatientRecordingPanel() {
  const [sessionId] = useState(() => crypto.randomUUID())

  return (
    <section aria-labelledby="patient-recording-heading" className="card">
      <h2 id="patient-recording-heading">Record a Patient Consultation</h2>
      <p className="record-hint">
        Requires institutional ethics clearance (set by your administrator) and fresh consent for
        this specific session.
      </p>
      <ConsentGate
        key={sessionId}
        subjectType="patient_recording_session"
        referenceId={sessionId}
        title="Consent to recording this consultation"
        description="I confirm the patient has given informed consent for this specific consultation to be recorded, transcribed, de-identified, and used to build my digital twin."
      >
        <RecordAndReview
          kind="patient_consultation"
          sourceType="real_consultation"
          sessionReferenceId={sessionId}
        />
      </ConsentGate>
    </section>
  )
}

function RecordAndReview({
  kind,
  sourceType,
  sessionReferenceId,
}: {
  kind: 'walkthrough' | 'patient_consultation'
  sourceType: 'walkthrough' | 'real_consultation'
  sessionReferenceId?: string
}) {
  const [draft, setDraft] = useState<StructuredDraft | null>(null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedCaseId, setSavedCaseId] = useState<string | null>(null)

  async function handleRecordingComplete(blob: Blob) {
    setProcessing(true)
    setError(null)
    setDraft(null)
    try {
      const result = await api.uploadRecording(blob, kind, sessionReferenceId)
      setDraft(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not process the recording.')
    } finally {
      setProcessing(false)
    }
  }

  if (savedCaseId) {
    return <p className="record-status">Saved. You can record another session now.</p>
  }

  return (
    <div>
      <div className="record-row">
        <PushToRecordButton onRecordingComplete={handleRecordingComplete} />
        {processing && <p className="record-status">Transcribing and structuring...</p>}
      </div>
      {error && <p role="alert">{error}</p>}
      {draft && (
        <DraftReview draft={draft} sourceType={sourceType} onSaved={(id) => setSavedCaseId(id)} />
      )}
    </div>
  )
}
