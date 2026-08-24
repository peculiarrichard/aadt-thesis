import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PushToRecordButton } from './PushToRecordButton'

class MockMediaRecorder {
  mimeType = 'audio/webm'
  ondataavailable: ((event: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null

  constructor(_stream: MediaStream) {}

  start() {
    this.ondataavailable?.({ data: new Blob(['fake audio chunk']) })
  }

  stop() {
    this.onstop?.()
  }
}

function mockStream() {
  const track = { stop: vi.fn() }
  return { getTracks: () => [track], _track: track } as unknown as MediaStream & {
    _track: { stop: ReturnType<typeof vi.fn> }
  }
}

describe('PushToRecordButton', () => {
  let getUserMedia: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.stubGlobal('MediaRecorder', MockMediaRecorder)
    getUserMedia = vi.fn().mockResolvedValue(mockStream())
    Object.defineProperty(navigator, 'mediaDevices', {
      value: { getUserMedia },
      writable: true,
      configurable: true,
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('starts idle, showing "Start recording"', () => {
    render(<PushToRecordButton onRecordingComplete={vi.fn()} />)

    const button = screen.getByRole('button', { name: 'Start recording' })
    expect(button).toHaveAttribute('aria-pressed', 'false')
  })

  it('requests the microphone and switches to recording state on start', async () => {
    render(<PushToRecordButton onRecordingComplete={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Start recording' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Stop recording' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
    })
    expect(getUserMedia).toHaveBeenCalledWith({ audio: true })
  })

  it('calls onRecordingComplete with a Blob and returns to idle on stop', async () => {
    const onRecordingComplete = vi.fn()
    render(<PushToRecordButton onRecordingComplete={onRecordingComplete} />)

    fireEvent.click(screen.getByRole('button', { name: 'Start recording' }))
    await waitFor(() => screen.getByRole('button', { name: 'Stop recording' }))

    fireEvent.click(screen.getByRole('button', { name: 'Stop recording' }))

    expect(onRecordingComplete).toHaveBeenCalledTimes(1)
    expect(onRecordingComplete.mock.calls[0][0]).toBeInstanceOf(Blob)
    expect(screen.getByRole('button', { name: 'Start recording' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('shows an error and stays idle if microphone access is denied', async () => {
    getUserMedia.mockRejectedValueOnce(new Error('Permission denied'))
    render(<PushToRecordButton onRecordingComplete={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Start recording' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/could not access the microphone/i)
    })
    expect(screen.getByRole('button', { name: 'Start recording' })).toBeInTheDocument()
  })
})
