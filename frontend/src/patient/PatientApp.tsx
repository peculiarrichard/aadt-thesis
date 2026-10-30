import { useEffect, useState } from 'react'
import { api, type PatientSession } from '../api'
import { IntakeForm } from './IntakeForm'
import { PatientChat } from './PatientChat'
import { PatientLoginScreen } from './PatientLoginScreen'
import { PatientReportView } from './PatientReportView'
import { TwinDirectory } from './TwinDirectory'

// Patient-facing digital twin (further work, outside the thesis's evaluated
// methodology -- simulated patients only). Mounted at the /patient path
// (see main.tsx) as a separate app shell from the clinician console --
// nothing about the console changes.
type View = 'directory' | 'intake' | 'chat' | 'result'

export function PatientApp() {
  const [patient, setPatient] = useState<PatientSession | null | undefined>(undefined)
  const [view, setView] = useState<View>('directory')
  const [selectedClinicianId, setSelectedClinicianId] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)

  useEffect(() => {
    api.getCurrentPatient().then(setPatient)
  }, [])

  if (patient === undefined) {
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
          <h1>ADDT Patient Portal</h1>
          <p className="app-tagline">
            Simulated patients only -- no real identities or symptoms. For demonstration.
          </p>
        </div>
        {patient && (
          <div className="session-info">
            <span>{patient.username}</span>
            <button type="button" onClick={() => api.patientLogout().then(() => setPatient(null))}>
              Sign out
            </button>
          </div>
        )}
      </header>

      {!patient ? (
        <PatientLoginScreen onSignedIn={setPatient} />
      ) : (
        <main>
          {view === 'directory' && (
            <TwinDirectory
              onSelect={(clinicianId) => {
                setSelectedClinicianId(clinicianId)
                setView('intake')
              }}
            />
          )}
          {view === 'intake' && selectedClinicianId && (
            <IntakeForm
              clinicianId={selectedClinicianId}
              onStarted={(newSessionId) => {
                setSessionId(newSessionId)
                setView('chat')
              }}
              onCancel={() => setView('directory')}
            />
          )}
          {view === 'chat' && sessionId && (
            <PatientChat sessionId={sessionId} onSubmitted={() => setView('result')} />
          )}
          {view === 'result' && sessionId && selectedClinicianId && (
            <PatientReportView
              sessionId={sessionId}
              clinicianId={selectedClinicianId}
              onDone={() => {
                setSessionId(null)
                setSelectedClinicianId(null)
                setView('directory')
              }}
            />
          )}
        </main>
      )}
    </div>
  )
}
