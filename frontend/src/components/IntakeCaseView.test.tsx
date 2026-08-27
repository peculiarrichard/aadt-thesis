import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { IntakeCaseView } from './IntakeCaseView'

describe('IntakeCaseView', () => {
  it('shows the first mock case by default with its disposition and confidence', () => {
    render(<IntakeCaseView />)

    expect(screen.getByText(/RDT positive for malaria/)).toBeInTheDocument()
    expect(screen.getByText('Manage at primary care')).toBeInTheDocument()
  })

  it('withholds a disposition and shows an escalation notice for an escalated case', () => {
    render(<IntakeCaseView />)

    fireEvent.change(screen.getByLabelText('Select a case'), {
      target: { value: 'SC-012' },
    })

    expect(screen.getByRole('status')).toHaveTextContent(/escalated for review/i)
    expect(screen.queryByText('Refer (urgent/emergency)')).not.toBeInTheDocument()
    expect(screen.getByText(/Constraint rules triggered/)).toHaveTextContent('RF-003')
  })

  it('shows a note flagging the baseline under-triage for SC-006', () => {
    render(<IntakeCaseView />)

    fireEvent.change(screen.getByLabelText('Select a case'), {
      target: { value: 'SC-006' },
    })

    expect(screen.getByRole('note')).toHaveTextContent(/under-triages/i)
  })
})
