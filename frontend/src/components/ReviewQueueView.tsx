import { useState } from 'react'
import { dispositionBadgeClass, dispositionLabel } from '../dispositionDisplay'
import { buildInitialReviewQueue } from '../mockData'
import type { ClinicianAction, ReviewQueueItem } from '../types'

// Layer 8 review queue/dashboard (Section 5.8), built against mock data (task 11).
export function ReviewQueueView() {
  const [items, setItems] = useState<ReviewQueueItem[]>(buildInitialReviewQueue)

  function setAction(interactionId: string, action: ClinicianAction) {
    setItems((current) =>
      current.map((item) =>
        item.interactionId === interactionId ? { ...item, clinicianAction: action } : item,
      ),
    )
  }

  const decided = items.filter((item) => item.clinicianAction !== 'pending')
  const rate = (action: ClinicianAction) =>
    decided.length === 0
      ? 0
      : decided.filter((item) => item.clinicianAction === action).length / decided.length

  return (
    <section aria-labelledby="queue-heading" className="card">
      <h2 id="queue-heading">Review Queue</h2>

      <dl className="stat-grid">
        <div className="stat-tile">
          <dt>Acceptance rate</dt>
          <dd>{(rate('approved') * 100).toFixed(0)}%</dd>
        </div>
        <div className="stat-tile">
          <dt>Correction rate</dt>
          <dd>{(rate('corrected') * 100).toFixed(0)}%</dd>
        </div>
        <div className="stat-tile">
          <dt>Escalation rate</dt>
          <dd>{(rate('escalated_review') * 100).toFixed(0)}%</dd>
        </div>
      </dl>

      <h3>Queue</h3>
      <ul className="queue-list">
        {items.map((item) => (
          <li key={item.interactionId} className="queue-item">
            <div className="queue-item-top">
              <span className="queue-item-title">{item.caseLabel}</span>
              <span className={`status-pill status-pill--${item.clinicianAction}`}>
                {item.clinicianAction.replace('_', ' ')}
              </span>
            </div>
            <div className="queue-item-meta">
              {item.result.escalated ? (
                <span className="badge badge--escalated">Escalated by the twin</span>
              ) : (
                <span className={dispositionBadgeClass(item.result.disposition!)}>
                  {dispositionLabel(item.result.disposition!)}
                </span>
              )}{' '}
              -- confidence {item.result.confidence.toFixed(2)} -- status: {item.clinicianAction}
            </div>
            <div className="queue-actions">
              <button type="button" onClick={() => setAction(item.interactionId, 'approved')}>
                Approve
              </button>
              <button type="button" onClick={() => setAction(item.interactionId, 'corrected')}>
                Correct
              </button>
              <button
                type="button"
                onClick={() => setAction(item.interactionId, 'escalated_review')}
              >
                Handle directly
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
