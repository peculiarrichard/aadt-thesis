import { useState } from 'react'
import { api } from '../api'

// One review per resolved chat session (Phase V) -- shown once the doctor
// has acted, not before.
export function ReviewSubmission({
  clinicianId,
  chatSessionId,
  onDone,
}: {
  clinicianId: string
  chatSessionId: string
  onDone: () => void
}) {
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api.submitReview(clinicianId, chatSessionId, rating, comment || undefined)
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not submit your review.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="case-form">
      <div className="field">
        <label htmlFor="review-rating">Rate this consult (1-5)</label>
        <input
          id="review-rating"
          type="number"
          min={1}
          max={5}
          value={rating}
          onChange={(e) => setRating(Number(e.target.value))}
        />
      </div>
      <div className="field">
        <label htmlFor="review-comment">Comment (optional)</label>
        <textarea
          id="review-comment"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={2}
        />
      </div>
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={submitting}>
        {submitting ? 'Submitting...' : 'Submit review'}
      </button>
    </form>
  )
}
