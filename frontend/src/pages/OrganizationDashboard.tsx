import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { BuildingIcon } from '../components/Icons'
import { api } from '../lib/api'
import type { ApplicationListItem, OrganizationSummary, Scholarship, ScholarshipList } from '../types'

const initialForm = {
  title: 'Digital Learning Access Scholarship 2026–27',
  summary: 'A provider scholarship supporting undergraduate learners who need digital learning access.',
  academic_year: '2026-27',
  scope: 'STATE',
  states: 'OD',
  education: 'UNDERGRADUATE',
  courses: 'BTECH,BE',
  categories: 'INCOME,DIGITAL_ACCESS',
  benefit: '₹45,000 toward approved learning devices and connectivity.',
  minimum: '45000',
  maximum: '45000',
  opens: '2026-08-25T09:00',
  deadline: '2026-11-25T23:00',
  sourceUrl: '',
  helpdeskUrl: '',
  sourceText: 'Applicants must be domiciled in Odisha and enrolled in a recognized undergraduate B.Tech or B.E. programme. The annual family-income ceiling is ₹4,00,000. Applications close on 25 November 2026. Applicants should prepare enrolment, marks, and income evidence.',
}

export function OrganizationDashboard() {
  const [organization, setOrganization] = useState<OrganizationSummary | null>(null)
  const [scholarships, setScholarships] = useState<Scholarship[]>([])
  const [applications, setApplications] = useState<ApplicationListItem[]>([])
  const [form, setForm] = useState(initialForm)
  const [showForm, setShowForm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function loadDashboard() {
    try {
      const [org, scholarshipResponse, applicationResponse] = await Promise.all([
        api<OrganizationSummary>('/api/organizations/me'),
        api<ScholarshipList>('/api/organizations/me/scholarships'),
        api<ApplicationListItem[]>('/api/organizations/me/applications'),
      ])
      setOrganization(org)
      setScholarships(scholarshipResponse.items)
      setApplications(applicationResponse)
      if (org.jurisdiction_state_code) {
        setForm((current) => ({ ...current, states: org.jurisdiction_state_code ?? 'ALL' }))
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load organization')
    }
  }

  useEffect(() => { void loadDashboard() }, [])

  async function createScholarship(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const created = await api<Scholarship>('/api/organizations/me/scholarships', {
        method: 'POST',
        body: JSON.stringify({
          title: form.title,
          summary: form.summary,
          academic_year: form.academic_year,
          scope: form.scope,
          applicable_state_codes: form.states.split(',').map((value) => value.trim()),
          education_levels: form.education.split(',').map((value) => value.trim()),
          course_families: form.courses.split(',').map((value) => value.trim()),
          category_tags: form.categories.split(',').map((value) => value.trim()).filter(Boolean),
          benefit_summary: form.benefit,
          benefit_amount_min: Number(form.minimum),
          benefit_amount_max: Number(form.maximum),
          application_opens_at: new Date(form.opens).toISOString(),
          application_deadline_at: new Date(form.deadline).toISOString(),
          official_source_url: form.sourceUrl,
          provider_helpdesk_url: form.helpdeskUrl,
          source_sections: [{ section_title: 'Eligibility and application guidance', text: form.sourceText }],
        }),
      })
      setScholarships((current) => [created, ...current])
      setShowForm(false)
      setMessage('Owner draft created and provider-supplied evidence confirmed. Publish directly when ready.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not create scholarship')
    } finally {
      setBusy(false)
    }
  }

  async function publishVersion(versionId: string) {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api(`/api/organizations/me/scholarship-versions/${versionId}/publish`, { method: 'POST' })
      setMessage('Published directly by your organization. The record is now available in the public directory.')
      await loadDashboard()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not publish version')
    } finally {
      setBusy(false)
    }
  }

  async function reviewApplication(application: ApplicationListItem, status: string) {
    setBusy(true)
    setError('')
    try {
      await api(`/api/organizations/me/applications/${application.id}/status`, {
        method: 'POST',
        body: JSON.stringify({
          status,
          message: `Organization moved this application to ${status.replaceAll('_', ' ')}.`,
        }),
      })
      await loadDashboard()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not update application')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="organization-page section-pad">
      <section className="org-header">
        <div>
          <p className="section-kicker">Organization workspace</p>
          <h1>{organization?.display_name ?? 'Loading organization…'}</h1>
          <p>Own, confirm, publish, pause, and manage only your organization’s scholarship records.</p>
        </div>
        <div className="ownership-card">
          <BuildingIcon />
          <div>
            <span>Record ownership</span>
            <strong>{organization?.member_role?.replaceAll('_', ' ') ?? 'Organization member'}</strong>
            <small>Domain: {organization?.ownership_domain ?? 'Loading…'}</small>
          </div>
        </div>
      </section>

      {message && <div className="success-banner">{message}</div>}
      {error && <div className="error-banner">{error}</div>}

      <section className="org-metrics">
        <article>
          <span>Published knowledge</span>
          <strong>{scholarships.filter((item) => item.publication_status === 'PUBLISHED').length}</strong>
          <small>Versions published directly by your organization</small>
        </article>
        <article>
          <span>Student applications</span>
          <strong>{applications.length}</strong>
          <small>Separate provider decision workflow</small>
        </article>
        <article>
          <span>Ownership schema</span>
          <strong className="metric-text">{organization?.organization_type.replaceAll('_', ' ') ?? '—'}</strong>
          <small>Strictly isolated to {organization?.ownership_domain ?? 'your organization domain'}</small>
        </article>
      </section>

      <section className="org-section">
        <div className="org-section-heading">
          <div><p className="section-kicker">Scholarship registry</p><h2>Your published and draft programmes</h2></div>
          <button className="button button-primary" type="button" onClick={() => setShowForm((value) => !value)}>
            {showForm ? 'Close form' : 'Create scholarship'}
          </button>
        </div>

        {showForm && (
          <form className="publisher-form" onSubmit={(event) => void createScholarship(event)}>
            <div className="form-section-title"><span>01</span><div><h3>Programme identity</h3><p>Every field remains owned by your organization.</p></div></div>
            <div className="form-grid">
              <label>Scholarship title<input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required /></label>
              <label>Academic year<input value={form.academic_year} onChange={(event) => setForm({ ...form, academic_year: event.target.value })} required /></label>
            </div>
            <label>Short summary<textarea rows={2} value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} required /></label>
            <div className="form-grid three-grid">
              <label>Scope<input value={form.scope} onChange={(event) => setForm({ ...form, scope: event.target.value })} /></label>
              <label>States<input value={form.states} onChange={(event) => setForm({ ...form, states: event.target.value })} /></label>
              <label>Education levels<input value={form.education} onChange={(event) => setForm({ ...form, education: event.target.value })} /></label>
              <label>Courses<input value={form.courses} onChange={(event) => setForm({ ...form, courses: event.target.value })} /></label>
              <label>Categories<input value={form.categories} onChange={(event) => setForm({ ...form, categories: event.target.value })} /></label>
            </div>
            <div className="form-section-title"><span>02</span><div><h3>Benefit and dates</h3><p>These values appear directly in student results.</p></div></div>
            <label>Benefit summary<textarea rows={2} value={form.benefit} onChange={(event) => setForm({ ...form, benefit: event.target.value })} /></label>
            <div className="form-grid">
              <label>Minimum benefit<input type="number" value={form.minimum} onChange={(event) => setForm({ ...form, minimum: event.target.value })} /></label>
              <label>Maximum benefit<input type="number" value={form.maximum} onChange={(event) => setForm({ ...form, maximum: event.target.value })} /></label>
              <label>Opens<input type="datetime-local" value={form.opens} onChange={(event) => setForm({ ...form, opens: event.target.value })} /></label>
              <label>Deadline<input type="datetime-local" value={form.deadline} onChange={(event) => setForm({ ...form, deadline: event.target.value })} /></label>
            </div>
            <div className="form-section-title"><span>03</span><div><h3>Provider-supplied source</h3><p>AI may use only the evidence your organization supplies and confirms here.</p></div></div>
            <div className="form-grid">
              <label>Official source URL<input type="url" placeholder="https://provider.gov.in/scholarships/programme" value={form.sourceUrl} onChange={(event) => setForm({ ...form, sourceUrl: event.target.value })} required /></label>
              <label>Helpdesk URL<input type="url" placeholder="https://provider.gov.in/help" value={form.helpdeskUrl} onChange={(event) => setForm({ ...form, helpdeskUrl: event.target.value })} required /></label>
            </div>
            <label>Eligibility and application source text<textarea rows={6} value={form.sourceText} onChange={(event) => setForm({ ...form, sourceText: event.target.value })} required /></label>
            <button className="button button-primary" disabled={busy} type="submit">{busy ? 'Creating draft…' : 'Create owner draft'}</button>
          </form>
        )}

        <div className="registry-table" role="table">
          <div className="registry-head" role="row"><span>Scholarship</span><span>Status</span><span>Academic year</span><span>Action</span></div>
          {scholarships.map((item) => (
            <div className="registry-row" role="row" key={item.version_id}>
              <div><BuildingIcon /><span><strong>{item.title}</strong><small>{item.summary}</small></span></div>
              <span className={`status-dot status-${item.publication_status.toLowerCase()}`}>{item.publication_status.replaceAll('_', ' ')}</span>
              <span>{item.academic_year}</span>
              <span>{item.publication_status === 'DRAFT' ? <button className="table-button" type="button" disabled={busy} onClick={() => void publishVersion(item.version_id)}>Publish directly</button> : 'No publish action'}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="org-section">
        <div className="org-section-heading">
          <div><p className="section-kicker">Student application review</p><h2>Student applications</h2><p>Application review and provider decisions remain separate from scholarship publication.</p></div>
        </div>
        <div className="application-list">
          {applications.length === 0 ? (
            <div className="empty-state"><p>No applications have reached this organization.</p></div>
          ) : applications.map((application) => (
            <div className="application-row" key={application.id}>
              <span className="application-status">{application.status.replaceAll('_', ' ')}</span>
              <div><strong>{application.scholarship_title}</strong><small>Student applicant</small></div>
              <time>{new Date(application.updated_at).toLocaleDateString('en-IN')}</time>
              <div className="review-actions">
                {['SUBMITTED', 'RESUBMITTED'].includes(application.status) && <button onClick={() => void reviewApplication(application, 'UNDER_ORGANIZATION_REVIEW')}>Begin review</button>}
                {application.status === 'UNDER_ORGANIZATION_REVIEW' && <><button onClick={() => void reviewApplication(application, 'CORRECTION_REQUESTED')}>Request correction</button><button onClick={() => void reviewApplication(application, 'APPROVED')}>Approve application</button></>}
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}
