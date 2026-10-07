import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { api } from './api'

vi.mock('./api', async () => {
  const actual = await vi.importActual<typeof import('./api')>('./api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getCurrentClinician: vi.fn(),
      getConsoleResults: vi.fn(),
      logout: vi.fn(),
    },
  }
})

const FAKE_CLINICIAN = {
  clinicianId: 'c1',
  name: 'Dr. Test',
  email: 'doctor@example.com',
  consentStatus: 'granted',
}

describe('App', () => {
  beforeEach(() => {
    vi.mocked(api.getConsoleResults).mockResolvedValue([])
  })

  it('shows a sign-in screen when not logged in', async () => {
    vi.mocked(api.getCurrentClinician).mockResolvedValue(null)
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'ADDT Console' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('shows the intake/case view by default once logged in', async () => {
    vi.mocked(api.getCurrentClinician).mockResolvedValue(FAKE_CLINICIAN)
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Intake / Case' })).toBeInTheDocument()
  })

  it('switches to the review queue view on tab click', async () => {
    vi.mocked(api.getCurrentClinician).mockResolvedValue(FAKE_CLINICIAN)
    render(<App />)
    await screen.findByRole('heading', { name: 'Intake / Case' })

    fireEvent.click(screen.getByRole('button', { name: 'Review Queue' }))

    expect(screen.getByRole('heading', { name: 'Review Queue' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Intake / Case' })).not.toBeInTheDocument()
  })

  it('switches to the results view on tab click', async () => {
    vi.mocked(api.getCurrentClinician).mockResolvedValue(FAKE_CLINICIAN)
    render(<App />)
    await screen.findByRole('heading', { name: 'Intake / Case' })

    fireEvent.click(screen.getByRole('button', { name: 'Results' }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Evaluation Results' })).toBeInTheDocument()
    })
  })
})
