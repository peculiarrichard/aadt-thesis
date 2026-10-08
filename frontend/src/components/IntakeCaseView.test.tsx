import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { IntakeCaseView } from './IntakeCaseView'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return {
    ...actual,
    api: {
      ...actual.api,
      getConsoleCases: vi.fn(),
      getCaseResult: vi.fn(),
    },
  }
})

const CASES = [
  {
    caseId: 'id-1',
    externalCaseRef: 'S1-C02',
    presentingSummary: 'RDT positive for malaria, uncomplicated.',
    doctorDisposition: 'self_care_advice',
    sourceType: 'walkthrough',
  },
  {
    caseId: 'id-2',
    externalCaseRef: 'S2-C06',
    presentingSummary: 'Thunderclap headache.',
    doctorDisposition: 'urgent_referral',
    sourceType: 'walkthrough',
  },
]

const NON_ESCALATED_RESULT = {
  configLabel: 'guideline_plus_precedent',
  draftDisposition: 'self_care_advice',
  disposition: 'self_care_advice',
  confidence: 0.8,
  escalated: false,
  escalationReasons: [],
  precedentCaseRefs: ['S1-C05'],
  explanation: {
    matchedConditions: ['MALARIA'],
    guidelineEvidence: ['MALARIA: fever'],
    constraintRulesTriggered: [],
    reasoningSummary: 'Guideline evidence found for: MALARIA.',
  },
}

const ESCALATED_RESULT = {
  ...NON_ESCALATED_RESULT,
  disposition: null,
  escalated: true,
  escalationReasons: ['constraint_violation'],
  explanation: {
    ...NON_ESCALATED_RESULT.explanation,
    constraintRulesTriggered: ['RF-003'],
    reasoningSummary: 'Escalated: case text tripped red flag rule(s) RF-003.',
  },
}

describe('IntakeCaseView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getConsoleCases).mockResolvedValue(CASES)
  })

  it('shows the first real case by default, running the twin only after the button is clicked', async () => {
    vi.mocked(api.getCaseResult).mockResolvedValue(NON_ESCALATED_RESULT)
    render(<IntakeCaseView />)

    expect(await screen.findByText(/RDT positive for malaria/)).toBeInTheDocument()
    expect(api.getCaseResult).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: /run twin on this case/i }))

    expect(await screen.findByText('Self-care advice')).toBeInTheDocument()
    expect(api.getCaseResult).toHaveBeenCalledWith('id-1')
  })

  it('withholds a disposition and shows an escalation notice for an escalated result', async () => {
    vi.mocked(api.getCaseResult).mockResolvedValue(ESCALATED_RESULT)
    render(<IntakeCaseView />)
    await screen.findByText(/RDT positive for malaria/)

    fireEvent.change(screen.getByLabelText('Select a case'), { target: { value: 'id-2' } })
    fireEvent.click(screen.getByRole('button', { name: /run twin on this case/i }))

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/escalated for review/i)
    })
    expect(screen.queryByText('Urgent referral')).not.toBeInTheDocument()
    expect(screen.getByText(/Constraint rules triggered/)).toHaveTextContent('RF-003')
  })

  it('runs the twin on every case, one at a time, from a single button', async () => {
    vi.mocked(api.getCaseResult).mockResolvedValue(NON_ESCALATED_RESULT)
    render(<IntakeCaseView />)
    await screen.findByText(/RDT positive for malaria/)

    fireEvent.click(screen.getByRole('button', { name: /run twin on all cases/i }))

    await waitFor(() => {
      expect(api.getCaseResult).toHaveBeenCalledWith('id-1')
      expect(api.getCaseResult).toHaveBeenCalledWith('id-2')
    })
    expect(api.getCaseResult).toHaveBeenCalledTimes(2)

    fireEvent.change(screen.getByLabelText('Select a case'), { target: { value: 'id-2' } })
    expect(await screen.findByText('Self-care advice')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /run twin on this case/i })).not.toBeInTheDocument()
  })
})
