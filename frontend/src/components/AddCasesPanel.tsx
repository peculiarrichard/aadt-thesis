import { useRef, useState } from 'react'
import { api, type StructuredDraft } from '../api'
import { CaseForm } from './CaseForm'
import { ConsentGate } from './ConsentGate'
import { DraftReview } from './DraftReview'

// Phase K: walkthrough-case intake, no patient involved -- bulk upload
// (JSON/.xlsx) and one-by-one form, both behind the same standing
// WALKTHROUGH_RECORDING-equivalent consent. Deliberately its own tab,
// separate from the patient-related recording/upload panels.
//
// Privacy option 4: neither path saves directly -- both scan first and show
// a review step. The one-by-one form reuses DraftReview (same as the
// recording/de-identified-text flows); bulk shows a compact list since it
// can be many records, with one attestation covering the whole batch.
export function AddCasesPanel() {
  return (
    <section aria-labelledby="add-cases-heading" className="card">
      <h2 id="add-cases-heading">Add Walkthrough Cases</h2>
      <p className="record-hint">
        For cases you've already talked through outside this system -- no patient is involved in any
        of this.
      </p>
      <ConsentGate
        subjectType="walkthrough_recording"
        title="Consent to add your case data"
        description="I consent to my own walkthrough case narration and reasoning being stored and used to build my digital twin."
      >
        <BulkUpload />
        <OneByOneForm />
      </ConsentGate>
    </section>
  )
}

function BulkUpload() {
  const [drafts, setDrafts] = useState<StructuredDraft[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    setDrafts(null)
    try {
      setDrafts(await api.bulkUploadCases(file))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="upload-block">
      <h3>Bulk upload</h3>
      <p className="record-hint">
        Download a template, fill it in, then upload it here.{' '}
        <a href={api.jsonTemplateUrl()}>JSON template</a> ·{' '}
        <a href={api.xlsxTemplateUrl()}>Excel template</a>
      </p>
      <input
        ref={inputRef}
        type="file"
        accept=".json,.xlsx"
        onChange={handleFileChange}
        disabled={uploading}
        aria-label="Upload cases file"
      />
      {uploading && <p>Uploading...</p>}
      {error && <p role="alert">{error}</p>}
      {drafts && drafts.length > 0 && (
        <BulkDraftReview drafts={drafts} onDone={() => setDrafts(null)} />
      )}
      {drafts && drafts.length === 0 && <p>No cases found in that file.</p>}
    </div>
  )
}

function BulkDraftReview({ drafts, onDone }: { drafts: StructuredDraft[]; onDone: () => void }) {
  const [attestationChecked, setAttestationChecked] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savedCount, setSavedCount] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const anyFlagged = drafts.some((d) => d.llmFlagged || Object.keys(d.redactionSummary).length > 0)

  async function saveAll() {
    setSaving(true)
    setError(null)
    setSavedCount(0)
    try {
      for (const draft of drafts) {
        await api.confirmDraft(
          {
            caseId: draft.caseId ?? undefined,
            caseText: draft.caseText,
            initialImpression: draft.initialImpression ?? undefined,
            questionsToAsk: draft.questionsToAsk,
            examinationOrChecks: draft.examinationOrChecks ?? undefined,
            factorsTowardReferral: draft.factorsTowardReferral ?? undefined,
            factorsAgainstReferral: draft.factorsAgainstReferral ?? undefined,
            flipUp: draft.flipUp ?? undefined,
            flipDown: draft.flipDown ?? undefined,
            redFlags: draft.redFlags ?? undefined,
            confidence: draft.confidence ?? undefined,
            generalRule: draft.generalRule ?? undefined,
            disposition: draft.disposition ?? '',
            dispositionReason: draft.dispositionReason ?? undefined,
          },
          'walkthrough',
          true,
        )
        setSavedCount((n) => n + 1)
      }
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save all cases.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="draft-review">
      <h4>{drafts.length} case(s) parsed -- review before saving</h4>
      <ul className="evidence-list">
        {drafts.map((draft, i) => (
          <li key={draft.caseId ?? i}>
            <strong>{draft.caseId ?? `Record ${i + 1}`}</strong>: {draft.caseText.slice(0, 80)}
            {draft.caseText.length > 80 ? '...' : ''}
            {Object.keys(draft.redactionSummary).length > 0 && (
              <>
                {' '}
                -- redacted:{' '}
                {Object.entries(draft.redactionSummary)
                  .map(([k, v]) => `${k} (${v})`)
                  .join(', ')}
              </>
            )}
            {draft.llmFlagged && (
              <span className="note note--flag"> -- flagged: {draft.llmFlagDetails}</span>
            )}
          </li>
        ))}
      </ul>
      {anyFlagged && (
        <p className="note note--flag">
          One or more cases were redacted or flagged above. Review each one before confirming.
        </p>
      )}
      <div className="field attestation-field">
        <label htmlFor="bulk-attestation">
          <input
            id="bulk-attestation"
            type="checkbox"
            checked={attestationChecked}
            onChange={(e) => setAttestationChecked(e.target.checked)}
          />{' '}
          I confirm none of these cases reference a real, identifiable patient.
        </label>
      </div>
      {error && <p role="alert">{error}</p>}
      {saving && (
        <p>
          Saving {savedCount + 1} of {drafts.length}...
        </p>
      )}
      <button type="button" onClick={saveAll} disabled={saving || !attestationChecked}>
        Save all {drafts.length} case(s)
      </button>
    </div>
  )
}

function OneByOneForm() {
  const [draft, setDraft] = useState<StructuredDraft | null>(null)
  const [savedCount, setSavedCount] = useState(0)
  const [showForm, setShowForm] = useState(false)

  return (
    <div className="upload-block">
      <h3>Add one case</h3>
      {!showForm && !draft && (
        <button type="button" onClick={() => setShowForm(true)}>
          Add a case
        </button>
      )}
      {savedCount > 0 && <p className="record-status">Saved {savedCount} case(s) this session.</p>}
      {showForm && !draft && (
        <CaseForm
          submitLabel="Review before saving"
          onSubmit={async (fields) => {
            setDraft(await api.scanCaseForm(fields))
          }}
        />
      )}
      {draft && (
        <DraftReview
          draft={draft}
          sourceType="walkthrough"
          onSaved={() => {
            setSavedCount((n) => n + 1)
            setDraft(null)
            setShowForm(false)
          }}
        />
      )}
    </div>
  )
}
