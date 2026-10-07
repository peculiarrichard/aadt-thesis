import { api } from '../api'
import { TwinDiagram } from './TwinDiagram'

// Gates the console behind Google sign-in.
export function LoginScreen() {
  return (
    <section className="login-hero" aria-labelledby="login-heading">
      <div className="login-diagram-panel">
        <TwinDiagram />
      </div>

      <div className="card login-panel">
        <h2 id="login-heading">Sign in</h2>
        <p>
          Sign in with your Google account to open your console -- your cases, your twin's live
          output, and your evaluation results.
        </p>
        <a className="login-button" href={api.loginUrl()}>
          Sign in with Google
        </a>
      </div>
    </section>
  )
}
