import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { TwinBuildPanel } from './TwinBuildPanel'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual,
    api: { ...actual.api, getTwinStatus: vi.fn(), buildTwin: vi.fn() },
  }
})

describe('TwinBuildPanel', () => {
  beforeEach(() => {
    vi.mocked(api.buildTwin).mockReset()
  })

  it('shows progress and disables build when below threshold', async () => {
    vi.mocked(api.getTwinStatus).mockResolvedValue({
      qualifyingCaseCount: 5,
      minCasesRequired: 20,
      readyToBuild: false,
      alreadyBuilt: false,
    })

    render(<TwinBuildPanel />)

    expect(await screen.findByText('5 / 20 cases')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /build my twin/i })).not.toBeInTheDocument()
    expect(screen.getByText(/add 15 more case/i)).toBeInTheDocument()
  })

  it('allows building once the threshold is met', async () => {
    vi.mocked(api.getTwinStatus).mockResolvedValue({
      qualifyingCaseCount: 20,
      minCasesRequired: 20,
      readyToBuild: true,
      alreadyBuilt: false,
    })
    vi.mocked(api.buildTwin).mockResolvedValue({ embeddedCount: 20 })

    render(<TwinBuildPanel />)

    const button = await screen.findByRole('button', { name: 'Build my twin' })
    fireEvent.click(button)

    await waitFor(() => {
      expect(screen.getByText('Twin built from 20 case(s).')).toBeInTheDocument()
    })
    expect(api.buildTwin).toHaveBeenCalledOnce()
  })
})
