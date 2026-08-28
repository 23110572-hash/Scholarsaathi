import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowIcon } from '../components/Icons'
import { api } from '../lib/api'
import type { ApplicationListItem } from '../types'

export function StudentApplicationsPage() {
  const [applications, setApplications] = useState<ApplicationListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api<ApplicationListItem[]>('/api/student/applications')
      .then(setApplications)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Unable to load applications'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <main className="content-page section-pad">
      <div className="page-heading-row">
        <div><p className="section-kicker">Application timeline</p><h1>Your applications</h1>
          <p>Track drafts, submissions, provider updates, and required corrections.</p></div>
        <Link className="button button-secondary" to="/student">Find scholarships</Link>
      </div>
      {error && <div className="error-banner">{error}</div>}
      {loading ? <div className="loader" /> : applications.length === 0 ? (
        <div className="empty-state"><h2>No applications yet</h2><p>Open a scholarship to review its application requirements and begin when ready.</p></div>
      ) : (
        <div className="application-list">
          {applications.map((application) => (
            <Link key={application.id} to={`/applications/${application.id}`} className="application-row">
              <span className="application-status">{application.status.replaceAll('_', ' ')}</span>
              <div><strong>{application.scholarship_title}</strong><small>{application.organization_name}</small></div>
              <time>{new Date(application.updated_at).toLocaleDateString('en-IN')}</time>
              <ArrowIcon />
            </Link>
          ))}
        </div>
      )}
    </main>
  )
}
