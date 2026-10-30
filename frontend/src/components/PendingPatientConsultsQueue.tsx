import { useEffect, useState } from 'react'
import { api, type PendingChatDetail, type PendingChatSummary } from '../api'
import { DoctorReport } from './DoctorReport'

const DISPOSITION_OPTIONS = ['self-care advice', 'scheduled appointment', 'urgent referral']

// Doctor's review queue for patient-chat consults (Phase X) -- the same
// approve/correct/escalate mechanism as Consult Mode's feedback loop
// (ConsultPanel.tsx's FeedbackControls), applied to patient-originated
// sessions instead of her own ad-hoc ones.
export function PendingPatientConsultsQueue() {
  const [pending, setPending] = useState<PendingChatSummary[] | null>(null)
  const [selected, setSelected] = useState<PendingChatDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  function refresh() {
    api
      .listPendingPatientChats()
      .then(setPending)
      .catch((err) =>
        setError(err instanceof Error ? err.message : 'Could not load pending consults.'),
      )
  }

  useEffect(() => {
    refresh()
  }, [])

  async function openDetail(sessionId: string) {
    setSelected(await api.getPendingPatientChat(sessionId))
  }

  if (error) return <p role="alert">{error}</p>

  if (selected) {
    return (
      <PendingChatReview
        chat={selected}
        onDone={() => {
          setSelected(null)
          refresh()
        }}
      />
    )
  }

  return (
    <section aria-labelledby="pending-patient-chats-heading" className="card">
      <h2 id="pending-patient-chats-heading">Pending patient consults</h2>
      {pending === null && <p>Loading...</p>}
      {pending !== null && pending.length === 0 && <p>Nothing awaiting your review.</p>}
      {pending !== null && pending.length > 0 && (
        <ul className="queue-list">
          {pending.map((chat) => (
            <li key={chat.sessionId} className="queue-item">
              <button type="button" onClick={() => openDetail(chat.sessionId)}>
                <span className="queue-item-title">{chat.patientUsername}</span>
                <span className="queue-item-meta">{chat.submittedForReviewAt ?? 'just now'}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function PendingChatReview({ chat, onDone }: { chat: PendingChatDetail; onDone: () => void }) {
  const [showCorrection, setShowCorrection] = useState(false)
  const [correctedDisposition, setCorrectedDisposition] = useState('')
  const [correctedReasoning, setCorrectedReasoning] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function act(action: 'approved' | 'escalated_review') {
    setSubmitting(true)
    try {
      await api.reviewPatientChat(chat.sessionId, action)
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record your decision.')
    } finally {
      setSubmitting(false)
    }
  }

  async function submitCorrection(event: React.FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api.reviewPatientChat(chat.sessionId, 'corrected', {
        correctedDisposition,
        correctedReasoning,
      })
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record your correction.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section aria-labelledby="pending-chat-detail-heading" className="card">
      <h2 id="pending-chat-detail-heading">Reviewing: {chat.patientUsername}</h2>

      <div className="chat-transcript">
        {chat.transcript.map((message, index) => (
          <div key={index} className={`chat-bubble chat-bubble--${message.role}`}>
            {message.content}
          </div>
        ))}
      </div>

      {chat.report && <DoctorReport report={chat.report} />}

      {error && <p role="alert">{error}</p>}

      {showCorrection ? (
        <form onSubmit={submitCorrection} className="case-form">
          <div className="field">
            <label htmlFor="pending-corrected-disposition">What should the disposition be?</label>
            <select
              id="pending-corrected-disposition"
              value={correctedDisposition}
              onChange={(e) => setCorrectedDisposition(e.target.value)}
              required
            >
              <option value="" disabled>
                Select a disposition
              </option>
              {DISPOSITION_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="pending-corrected-reasoning">
              Your reasoning / plan for the patient
            </label>
            <textarea
              id="pending-corrected-reasoning"
              value={correctedReasoning}
              onChange={(e) => setCorrectedReasoning(e.target.value)}
              rows={3}
            />
          </div>
          <button type="submit" disabled={submitting}>
            {submitting ? 'Saving...' : 'Submit correction'}
          </button>
        </form>
      ) : (
        <div className="queue-actions">
          <button type="button" onClick={() => act('approved')} disabled={submitting}>
            Approve
          </button>
          <button type="button" onClick={() => setShowCorrection(true)} disabled={submitting}>
            Correct it
          </button>
          <button type="button" onClick={() => act('escalated_review')} disabled={submitting}>
            Escalate to specialist
          </button>
        </div>
      )}
    </section>
  )
}
