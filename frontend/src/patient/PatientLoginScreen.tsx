import { useState } from 'react'
import { api, type PatientSession } from '../api'

// Simulated patients only -- email+password here is for a demo account, not
// a real identity; the username (not the email) is what's shown everywhere
// else in the app.
export function PatientLoginScreen({
  onSignedIn,
}: {
  onSignedIn: (session: PatientSession) => void
}) {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [username, setUsername] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const session =
        mode === 'signup'
          ? await api.patientSignup(email, password, username)
          : await api.patientLogin(email, password)
      onSignedIn(session)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="login-hero" aria-labelledby="patient-login-heading">
      <div className="card login-panel">
        <h2 id="patient-login-heading">
          {mode === 'signup' ? 'Create a demo account' : 'Sign in'}
        </h2>
        <p className="field-note">
          Simulated patients only -- use a made-up identity, never a real name, email, or
          symptoms.
        </p>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="patient-email">Email (for this demo account)</label>
            <input
              id="patient-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="patient-password">Password</label>
            <input
              id="patient-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {mode === 'signup' && (
            <div className="field">
              <label htmlFor="patient-username">
                Username (shown instead of your name or email everywhere in this app)
              </label>
              <input
                id="patient-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. simulated-patient-7"
                required
              />
            </div>
          )}
          {error && <p role="alert">{error}</p>}
          <button type="submit" disabled={submitting}>
            {submitting ? 'Please wait...' : mode === 'signup' ? 'Create account' : 'Sign in'}
          </button>
        </form>
        <button type="button" onClick={() => setMode(mode === 'signup' ? 'login' : 'signup')}>
          {mode === 'signup'
            ? 'Already have an account? Sign in'
            : "Don't have an account? Sign up"}
        </button>
      </div>
    </section>
  )
}
