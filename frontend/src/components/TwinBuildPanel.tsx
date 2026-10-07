import { useEffect, useState } from 'react'
import { api, type TwinStatus } from '../api'

// Phase N: progress toward the minimum-case gate, and the build action
// itself once it's met.
export function TwinBuildPanel() {
  const [status, setStatus] = useState<TwinStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [building, setBuilding] = useState(false)
  const [buildResult, setBuildResult] = useState<string | null>(null)

  function refresh() {
    api
      .getTwinStatus()
      .then(setStatus)
      .catch(() => setError('Could not load twin status.'))
  }

  useEffect(() => {
    refresh()
  }, [])

  async function handleBuild() {
    setBuilding(true)
    setError(null)
    setBuildResult(null)
    try {
      const { embeddedCount } = await api.buildTwin()
      setBuildResult(`Twin built from ${embeddedCount} case(s).`)
      refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not build your twin.')
    } finally {
      setBuilding(false)
    }
  }

  return (
    <section aria-labelledby="twin-build-heading" className="card">
      <h2 id="twin-build-heading">Build Your Twin</h2>
      {error && <p role="alert">{error}</p>}
      {!status && !error && <p>Loading...</p>}
      {status && (
        <>
          <p>
            {status.qualifyingCaseCount} / {status.minCasesRequired} cases
          </p>
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{
                width: `${Math.min(100, (status.qualifyingCaseCount / status.minCasesRequired) * 100)}%`,
              }}
            />
          </div>
          {status.alreadyBuilt && <p className="record-status">Your twin is already built.</p>}
          {!status.readyToBuild && (
            <p className="record-hint">
              Add {status.minCasesRequired - status.qualifyingCaseCount} more case(s) (walkthrough
              or de-identified patient cases) before you can build your twin.
            </p>
          )}
          {status.readyToBuild && (
            <button type="button" onClick={handleBuild} disabled={building}>
              {building
                ? 'Building...'
                : status.alreadyBuilt
                  ? 'Rebuild twin with latest cases'
                  : 'Build my twin'}
            </button>
          )}
          {buildResult && <p className="record-status">{buildResult}</p>}
        </>
      )}
    </section>
  )
}
