import { useEffect, useState } from 'react'
import { api, type TwinProfile } from '../api'

// Single clinician today, shaped as a list so it generalizes later without
// an API change (Phase V).
export function TwinDirectory({ onSelect }: { onSelect: (clinicianId: string) => void }) {
  const [twins, setTwins] = useState<TwinProfile[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listTwinDirectory()
      .then(setTwins)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load the directory.'))
  }, [])

  if (error) return <p role="alert">{error}</p>
  if (twins === null) return <p>Loading...</p>
  if (twins.length === 0) return <p>No doctors&rsquo; twins are available yet.</p>

  return (
    <section aria-labelledby="directory-heading" className="card">
      <h2 id="directory-heading">Choose a doctor&rsquo;s digital twin</h2>
      <p className="field-note">Simulated patients only -- for demonstration, not real care.</p>
      <div className="twin-directory">
        {twins.map((twin) => (
          <article key={twin.clinicianId} className="twin-card">
            <h3>{twin.name}</h3>
            <dl className="doctor-report__clerical">
              <div>
                <dt>Specialty</dt>
                <dd>{twin.specialty ?? 'Not specified'}</dd>
              </div>
              <div>
                <dt>Hospital</dt>
                <dd>{twin.hospital ?? 'Not specified'}</dd>
              </div>
              <div>
                <dt>Location</dt>
                <dd>{twin.location ?? 'Not specified'}</dd>
              </div>
              <div>
                <dt>Patients attended</dt>
                <dd>{twin.patientsAttended}</dd>
              </div>
              <div>
                <dt>Twin confidence</dt>
                <dd>
                  {twin.averageConfidence !== null
                    ? `${Math.round(twin.averageConfidence * 100)}%`
                    : 'Not enough data yet'}
                </dd>
              </div>
              <div>
                <dt>Reviews</dt>
                <dd>
                  {twin.reviewCount > 0
                    ? `${twin.averageRating?.toFixed(1)} / 5 (${twin.reviewCount})`
                    : 'No reviews yet'}
                </dd>
              </div>
            </dl>
            <button type="button" onClick={() => onSelect(twin.clinicianId)}>
              Consult this twin
            </button>
          </article>
        ))}
      </div>
    </section>
  )
}
