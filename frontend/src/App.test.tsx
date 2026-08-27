import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders the console heading', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'ADDT Console' })).toBeInTheDocument()
  })

  it('shows the intake/case view by default', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'Intake / Case' })).toBeInTheDocument()
  })

  it('switches to the review queue view on tab click', () => {
    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Review Queue' }))

    expect(screen.getByRole('heading', { name: 'Review Queue' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Intake / Case' })).not.toBeInTheDocument()
  })
})
