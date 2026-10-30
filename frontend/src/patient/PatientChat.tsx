import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

interface ChatMessage {
  role: 'patient' | 'twin'
  content: string
}

type IncomingMessage =
  | { type: 'question'; content: string }
  | { type: 'history'; messages: ChatMessage[] }
  | { type: 'submitted_for_review' }

// Real-time chat intake (Phase W) -- the twin asks history-taking questions
// one at a time; once it signals it's gathered enough, the server runs the
// twin and this view hands off to the pending/resolved report (PatientApp).
export function PatientChat({
  sessionId,
  onSubmitted,
}: {
  sessionId: string
  onSubmitted: () => void
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [connected, setConnected] = useState(false)
  const [waitingForTwin, setWaitingForTwin] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const socketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const socket = new WebSocket(api.chatSocketUrl(sessionId))
    socketRef.current = socket

    socket.onopen = () => setConnected(true)
    socket.onerror = () => setError('Lost connection to the twin.')
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data) as IncomingMessage
      if (data.type === 'question') {
        setMessages((prev) => [...prev, { role: 'twin', content: data.content }])
        setWaitingForTwin(false)
      } else if (data.type === 'history') {
        setMessages(data.messages)
        setWaitingForTwin(false)
      } else if (data.type === 'submitted_for_review') {
        onSubmitted()
      }
    }

    return () => socket.close()
  }, [sessionId, onSubmitted])

  function sendAnswer(event: React.FormEvent) {
    event.preventDefault()
    if (!draft.trim() || !socketRef.current) return
    setMessages((prev) => [...prev, { role: 'patient', content: draft }])
    socketRef.current.send(JSON.stringify({ content: draft }))
    setDraft('')
    setWaitingForTwin(true)
  }

  return (
    <section aria-labelledby="chat-heading" className="card">
      <h2 id="chat-heading">Chat with the twin</h2>
      <p className="field-note">Simulated consult -- answer as your made-up patient would.</p>
      {!connected && !error && <p>Connecting...</p>}
      {error && <p role="alert">{error}</p>}
      <div className="chat-transcript">
        {messages.map((message, index) => (
          <div key={index} className={`chat-bubble chat-bubble--${message.role}`}>
            {message.content}
          </div>
        ))}
        {waitingForTwin && connected && <div className="chat-bubble chat-bubble--twin">...</div>}
      </div>
      <form onSubmit={sendAnswer} className="chat-input-row">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={!connected || waitingForTwin}
          placeholder="Type your answer..."
        />
        <button type="submit" disabled={!connected || waitingForTwin || !draft.trim()}>
          Send
        </button>
      </form>
    </section>
  )
}
