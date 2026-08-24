import { useRef, useState } from 'react'

/**
 * Push-to-record control (Section 6.1): the doctor explicitly starts and stops
 * recording per patient. No passive or continuous listening — recording only
 * happens between a start click and a stop click.
 *
 * Not wired into a console page yet: the intake/case view composition belongs
 * to the console shell (docs/build_plan.md task 11), not yet built. This
 * component is scaffolded and tested standalone.
 *
 * Not switched on for real consultations: capturing a live consultation
 * captures the patient's voice too, which needs patient consent and ethics
 * clearance (Section 6.1, docs/build_plan.md Phase 1) that this project doesn't
 * have yet. This component is a code-path scaffold only.
 */

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
        aria-pressed={state === 'recording'}
        onClick={state === 'recording' ? stop : start}
      >
        {state === 'recording' ? 'Stop recording' : 'Start recording'}
      </button>
      {errorMessage && <p role="alert">{errorMessage}</p>}
    </div>
  )
}
