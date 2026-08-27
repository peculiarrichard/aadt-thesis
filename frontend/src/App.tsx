import { useState } from 'react'
import { IntakeCaseView } from './components/IntakeCaseView'
import { ReviewQueueView } from './components/ReviewQueueView'

// Layer 8 console shell (Section 5.8): two views, no router needed for just two tabs.
type View = 'intake' | 'queue'

function App() {
  const [view, setView] = useState<View>('intake')

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>ADDT Console</h1>
          <p className="app-tagline">Agentic Digital Twin -- clinician review console</p>
        </div>
      </header>
      <nav className="tab-nav" aria-label="Console views">
        <button type="button" aria-pressed={view === 'intake'} onClick={() => setView('intake')}>
          Intake / Case
        </button>
        <button type="button" aria-pressed={view === 'queue'} onClick={() => setView('queue')}>
          Review Queue
        </button>
      </nav>
      <main>{view === 'intake' ? <IntakeCaseView /> : <ReviewQueueView />}</main>
    </div>
  )
}

export default App
