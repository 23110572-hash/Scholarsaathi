import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowIcon, BookmarkIcon, SearchIcon, SparkIcon } from '../components/Icons'
import { ScholarshipCard } from '../components/ScholarshipCard'
import { useAuth } from '../context/AuthContext'
import { api } from '../lib/api'
import type {
  DiscoveryResponse,
  Scholarship,
  ScholarshipAssessment,
  ScholarshipList,
  StudentProfile,
} from '../types'

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

const emptySearchProfile: SearchProfile = {
  state: '',
  education_level: '',
  course: '',
  course_year: '',
  marks_percentage: '',
  family_income_range: '',
  categories: '',
  message: '',
}

/** Seeds the search form from the saved profile so details are entered once, not retyped. */
function searchProfileFromStudentProfile(profile: StudentProfile): SearchProfile {
  return {
    state: profile.state_code ?? '',
    education_level: profile.education_level ?? '',
    course: profile.course ?? '',
    course_year: profile.course_year === null ? '' : String(profile.course_year),
    marks_percentage: profile.marks_percentage === null ? '' : String(profile.marks_percentage),
    family_income_range: profile.family_income_range ?? '',
    categories: profile.categories.join(', '),
    message: '',
  }
}

const STATE_OPTIONS = [
  { value: 'OD', label: 'Odisha' },
  { value: 'MH', label: 'Maharashtra' },
  { value: 'KA', label: 'Karnataka' },
  { value: 'WB', label: 'West Bengal' },
  { value: 'DL', label: 'Delhi' },
]

