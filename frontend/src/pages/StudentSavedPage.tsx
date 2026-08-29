import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowIcon, BookmarkIcon } from '../components/Icons'
import { ScholarshipCard } from '../components/ScholarshipCard'
import { api } from '../lib/api'
import type { Scholarship, ScholarshipList } from '../types'

export function StudentSavedPage() {
  const [saved, setSaved] = useState<Scholarship[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const response = await api<ScholarshipList>('/api/student/saved-scholarships')
        if (!cancelled) setSaved(response.items)
      } catch (caught) {
        if (!cancelled) {
          setError(
            caught instanceof Error ? caught.message : 'Your saved scholarships could not be loaded.',
          )
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  async function removeSaved(scholarshipId: string) {
    setBusyId(scholarshipId)
    setError('')
    setNotice('')
    try {
      await api(`/api/student/saved-scholarships/${scholarshipId}`, { method: 'DELETE' })
      setSaved((current) => current.filter((item) => item.id !== scholarshipId))
      setNotice('Removed from your saved list.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'That scholarship could not be removed.')
    } finally {
      setBusyId('')
    }
  }

  if (loading) {
    return (
      <main className="screen-center">
        <div className="loader" role="status" aria-label="Loading your saved scholarships" />
      </main>
    )
  }

  return (
    <main className="modern-workspace-page">
      <div className="modern-workspace-overlay"></div>
      <div className="modern-workspace-content">
        <section className="modern-workspace-intro section-pad">
          <div>
            <p className="modern-section-kicker">Saved scholarships</p>
            <h1>{saved.length === 1 ? '1 saved scholarship' : `${saved.length} saved scholarships`}</h1>
            <p>Everything you bookmarked, newest first.</p>
          </div>
          <Link className="modern-profile-back" to="/student">
            Back to workspace <ArrowIcon />
          </Link>
        </section>

        <section className="modern-results-section section-pad" aria-live="polite">
          {notice && <div className="success-banner" role="status">{notice}</div>}
          {error && <div className="error-banner" role="alert">{error}</div>}

          {saved.length === 0 ? (
            <div className="empty-state">
              <BookmarkIcon />
              <h3>Nothing saved yet</h3>
              <p>
                Use the bookmark button on any scholarship to keep it here while you prepare an
                application.
              </p>
              <Link className="modern-button-secondary" to="/scholarships">Browse scholarships</Link>
            </div>
          ) : (
            <div className="scholarship-grid">
              {saved.map((scholarship) => (
                <ScholarshipCard
                  key={scholarship.id}
                  scholarship={scholarship}
                  saved
                  busy={busyId === scholarship.id}
                  onUnsave={(id) => void removeSaved(id)}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
