import { useEffect, useState } from 'react'
import { api, type CaseResult, type ConsoleCase } from '../api'
import { dispositionBadgeClass, dispositionLabel } from '../dispositionDisplay'
import type { DispositionClass } from '../types'
import { PushToRecordButton } from './PushToRecordButton'

// Layer 8 intake/case view (Section 5.8), wired to real backend data.
// The twin output panel calls GET /console/cases/{id}/result live -- it defaults
// to the deterministic guideline_plus_precedent config, not the LLM-calling
// configs, so browsing cases can't trigger the same memory-heavy inference path
// the batch LOOCV run needs.
export function IntakeCaseView() {
  const [cases, setCases] = useState<ConsoleCase[] | null>(null)
  const [casesError, setCasesError] = useState<string | null>(null)
  const [explicitSelection, setExplicitSelection] = useState<string | null>(null)

  const [recordingNote, setRecordingNote] = useState<string | null>(null)

  useEffect(() => {
    api
      .getConsoleCases()
      .then(setCases)
      .catch(() => setCasesError('Could not load cases.'))
  }, [])

  function handleRecordingComplete(blob: Blob) {
    setRecordingNote(
      `Captured ${Math.max(1, Math.round(blob.size / 1024))} KB (${blob.type || 'unknown type'}) -- mock capture only, not sent anywhere. Real consultation recording stays gated behind ethics clearance (Section 6.1).`,
    )
  }

  const selectedId = explicitSelection ?? cases?.[0]?.caseId ?? null
  const selected = cases?.find((c) => c.caseId === selectedId) ?? null

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
      {casesError && <p role="alert">{casesError}</p>}
      {!casesError && cases === null && <p>Loading cases...</p>}
      {cases !== null && cases.length === 0 && <p>No cases found for this clinician.</p>}

      {cases !== null && cases.length > 0 && (
        <div className="field">
          <label htmlFor="case-select">Select a case</label>
          <select
            id="case-select"
            value={selectedId ?? ''}
            onChange={(event) => setExplicitSelection(event.target.value)}
          >
            {cases.map((c) => (
              <option key={c.caseId} value={c.caseId}>
                {c.externalCaseRef ?? c.caseId}
              </option>
            ))}
          </select>
        </div>
      )}

      {selected && (
        <>
          <h3>Structured case summary</h3>
          <dl className="summary-grid">
            <dt>Presenting summary</dt>
            <dd>{selected.presentingSummary}</dd>
            <dt>Doctor's disposition</dt>
            <dd>{selected.doctorDisposition ?? 'not recorded'}</dd>
            <dt>Source</dt>
            <dd>{selected.sourceType}</dd>
          </dl>

          <TwinOutputPanel key={selected.caseId} caseId={selected.caseId} />
        </>
      )}
    </section>
  )
}

function TwinOutputPanel({ caseId }: { caseId: string }) {
  const [result, setResult] = useState<CaseResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .getCaseResult(caseId)
      .then(setResult)
      .catch(() => setError('Could not run the twin agent for this case.'))
  }, [caseId])

  return (
    <>
      <h3>Twin output</h3>
      {!result && !error && <p>Running the twin agent...</p>}
      {error && <p role="alert">{error}</p>}

      {result && (
        <>
          {result.escalated ? (
            <div className="result-panel result-panel--escalated" role="status">
              <span className="badge badge--escalated">Escalated for review</span>
              <span className="confidence">
                confidence {result.confidence.toFixed(2)} -- no disposition is shown as a normal
                output (Section 9)
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

          <h4>Explanation ({result.configLabel})</h4>
          <p>{result.explanation.reasoningSummary}</p>
          {result.explanation.guidelineEvidence.length > 0 && (
            <ul className="evidence-list">
              {result.explanation.guidelineEvidence.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
          {result.explanation.constraintRulesTriggered.length > 0 && (
            <p>
              Constraint rules triggered: {result.explanation.constraintRulesTriggered.join(', ')}
            </p>
          )}
          {result.precedentCaseRefs.length > 0 && (
            <p>Retrieved precedent cases: {result.precedentCaseRefs.join(', ')}</p>
          )}
        </>
      )}
    </>
  )
}
