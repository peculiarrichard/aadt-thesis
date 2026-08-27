import { useState } from 'react'
import { dispositionBadgeClass, dispositionLabel } from '../dispositionDisplay'
import { CASE_NOTES, MOCK_CASES } from '../mockData'
import type { MockCase } from '../types'
import { PushToRecordButton } from './PushToRecordButton'

// Layer 8 intake/case view (Section 5.8), built against mock data (task 11).
// Recording is still a local mock capture only -- see docs/build_plan.md task 11.
export function IntakeCaseView() {
  const [selected, setSelected] = useState<MockCase>(MOCK_CASES[0])
  const [recordingNote, setRecordingNote] = useState<string | null>(null)

  const note = CASE_NOTES[selected.input.caseId]

  function handleRecordingComplete(blob: Blob) {
    setRecordingNote(
      `Captured ${Math.max(1, Math.round(blob.size / 1024))} KB (${blob.type || 'unknown type'}) -- mock capture only, not sent anywhere. Real consultation recording stays gated behind ethics clearance (Section 6.1).`,
    )
  }

  return (
    <section aria-labelledby="intake-heading" className="card">
      <h2 id="intake-heading">Intake / Case</h2>

      <h3>Record consultation (scaffold)</h3>
      <div className="record-row">
        <PushToRecordButton onRecordingComplete={handleRecordingComplete} />
        {recordingNote && <p className="record-status">{recordingNote}</p>}
      </div>
      <p className="record-hint">
        Explicit start/stop only -- no passive or continuous listening. Not switched on for real
        consultations.
      </p>

      <h3>Case</h3>
      <div className="field">
        <label htmlFor="case-select">Select a case</label>
        <select
          id="case-select"
          value={selected.input.caseId}
          onChange={(event) => {
            const next = MOCK_CASES.find((c) => c.input.caseId === event.target.value)
            if (next) setSelected(next)
          }}
        >
          {MOCK_CASES.map((mockCase) => (
            <option key={mockCase.input.caseId} value={mockCase.input.caseId}>
              {mockCase.input.label}
            </option>
          ))}
        </select>
      </div>

      <h3>Structured case summary</h3>
      <dl className="summary-grid">
        <dt>Presenting complaint</dt>
        <dd>{selected.input.presentingComplaint}</dd>
        <dt>History</dt>
        <dd>{selected.input.history}</dd>
        <dt>Examination findings</dt>
        <dd>{selected.input.examinationFindings}</dd>
      </dl>

      <h3>Twin output</h3>
      {selected.result.escalated ? (
        <div className="result-panel result-panel--escalated" role="status">
          <span className="badge badge--escalated">Escalated for review</span>
          <span className="confidence">
            confidence {selected.result.confidence.toFixed(2)} -- no disposition is shown as a
            normal output (Section 9)
          </span>
        </div>
      ) : (
        <div className="result-panel" role="status">
          <span className={dispositionBadgeClass(selected.result.disposition!)}>
            {dispositionLabel(selected.result.disposition!)}
          </span>
          <span className="confidence">confidence {selected.result.confidence.toFixed(2)}</span>
        </div>
      )}

      <h4>Explanation</h4>
      <p>{selected.result.explanation.reasoningSummary}</p>
      {selected.result.explanation.guidelineEvidence.length > 0 && (
        <ul className="evidence-list">
          {selected.result.explanation.guidelineEvidence.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      {selected.result.explanation.constraintRulesTriggered.length > 0 && (
        <p>
          Constraint rules triggered:{' '}
          {selected.result.explanation.constraintRulesTriggered.join(', ')}
        </p>
      )}

      {note && (
        <p role="note" className="note">
          {note}
        </p>
      )}
    </section>
  )
}
