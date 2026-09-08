import { useEffect, useMemo, useState } from 'react'
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

function discoveryRequestFromProfile(profile: StudentProfile, preferredLanguage: string) {
  return {
    state: profile.state_code ?? undefined,
    gender: profile.gender ?? undefined,
    education_level: profile.education_level ?? undefined,
    course: profile.course ?? undefined,
    course_year: profile.course_year ?? undefined,
    marks_percentage: profile.marks_percentage ?? undefined,
    family_income_range: profile.family_income_range ?? undefined,
    categories: profile.categories,
    preferred_language: preferredLanguage,
  }
}

export function StudentDashboard() {
  const { user } = useAuth()
  const [studentProfile, setStudentProfile] = useState<StudentProfile | null>(null)
  const [catalog, setCatalog] = useState<Scholarship[]>([])
  const [saved, setSaved] = useState<Scholarship[]>([])
  const [discovery, setDiscovery] = useState<DiscoveryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function load() {
      // Each panel degrades independently: a failed recommendation request still shows the catalog.
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
        const profile = profileResult.value
        setStudentProfile(profile)
        try {
          const response = await api<DiscoveryResponse>('/api/ai/discover', {
            method: 'POST',
            body: JSON.stringify(
              discoveryRequestFromProfile(profile, user?.preferred_language ?? 'en'),
            ),
          })
          if (cancelled) return
          setDiscovery(response)
          setNotice(response.notice)
        } catch {
          // Keep the regular catalog visible when personalized discovery is unavailable.
        }
      }
      if (!cancelled) setLoading(false)
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [user?.preferred_language])

  const assessments = useMemo(() => {
    const map = new Map<string, ScholarshipAssessment>()
    discovery?.assessments.forEach((assessment) => {
      map.set(assessment.scholarship_version_id, assessment)
    })
    return map
  }, [discovery])

  const savedIds = useMemo(() => new Set(saved.map((item) => item.id)), [saved])

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

  const actionableVersions = new Set(
    discovery?.assessments
      .filter(
        (assessment) =>
          assessment.assessment === 'LIKELY_ELIGIBLE' ||
          assessment.assessment === 'POSSIBLY_ELIGIBLE_NEEDS_INFORMATION',
      )
      .map((assessment) => assessment.scholarship_version_id) ?? [],
  )
  const displayedScholarships = discovery
    ? discovery.candidates.filter((candidate) => actionableVersions.has(candidate.version_id))
    : catalog
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
            <p>Your saved profile is used to find scholarships you can review.</p>
          </div>
        </section>

        <section className="modern-profile-actions section-pad">
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
                  ? 'Your discovery profile is complete. Individual applications may still require provider-specific answers or documents.'
                  : `${completeness}% of your discovery profile is complete. Add your state, course, marks, and photo.`}
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
            <div>
              <p className="modern-section-kicker">Scholarships for you</p>
              <h2>Browse scholarships according to your profiles</h2>
            </div>
            <span>{loading ? 'Loading…' : `${displayedScholarships.length} shown`}</span>
          </div>
          {notice && <div className="notice-banner"><SparkIcon /><p>{notice}</p></div>}
          {error && <div className="error-banner" role="alert">{error}</div>}
          {!loading && displayedScholarships.length === 0 ? (
            <div className="empty-state"><SearchIcon /><h3>No scholarships found</h3><p>Complete or update your profile to improve your matches.</p></div>
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
