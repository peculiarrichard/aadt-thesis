import { useEffect, useState } from 'react'
import { api, type DoctorReport as DoctorReportData } from '../api'
import { DoctorReport } from '../components/DoctorReport'
import { ReviewSubmission } from './ReviewSubmission'

// Polls for the pending -> resolved transition (Phase X) -- the patient sees
// the twin's actual draft while pending, just clearly watermarked as
// unreviewed, per the explicit design decision not to withhold it.
export function PatientReportView({
  sessionId,
  clinicianId,
  onDone,
}: {
  sessionId: string
  clinicianId: string
  onDone: () => void
}) {
  const [pending, setPending] = useState(true)
  const [report, setReport] = useState<DoctorReportData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reviewed, setReviewed] = useState(false)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    async function poll() {
      try {
        const status = await api.getChatSession(sessionId)
        if (cancelled) return
        setPending(status.pending)
        setReport(status.report)
        if (status.pending) {
          timer = setTimeout(poll, 4000)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Could not load the result.')
        }
      }
    }

    poll()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [sessionId])

  if (error) return <p role="alert">{error}</p>
  if (report === null) return <p>Loading...</p>

  return (
    <section aria-labelledby="result-heading" className="card">
      <h2 id="result-heading">Your consult</h2>
      {pending ? (
        <p className="status-banner status-banner--pending">
          Waiting for Dr. {report.clinicianName}&rsquo;s review -- this is the twin&rsquo;s first
          draft, not yet final.
        </p>
      ) : (
        <p className="status-banner status-banner--resolved">
          Reviewed by Dr. {report.clinicianName} -- here&rsquo;s what to do.
        </p>
      )}
      <DoctorReport report={report} />
      {!pending && !reviewed && (
        <ReviewSubmission
          clinicianId={clinicianId}
          chatSessionId={sessionId}
          onDone={() => setReviewed(true)}
        />
      )}
      {!pending && (
        <button type="button" onClick={onDone}>
          Back to directory
        </button>
      )}
    </section>
  )
}
