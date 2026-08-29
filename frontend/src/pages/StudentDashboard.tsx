import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowIcon, SearchIcon, SparkIcon } from '../components/Icons'
import { ScholarshipCard } from '../components/ScholarshipCard'
import { useAuth } from '../context/AuthContext'
import { api } from '../lib/api'
import type { DiscoveryResponse, Scholarship, ScholarshipAssessment, ScholarshipList } from '../types'

interface SearchProfile {
  state: string
  education_level: string
  course: string
  course_year: string
  marks_percentage: string
  family_income_range: string
  categories: string
  message: string
}

const initialProfile: SearchProfile = {
  state: 'OD',
  education_level: 'UNDERGRADUATE',
  course: 'BTECH',
  course_year: '4',
  marks_percentage: '72',
  family_income_range: '250001_TO_400000',
  categories: '',
  message: 'Find scholarships for my technical degree.',
}

export function StudentDashboard() {
  const { user } = useAuth()
  const [profile, setProfile] = useState(initialProfile)
  const [catalog, setCatalog] = useState<Scholarship[]>([])
  const [discovery, setDiscovery] = useState<DiscoveryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadCatalog() {
      try {
        const response = await api<ScholarshipList>('/api/scholarships?limit=12')
        setCatalog(response.items)
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : 'Could not load scholarships')
      } finally {
        setLoading(false)
      }
    }
    void loadCatalog()
  }, [])

  const assessments = useMemo(() => {
    const map = new Map<string, ScholarshipAssessment>()
    discovery?.assessments.forEach((assessment) => {
      map.set(assessment.scholarship_version_id, assessment)
    })
    return map
  }, [discovery])

  async function handleDiscover(event: FormEvent) {
    event.preventDefault()
    setSearching(true)
    setError('')
    setNotice('')
    try {
      const response = await api<DiscoveryResponse>('/api/ai/discover', {
        method: 'POST',
        body: JSON.stringify({
          ...profile,
          course_year: Number(profile.course_year),
          marks_percentage: Number(profile.marks_percentage),
          categories: profile.categories
            .split(',')
            .map((value) => value.trim())
            .filter(Boolean),
          preferred_language: user?.preferred_language ?? 'en',
        }),
      })
      setDiscovery(response)
      setNotice(response.notice)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Search could not be completed')
    } finally {
      setSearching(false)
    }
  }

  async function saveScholarship(scholarshipId: string) {
    try {
      await api(`/api/student/saved-scholarships/${scholarshipId}`, { method: 'POST' })
      setNotice('Scholarship saved to your workspace.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save scholarship')
    }
  }

  const displayedScholarships = discovery?.candidates ?? catalog

  return (
    <main className="modern-workspace-page">
      <div className="modern-workspace-overlay"></div>
      <div className="modern-workspace-content">
        <section className="modern-workspace-intro section-pad">
          <div>
            <p className="modern-section-kicker">Student workspace</p>
            <h1>Hello, {user?.display_alias?.replace(/\s*\([^)]*\)\s*$/, '') ?? 'student'}.</h1>
            <p>Use your details to search for scholarships.</p>
          </div>
        </section>

        <section className="modern-discovery-shell section-pad">
          <div className="modern-assistant-panel modern-glass-card">
            <div className="modern-assistant-heading">
            <div><strong>Scholarship search</strong><small>Enter your details below</small></div>
          </div>
            <div className="modern-assistant-message">
              <p>Review each scholarship’s eligibility, deadline, and application instructions before applying.</p>
            </div>
            <form className="discovery-form modern-large-form" onSubmit={(event) => void handleDiscover(event)}>
            <div className="form-grid compact-grid">
              <label>State / UT
                <select value={profile.state} onChange={(e) => setProfile({ ...profile, state: e.target.value })}>
                  <option value="OD">Odisha</option><option value="MH">Maharashtra</option>
                  <option value="KA">Karnataka</option><option value="WB">West Bengal</option>
                  <option value="DL">Delhi</option>
                </select>
              </label>
              <label>Education level
                <select value={profile.education_level} onChange={(e) => setProfile({ ...profile, education_level: e.target.value })}>
                  <option value="UNDERGRADUATE">Undergraduate</option>
                  <option value="DIPLOMA">Diploma</option><option value="POSTGRADUATE">Postgraduate</option>
                </select>
              </label>
              <label>Course
                <select value={profile.course} onChange={(e) => setProfile({ ...profile, course: e.target.value })}>
                  <option value="BTECH">B.Tech</option><option value="BE">B.E.</option>
                  <option value="TECHNICAL_DIPLOMA">Technical diploma</option><option value="STEM">Other STEM</option>
                </select>
              </label>
              <label>Current year
                <input type="number" min="1" max="8" value={profile.course_year} onChange={(e) => setProfile({ ...profile, course_year: e.target.value })} />
              </label>
              <label>Marks percentage
                <input type="number" min="0" max="100" value={profile.marks_percentage} onChange={(e) => setProfile({ ...profile, marks_percentage: e.target.value })} />
              </label>
              <label>Family-income range
                <select value={profile.family_income_range} onChange={(e) => setProfile({ ...profile, family_income_range: e.target.value })}>
                  <option value="UP_TO_250000">Up to ₹2.5 lakh</option>
                  <option value="250001_TO_400000">₹2.5–4 lakh</option>
                  <option value="400001_TO_600000">₹4–6 lakh</option>
                  <option value="600001_TO_800000">₹6–8 lakh</option>
                  <option value="ABOVE_800000">Above ₹8 lakh</option>
                </select>
              </label>
            </div>
            <label>Optional categories
              <input placeholder="FIRST_GENERATION, WOMEN" value={profile.categories} onChange={(e) => setProfile({ ...profile, categories: e.target.value })} />
            </label>
            <label>What would you like help with?
              <textarea rows={3} value={profile.message} onChange={(e) => setProfile({ ...profile, message: e.target.value })} />
            </label>
            <button className="modern-button-primary button-full" type="submit" disabled={searching}>
              <SearchIcon /> {searching ? 'Searching scholarships…' : 'Find scholarships'}
            </button>
          </form>
          <p className="modern-sensitive-warning">Do not enter Aadhaar, PAN, bank details, passwords, or OTPs.</p>
        </div>

        <aside className="modern-workspace-side">
          <div className="modern-side-card modern-glass-card modern-dark-side">
            <span>Search</span><strong>Ready</strong>
            <p>Complete a search, review the details, and begin an application when ready.</p>
          </div>
          <Link className="modern-side-card modern-glass-card modern-link-side" to="/student/applications">
            <span>Applications</span><strong>View your timeline</strong><ArrowIcon />
          </Link>
          <div className="modern-side-card modern-glass-card">
            <span>Scholarship list</span><strong>{catalog.length} currently shown</strong>
            <p>Use the scholarship catalog to filter by provider, state, education level, or deadline.</p>
          </div>
        </aside>
      </section>

      <section className="modern-results-section section-pad" aria-live="polite">
        <div className="modern-results-heading">
          <div><p className="modern-section-kicker">{discovery ? 'Search results' : 'Scholarships'}</p>
            <h2>{discovery ? `${displayedScholarships.length} scholarships to review` : 'Browse scholarships'}</h2></div>
          <span>{loading ? 'Loading…' : `${displayedScholarships.length} shown`}</span>
        </div>
        {notice && <div className="notice-banner"><SparkIcon /><p>{notice}</p></div>}
        {error && <div className="error-banner" role="alert">{error}</div>}
        {!loading && displayedScholarships.length === 0 ? (
          <div className="empty-state"><SearchIcon /><h3>No scholarships found</h3><p>Try broadening your course or state information.</p></div>
        ) : (
          <div className="scholarship-grid">
            {displayedScholarships.map((scholarship) => (
              <ScholarshipCard
                key={scholarship.id}
                scholarship={scholarship}
                assessment={assessments.get(scholarship.version_id)}
                onSave={(id) => void saveScholarship(id)}
              />
            ))}
          </div>
        )}
      </section>
      </div>
    </main>
  )
}
