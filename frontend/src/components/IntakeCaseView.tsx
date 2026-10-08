import { useEffect, useState } from 'react'
import { api, type CaseResult, type ConsoleCase } from '../api'
import { dispositionBadgeClass, dispositionLabel } from '../dispositionDisplay'
import type { DispositionClass } from '../types'
import { PushToRecordButton } from './PushToRecordButton'

// Twin output only runs on an explicit button click, using the deterministic
// guideline_plus_precedent config (not the LLM-calling ones).
export function IntakeCaseView() {
  const [cases, setCases] = useState<ConsoleCase[] | null>(null)
  const [casesError, setCasesError] = useState<string | null>(null)
  const [explicitSelection, setExplicitSelection] = useState<string | null>(null)

  const [recordingNote, setRecordingNote] = useState<string | null>(null)

  const [results, setResults] = useState<Record<string, CaseResult>>({})
  const [resultErrors, setResultErrors] = useState<Record<string, string>>({})
  const [runningIds, setRunningIds] = useState<Set<string>>(new Set())
  const [runningAll, setRunningAll] = useState(false)

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

  async function runCase(caseId: string) {
    setRunningIds((prev) => new Set(prev).add(caseId))
    setResultErrors(({ [caseId]: _dropped, ...rest }) => rest)
    try {
      const result = await api.getCaseResult(caseId)
      setResults((prev) => ({ ...prev, [caseId]: result }))
    } catch {
      setResultErrors((prev) => ({ ...prev, [caseId]: 'Could not run the twin agent for this case.' }))
    } finally {
      setRunningIds((prev) => {
        const next = new Set(prev)
        next.delete(caseId)
        return next
      })
    }
  }

  async function handleRunAll() {
    if (!cases) return
    setRunningAll(true)
    // Sequential, not Promise.all -- each call hits the DB, and running every
    // case concurrently is the same connection-pool spike a batch LOOCV run causes.
    for (const c of cases) {
      await runCase(c.caseId)
    }
    setRunningAll(false)
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
          <button type="button" onClick={handleRunAll} disabled={runningAll}>
            {runningAll ? 'Running twin on all cases...' : 'Run twin on all cases'}
          </button>
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

          <TwinOutputPanel
            result={results[selected.caseId] ?? null}
            error={resultErrors[selected.caseId] ?? null}
            running={runningIds.has(selected.caseId)}
            onRun={() => runCase(selected.caseId)}
          />
        </>
      )}
    </section>
  )
}

function TwinOutputPanel({
  result,
  error,
  running,
  onRun,
}: {
  result: CaseResult | null
  error: string | null
  running: boolean
  onRun: () => void
}) {
  return (
    <>
      <h3>Twin output</h3>
      {!result && (
        <button type="button" onClick={onRun} disabled={running}>
          {running ? 'Running the twin agent...' : 'Run twin on this case'}
        </button>
      )}
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
