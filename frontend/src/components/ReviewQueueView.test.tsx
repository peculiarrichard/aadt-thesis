import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ReviewQueueView } from './ReviewQueueView'

describe('ReviewQueueView', () => {
  it('renders every mock queue item', () => {
    render(<ReviewQueueView />)

    expect(screen.getAllByRole('listitem')).toHaveLength(4)
  })

  it('computes acceptance/correction/escalation rates from decided items only', () => {
    render(<ReviewQueueView />)

    // 3 decided items seeded (1 approved, 1 corrected, 1 escalated_review), 1 pending excluded.
    expect(screen.getByText('Acceptance rate').nextElementSibling).toHaveTextContent('33%')
    expect(screen.getByText('Correction rate').nextElementSibling).toHaveTextContent('33%')
    expect(screen.getByText('Escalation rate').nextElementSibling).toHaveTextContent('33%')
  })

  it('updates an item and the dashboard when the doctor approves a pending case', () => {
    render(<ReviewQueueView />)

    const pendingItem = screen.getByText(/status: pending/).closest('li')!
    fireEvent.click(within(pendingItem).getByRole('button', { name: 'Approve' }))

    expect(within(pendingItem).getByText(/status: approved/)).toBeInTheDocument()
    expect(screen.getByText('Acceptance rate').nextElementSibling).toHaveTextContent('50%')
  })
})
