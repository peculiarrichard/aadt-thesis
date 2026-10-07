import { useEffect, useState } from 'react'
import { api, type ClinicianSession } from './api'
import { AddCasesPanel } from './components/AddCasesPanel'
import { ConsultPanel } from './components/ConsultPanel'
import { DeidentifiedUploadPanel } from './components/DeidentifiedUploadPanel'
import { IntakeCaseView } from './components/IntakeCaseView'
import { LoginScreen } from './components/LoginScreen'
import { PatientRecordingPanel, WalkthroughRecordingPanel } from './components/RecordingPanel'
import { ResultsView } from './components/ResultsView'
import { ReviewQueueView } from './components/ReviewQueueView'
import { TwinBuildPanel } from './components/TwinBuildPanel'

// Layer 8 console shell (Section 5.8). Gated behind Google sign-in. Each
// data-intake path is its own tab, deliberately kept separate (not combined
// into one generic "add data" screen) so what a doctor is consenting to and
// doing is always unambiguous.
type View =
  | 'intake'
  | 'addCases'
  | 'recordWalkthrough'
  | 'recordPatient'
  | 'uploadDeidentified'
  | 'buildTwin'
  | 'consult'
  | 'queue'
  | 'results'

const TABS: { key: View; label: string }[] = [
  { key: 'intake', label: 'Intake / Case' },
  { key: 'addCases', label: 'Add Cases' },
  { key: 'recordWalkthrough', label: 'Record Walkthrough' },
  { key: 'recordPatient', label: 'Record Patient' },
  { key: 'uploadDeidentified', label: 'Upload De-Identified' },
  { key: 'buildTwin', label: 'Build Twin' },
  { key: 'consult', label: 'Consult' },
  { key: 'queue', label: 'Review Queue' },
  { key: 'results', label: 'Results' },
]

function App() {
  const [view, setView] = useState<View>('intake')
  const [clinician, setClinician] = useState<ClinicianSession | null | undefined>(undefined)

  useEffect(() => {
    api.getCurrentClinician().then(setClinician)
  }, [])

  if (clinician === undefined) {
    return (
      <div className="app-shell">
        <p>Loading...</p>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>ADDT Console</h1>
          <p className="app-tagline">Agentic Digital Twin -- clinician review console</p>
        </div>
        {clinician && (
          <div className="session-info">
            <span>{clinician.name}</span>
            <button type="button" onClick={() => api.logout().then(() => setClinician(null))}>
              Sign out
            </button>
          </div>
        )}
      </header>

      {!clinician ? (
        <LoginScreen />
      ) : (
        <>
          <nav className="tab-nav" aria-label="Console views">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                aria-pressed={view === tab.key}
                onClick={() => setView(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </nav>
          <main>
            {view === 'intake' && <IntakeCaseView />}
            {view === 'addCases' && <AddCasesPanel />}
            {view === 'recordWalkthrough' && <WalkthroughRecordingPanel />}
            {view === 'recordPatient' && <PatientRecordingPanel />}
            {view === 'uploadDeidentified' && <DeidentifiedUploadPanel />}
            {view === 'buildTwin' && <TwinBuildPanel />}
            {view === 'consult' && <ConsultPanel />}
            {view === 'queue' && <ReviewQueueView />}
            {view === 'results' && <ResultsView />}
          </main>
        </>
      )}
    </div>
  )
}

export default App
