import { useEffect, useState } from 'react'
import { api, type ConfigSummary } from '../api'

// Section 5.8: "running concordance and calibration numbers... visible." Reads
// already-computed LOOCV results (backend/src/backend/evaluation/loocv.py) --
// does not trigger a live evaluation run itself.
const CONFIG_LABELS: Record<string, string> = {
  guideline_only: 'Guideline only (baseline)',
  guideline_plus_precedent: 'Guideline + precedent',
  guideline_plus_persona: 'Guideline + persona',
  full_system: 'Full twin (persona + precedent + guideline)',
}

export function ResultsView() {
  const [results, setResults] = useState<ConfigSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .getConsoleResults()
      .then(setResults)
      .catch(() => setError('Could not load results. Has the LOOCV evaluation been run yet?'))
  }, [])

  return (
    <section aria-labelledby="results-heading" className="card">
      <h2 id="results-heading">Evaluation Results</h2>
      <p className="record-hint">
        Leave-one-out cross-validation over the walkthrough cases (Section 10) -- see the "n" column
        per row for the current case count. Run <code>python -m backend.evaluation.loocv</code> to
        (re)compute.
      </p>

      {error && <p role="alert">{error}</p>}
      {!error && results === null && <p>Loading...</p>}
      {results !== null && results.length === 0 && (
        <p>No results logged yet -- run the LOOCV evaluation first.</p>
      )}

      {results !== null && results.length > 0 && (
        <table className="results-table">
          <thead>
            <tr>
              <th>Configuration</th>
              <th>n</th>
              <th>Concordance</th>
              <th>Cohen's kappa</th>
              <th>Mean severity-weighted error</th>
            </tr>
          </thead>
          <tbody>
            {results.map((row) => (
              <tr key={row.configLabel}>
                <td>{CONFIG_LABELS[row.configLabel] ?? row.configLabel}</td>
                <td>{row.n}</td>
                <td>{(row.concordance * 100).toFixed(1)}%</td>
                <td>{row.kappa.toFixed(3)}</td>
                <td>{row.meanSeverityWeightedError.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {results !== null &&
        results.map((row) => (
          <div key={row.configLabel}>
            <h3>{CONFIG_LABELS[row.configLabel] ?? row.configLabel} -- per class</h3>
            <ul className="evidence-list">
              {row.perClass.map((pc) => (
                <li key={pc.disposition}>
                  {pc.disposition}: {pc.correct}/{pc.support} ({(pc.accuracy * 100).toFixed(0)}%)
                </li>
              ))}
            </ul>
          </div>
        ))}
    </section>
  )
}