export function StudentDashboard() {
  const { user } = useAuth()
  const [profile, setProfile] = useState(emptySearchProfile)
  const [studentProfile, setStudentProfile] = useState<StudentProfile | null>(null)
  const [catalog, setCatalog] = useState<Scholarship[]>([])
  const [saved, setSaved] = useState<Scholarship[]>([])
  const [discovery, setDiscovery] = useState<DiscoveryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [savingId, setSavingId] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      // Each panel degrades independently: a failing saved list should not blank the catalog.
      const [catalogResult, savedResult, profileResult] = await Promise.allSettled([
        api<ScholarshipList>('/api/scholarships?limit=12'),
        api<ScholarshipList>('/api/student/saved-scholarships'),
        api<StudentProfile>('/api/student/profile'),
      ])
      if (cancelled) return

      if (catalogResult.status === 'fulfilled') {
        setCatalog(catalogResult.value.items)
      } else {
        setError('Could not load scholarships')
      }
      if (savedResult.status === 'fulfilled') {
        setSaved(savedResult.value.items)
      }
      if (profileResult.status === 'fulfilled') {
        setStudentProfile(profileResult.value)
        setProfile(searchProfileFromStudentProfile(profileResult.value))
      }
      setLoading(false)
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  const assessments = useMemo(() => {
    const map = new Map<string, ScholarshipAssessment>()
    discovery?.assessments.forEach((assessment) => {
      map.set(assessment.scholarship_version_id, assessment)
    })
    return map
  }, [discovery])

  const savedIds = useMemo(() => new Set(saved.map((item) => item.id)), [saved])

  async function handleDiscover(event: FormEvent) {
    event.preventDefault()
    setSearching(true)
    setError('')
    setNotice('')
    try {
      const response = await api<DiscoveryResponse>('/api/ai/discover', {
        method: 'POST',
        body: JSON.stringify({
          message: profile.message.trim() || undefined,
          state: profile.state || undefined,
          education_level: profile.education_level || undefined,
          course: profile.course || undefined,
          course_year: profile.course_year ? Number(profile.course_year) : undefined,
          marks_percentage: profile.marks_percentage
            ? Number(profile.marks_percentage)
            : undefined,
          family_income_range: profile.family_income_range || undefined,
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
    setSavingId(scholarshipId)
    setError('')
    try {
      await api(`/api/student/saved-scholarships/${scholarshipId}`, { method: 'POST' })
      const refreshed = await api<ScholarshipList>('/api/student/saved-scholarships')
      setSaved(refreshed.items)
      setNotice('Scholarship saved to your workspace.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save scholarship')
    } finally {
      setSavingId('')
    }
  }

  async function unsaveScholarship(scholarshipId: string) {
    setSavingId(scholarshipId)
    setError('')
    try {
      await api(`/api/student/saved-scholarships/${scholarshipId}`, { method: 'DELETE' })
      setSaved((current) => current.filter((item) => item.id !== scholarshipId))
      setNotice('Removed from your saved list.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not remove scholarship')
    } finally {
      setSavingId('')
    }
  }

  const displayedScholarships = discovery?.candidates ?? catalog
  const greeting = user?.display_alias?.replace(/\s*\([^)]*\)\s*$/, '') ?? 'student'
  const completeness = studentProfile?.completeness ?? 0
  const profileInitial = (studentProfile?.full_name || studentProfile?.display_alias || greeting)
    .trim()
    .charAt(0)
    .toUpperCase()

  return (
    <main className="modern-workspace-page">
      <div className="modern-workspace-overlay"></div>
      <div className="modern-workspace-content">
        <section className="modern-workspace-intro section-pad">
          <div>
            <p className="modern-section-kicker">Student workspace</p>
            <h1>Hello, {greeting}.</h1>
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
                    <option value="">Any State or UT</option>
                    {STATE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                    {profile.state && !STATE_OPTIONS.some((option) => option.value === profile.state) && (
                      <option value={profile.state}>{profile.state}</option>
                    )}
                  </select>
                </label>
                <label>Education level
                  <select value={profile.education_level} onChange={(e) => setProfile({ ...profile, education_level: e.target.value })}>
                    <option value="">Any level</option>
                    <option value="UNDERGRADUATE">Undergraduate</option>
                    <option value="DIPLOMA">Diploma</option><option value="POSTGRADUATE">Postgraduate</option>
                  </select>
                </label>
                <label>Course
                  <select value={profile.course} onChange={(e) => setProfile({ ...profile, course: e.target.value })}>
                    <option value="">Any course</option>
                    <option value="BTECH">B.Tech</option><option value="BE">B.E.</option>
                    <option value="TECHNICAL_DIPLOMA">Technical diploma</option><option value="STEM">Other STEM</option>
                    {profile.course && !['BTECH', 'BE', 'TECHNICAL_DIPLOMA', 'STEM'].includes(profile.course) && (
                      <option value={profile.course}>{profile.course}</option>
                    )}
                  </select>
                </label>
                <label>Current year
                  <input type="number" min="1" max="12" value={profile.course_year} onChange={(e) => setProfile({ ...profile, course_year: e.target.value })} />
                </label>
                <label>Marks percentage
                  <input type="number" min="0" max="100" value={profile.marks_percentage} onChange={(e) => setProfile({ ...profile, marks_percentage: e.target.value })} />
                </label>
                <label>Family-income range
                  <select value={profile.family_income_range} onChange={(e) => setProfile({ ...profile, family_income_range: e.target.value })}>
                    <option value="">Prefer not to say</option>
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
                <textarea rows={3} placeholder="Find scholarships for my technical degree." value={profile.message} onChange={(e) => setProfile({ ...profile, message: e.target.value })} />
              </label>
              <button className="modern-button-primary button-full" type="submit" disabled={searching}>
                <SearchIcon /> {searching ? 'Searching scholarships…' : 'Find scholarships'}
              </button>
            </form>
            <p className="modern-sensitive-warning">Do not enter Aadhaar, PAN, bank details, passwords, or OTPs.</p>
          </div>

          <aside className="modern-workspace-side">
            <Link className="modern-side-card modern-glass-card modern-profile-side" to="/student/profile">
              <div className="modern-profile-side-head">
                <div className="modern-profile-side-avatar">
                  {studentProfile?.photo_data_url ? (
                    <img src={studentProfile.photo_data_url} alt="" />
                  ) : (
                    <span aria-hidden="true">{profileInitial}</span>
                  )}
                </div>
                <div>
                  <span>Your profile</span>
                  <strong>{studentProfile?.full_name || studentProfile?.display_alias || 'Add your details'}</strong>
                </div>
              </div>
              <div className="modern-profile-progress-bar">
                <div className="modern-profile-progress-fill" style={{ width: `${completeness}%` }} />
              </div>
              <p>
                {completeness === 100
                  ? 'Your profile is complete. Searches use it automatically.'
                  : `${completeness}% complete. Add your state, course, marks, and photo.`}
              </p>
              <span className="modern-profile-side-cta">
                {completeness === 100 ? 'Review profile' : 'Complete profile'} <ArrowIcon />
              </span>
            </Link>
            <Link className="modern-side-card modern-glass-card modern-link-side" to="/student/applications">
              <span>Applications</span><strong>View your timeline</strong><ArrowIcon />
            </Link>
            <Link className="modern-side-card modern-glass-card" to="/student/saved">
              <span>Saved scholarships</span>
              <strong>{saved.length === 1 ? '1 saved' : `${saved.length} saved`}</strong>
              <p>Bookmarks you can return to while preparing an application.</p>
            </Link>
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
                  saved={savedIds.has(scholarship.id)}
                  busy={savingId === scholarship.id}
                  onSave={(id) => void saveScholarship(id)}
                  onUnsave={(id) => void unsaveScholarship(id)}
                />
              ))}
            </div>
          )}
        </section>

        <section className="modern-results-section modern-saved-section section-pad" aria-live="polite">
          <div className="modern-results-heading">
            <div>
              <p className="modern-section-kicker">Your shortlist</p>
              <h2>Saved scholarships</h2>
            </div>
            {saved.length > 0 && <Link className="modern-action-link" to="/student/saved">See all <ArrowIcon /></Link>}
          </div>
          {saved.length === 0 ? (
            <div className="empty-state">
              <BookmarkIcon />
              <h3>Nothing saved yet</h3>
              <p>Use the bookmark button on any scholarship above to keep it here.</p>
            </div>
          ) : (
            <div className="scholarship-grid">
              {saved.slice(0, 3).map((scholarship) => (
                <ScholarshipCard
                  key={scholarship.id}
                  scholarship={scholarship}
                  saved
                  busy={savingId === scholarship.id}
                  onUnsave={(id) => void unsaveScholarship(id)}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
