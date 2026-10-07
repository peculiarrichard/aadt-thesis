import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api, type StructuredDraft } from '../api'
import { DraftReview } from './DraftReview'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual,
    api: { ...actual.api, confirmDraft: vi.fn() },
  }
})

const BASE_DRAFT: StructuredDraft = {
  caseText: 'Fever and chills.',
  initialImpression: null,
  questionsToAsk: [],
  examinationOrChecks: null,
  factorsTowardReferral: null,
  factorsAgainstReferral: null,
  flipUp: null,
  flipDown: null,
  redFlags: null,
  confidence: null,
  generalRule: null,
  disposition: 'self-care advice',
  dispositionReason: null,
  redactionSummary: {},
  llmFlagged: false,
  llmFlagDetails: null,
}

describe('DraftReview', () => {
  it('disables saving until the attestation checkbox is checked', () => {
    render(<DraftReview draft={BASE_DRAFT} sourceType="walkthrough" onSaved={() => {}} />)

    expect(screen.getByRole('button', { name: 'Save case' })).toBeDisabled()

    fireEvent.click(
      screen.getByLabelText(/I confirm this case does not reference a real, identifiable patient/),
    )

    expect(screen.getByRole('button', { name: 'Save case' })).not.toBeDisabled()
  })

  it('shows the LLM flag banner when the draft was flagged', () => {
    render(
      <DraftReview
        draft={{ ...BASE_DRAFT, llmFlagged: true, llmFlagDetails: 'References a named clinic.' }}
        sourceType="walkthrough"
        onSaved={() => {}}
      />,
    )

    expect(screen.getByText(/References a named clinic\./)).toBeInTheDocument()
  })

  it('does not show a flag banner when nothing was flagged', () => {
    render(<DraftReview draft={BASE_DRAFT} sourceType="walkthrough" onSaved={() => {}} />)

    expect(screen.queryByText(/Automatic privacy check/)).not.toBeInTheDocument()
  })

  it('saves with attestation_confirmed true once confirmed', async () => {
    vi.mocked(api.confirmDraft).mockResolvedValue({ caseId: 'case-1', redactionSummary: {} })
    const onSaved = vi.fn()
    render(<DraftReview draft={BASE_DRAFT} sourceType="walkthrough" onSaved={onSaved} />)

    fireEvent.click(
      screen.getByLabelText(/I confirm this case does not reference a real, identifiable patient/),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Save case' }))

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith('case-1'))
    expect(api.confirmDraft).toHaveBeenCalledWith(
      expect.objectContaining({ caseText: 'Fever and chills.' }),
      'walkthrough',
      true,
    )
  })
})
