import { useState } from 'react'
import { api, type ConsentSubjectType } from '../api'

// Phase J: one explicit, separate consent screen per action -- never a single
// generic checkbox. The caller supplies the exact copy for what's being
// consented to; this component only handles the grant/already-granted state.
//
// Session-scoped consents (referenceId set) need a fresh grant per session --
// callers that generate a new referenceId per session (e.g. PatientRecordingPanel)
// should mount a new ConsentGate instance by passing `key={referenceId}`, which
// resets this component's state naturally rather than this component tracking
// referenceId changes itself.
interface ConsentGateProps {
  subjectType: ConsentSubjectType
  referenceId?: string
  title: string
  description: string
  children: React.ReactNode
}

export function ConsentGate({
  subjectType,
  referenceId,
  title,
  description,
  children,
}: ConsentGateProps) {
  const [granted, setGranted] = useState(false)
  const [granting, setGranting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (granted) {
    return <>{children}</>
  }

  async function handleGrant() {
    setGranting(true)
    setError(null)
    try {
      await api.grantConsent(subjectType, description, referenceId)
      setGranted(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record consent.')
    } finally {
      setGranting(false)
    }
  }

  return (
    <div className="consent-gate">
      <h3>{title}</h3>
      <p>{description}</p>
      {error && (
        <p role="alert" className="consent-error">
          {error}
        </p>
      )}
      <button type="button" onClick={handleGrant} disabled={granting}>
        {granting ? 'Recording consent...' : 'I consent'}
      </button>
    </div>
  )
}
