import { useEffect, useState } from 'react'
import { api, type TwinProfile } from '../api'

// The doctor's own view of her twin's profile/stats (Phase V) -- the same
// shape patients see on the directory, plus edit access to the fields she
// controls.
export function TwinProfilePanel() {
  const [profile, setProfile] = useState<TwinProfile | null>(null)
  const [specialty, setSpecialty] = useState('')
  const [hospital, setHospital] = useState('')
  const [location, setLocation] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getMyTwinProfile().then((p) => {
      setProfile(p)
      setSpecialty(p.specialty ?? '')
      setHospital(p.hospital ?? '')
      setLocation(p.location ?? '')
    })
  }, [])

  async function handleSave(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      setProfile(await api.updateMyTwinProfile({ specialty, hospital, location }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save your profile.')
    } finally {
      setSaving(false)
    }
  }

  if (profile === null) return <p>Loading...</p>

  return (
    <section aria-labelledby="twin-profile-heading" className="card">
      <h2 id="twin-profile-heading">Your twin&rsquo;s profile</h2>
      <p className="field-note">This is what patients see on the patient-facing directory.</p>
      <dl className="doctor-report__clerical">
        <div>
          <dt>Patients attended</dt>
          <dd>{profile.patientsAttended}</dd>
        </div>
        <div>
          <dt>Twin confidence</dt>
          <dd>
            {profile.averageConfidence !== null
              ? `${Math.round(profile.averageConfidence * 100)}%`
              : 'Not enough data yet'}
          </dd>
        </div>
        <div>
          <dt>Reviews</dt>
          <dd>
            {profile.reviewCount > 0
              ? `${profile.averageRating?.toFixed(1)} / 5 (${profile.reviewCount})`
              : 'No reviews yet'}
          </dd>
        </div>
      </dl>
      <form onSubmit={handleSave}>
        <div className="field">
          <label htmlFor="profile-specialty">Specialty</label>
          <input
            id="profile-specialty"
            type="text"
            value={specialty}
            onChange={(e) => setSpecialty(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="profile-hospital">Hospital</label>
          <input
            id="profile-hospital"
            type="text"
            value={hospital}
            onChange={(e) => setHospital(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="profile-location">Location</label>
          <input
            id="profile-location"
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />
        </div>
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={saving}>
          {saving ? 'Saving...' : 'Save'}
        </button>
      </form>
    </section>
  )
}
