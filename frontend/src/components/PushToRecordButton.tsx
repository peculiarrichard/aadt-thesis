import { useRef, useState } from 'react'

// Push-to-record control (Section 6.1): explicit start/stop only, no passive
// listening. Not switched on for real consultations -- see docs/build_plan.md.
type RecordingState = 'idle' | 'recording' | 'error'

interface PushToRecordButtonProps {
  onRecordingComplete: (blob: Blob) => void
}

export function PushToRecordButton({ onRecordingComplete }: PushToRecordButtonProps) {
  const [state, setState] = useState<RecordingState>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  async function start() {
    setErrorMessage(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data)
        }
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType })
        onRecordingComplete(blob)
        for (const track of stream.getTracks()) {
          track.stop()
        }
      }

      recorder.start()
      mediaRecorderRef.current = recorder
      setState('recording')
    } catch {
      setErrorMessage('Could not access the microphone. Check browser permissions.')
      setState('error')
    }
  }

  function stop() {
    mediaRecorderRef.current?.stop()
    setState('idle')
  }

  return (
    <div>
      <button
        type="button"
        className="record-btn"
        aria-pressed={state === 'recording'}
        onClick={state === 'recording' ? stop : start}
      >
        <span className="record-dot" aria-hidden="true" />
        {state === 'recording' ? 'Stop recording' : 'Start recording'}
      </button>
      {errorMessage && <p role="alert">{errorMessage}</p>}
    </div>
  )
}
