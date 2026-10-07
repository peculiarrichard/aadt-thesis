import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { ConsentGate } from './ConsentGate'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual,
    api: { ...actual.api, grantConsent: vi.fn() },
  }
})

describe('ConsentGate', () => {
  it('hides children until consent is granted', () => {
    render(
      <ConsentGate subjectType="walkthrough_recording" title="Consent" description="desc">
        <p>protected content</p>
      </ConsentGate>,
    )

    expect(screen.queryByText('protected content')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'I consent' })).toBeInTheDocument()
  })

  it('reveals children and records consent once granted', async () => {
    vi.mocked(api.grantConsent).mockResolvedValue(undefined)
    render(
      <ConsentGate subjectType="patient_data_batch" title="Consent" description="desc">
        <p>protected content</p>
      </ConsentGate>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'I consent' }))

    expect(await screen.findByText('protected content')).toBeInTheDocument()
    expect(api.grantConsent).toHaveBeenCalledWith('patient_data_batch', 'desc', undefined)
  })

  it('shows an error and keeps children hidden if recording consent fails', async () => {
    vi.mocked(api.grantConsent).mockRejectedValue(new Error('server down'))
    render(
      <ConsentGate subjectType="walkthrough_recording" title="Consent" description="desc">
        <p>protected content</p>
      </ConsentGate>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'I consent' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('server down')
    expect(screen.queryByText('protected content')).not.toBeInTheDocument()
  })
})
