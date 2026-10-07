import { useState } from 'react'
import { api, type StructuredDraft } from '../api'
import { ConsentGate } from './ConsentGate'
import { DraftReview } from './DraftReview'

// Phase M: a de-identified patient case the doctor already wrote up or
// recorded outside this system -- separate from the live-recording panel,
// separate consent ("I already de-identified this"), its own UI surface.
export function DeidentifiedUploadPanel() {
  return (
    <section aria-labelledby="deidentified-upload-heading" className="card">
      <h2 id="deidentified-upload-heading">Upload a De-Identified Patient Case</h2>
      <p className="record-hint">
        For a case you've already written up or recorded elsewhere, and already de-identified.
        Requires institutional ethics clearance.
      </p>
      <ConsentGate
        subjectType="patient_data_batch"
        title="Consent to this upload"
        description="I confirm this text has already been de-identified -- no real patient name, contact detail, or other identifying information is included."
      >
        <UploadForm />
      </ConsentGate>
    </section>
  )
}

function UploadForm() {
  const [text, setText] = useState('')
  const [draft, setDraft] = useState<StructuredDraft | null>(null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedCaseId, setSavedCaseId] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setProcessing(true)
    setError(null)
    setDraft(null)
    try {
      const result = await api.uploadDeidentifiedText(text)
      setDraft(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not process this text.')
    } finally {
      setProcessing(false)
    }
  }

  if (savedCaseId) {
    return <p className="record-status">Saved. You can upload another case now.</p>
  }

  return (
    <div>
      {!draft && (
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="deidentified-text">De-identified case text</label>
            <textarea
              id="deidentified-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              required
            />
          </div>
          {error && <p role="alert">{error}</p>}
          <button type="submit" disabled={processing}>
            {processing ? 'Processing...' : 'Process this case'}
          </button>
        </form>
      )}
      {draft && (
        <DraftReview
          draft={draft}
          sourceType="real_consultation"
          onSaved={(id) => setSavedCaseId(id)}
        />
      )}
    </div>
  )
}
