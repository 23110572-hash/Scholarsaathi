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
    <main className="modern-workspace-page modern-organization-page" style={{ minHeight: '100vh' }}>
      <div className="modern-workspace-overlay"></div>
      <div className="modern-container" style={{ paddingTop: '3rem', paddingBottom: '6rem', paddingLeft: '1.5rem', paddingRight: '1.5rem' }}>
        <section className="glass-card" style={{ padding: 'clamp(2rem, 5vw, 3rem)', marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '2rem' }}>
          <div>
            <p className="eyebrow">Organization workspace</p>
            <h1 style={{ fontSize: 'clamp(2.5rem, 5vw, 3.5rem)', margin: '0.5rem 0 1rem', color: '#0f172a' }}>{organization?.display_name ?? 'Loading organization…'}</h1>
            <p style={{ color: '#64748b', fontSize: '1.2rem', maxWidth: '600px' }}>Own, confirm, publish, pause, and manage only your organization’s scholarship records.</p>
          </div>
          <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', gap: '1rem', alignItems: 'center', background: 'rgba(255,255,255,0.6)' }}>
            <div style={{ color: 'var(--green)' }}><BuildingIcon /></div>
            <div>
              <span style={{ display: 'block', fontSize: '0.875rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 'bold' }}>Record ownership</span>
              <strong style={{ display: 'block', fontSize: '1.1rem', color: '#0f172a' }}>{organization?.member_role?.replaceAll('_', ' ') ?? 'Organization member'}</strong>
              <small style={{ color: '#64748b', fontSize: '0.9rem' }}>Domain: {organization?.ownership_domain ?? 'Loading…'}</small>
            </div>
          </div>
        </section>
      {message && <div className="success-banner">{message}</div>}
      {error && <div className="error-banner">{error}</div>}

      <section className="modern-metrics-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem', marginBottom: '3rem' }}>
        <article className="glass-card modern-hover-lift" style={{ padding: '1.5rem', borderLeft: '4px solid var(--green)' }}>
          <span style={{ display: 'block', fontSize: '0.9rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 'bold', marginBottom: '0.5rem' }}>Published knowledge</span>
          <strong style={{ display: 'block', fontSize: '2.5rem', color: '#0f172a', lineHeight: '1', marginBottom: '0.5rem' }}>{scholarships.filter((item) => item.publication_status === 'PUBLISHED').length}</strong>
          <small style={{ color: '#64748b', fontSize: '0.95rem' }}>Versions published directly by your organization</small>
        </article>
        <article className="glass-card modern-hover-lift" style={{ padding: '1.5rem', borderLeft: '4px solid var(--orange)' }}>
          <span style={{ display: 'block', fontSize: '0.9rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 'bold', marginBottom: '0.5rem' }}>Student applications</span>
          <strong style={{ display: 'block', fontSize: '2.5rem', color: '#0f172a', lineHeight: '1', marginBottom: '0.5rem' }}>{applications.length}</strong>
          <small style={{ color: '#64748b', fontSize: '0.95rem' }}>Separate provider decision workflow</small>
        </article>
        <article className="glass-card modern-hover-lift" style={{ padding: '1.5rem', borderLeft: '4px solid var(--blue)' }}>
          <span style={{ display: 'block', fontSize: '0.9rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 'bold', marginBottom: '0.5rem' }}>Ownership schema</span>
          <strong style={{ display: 'block', fontSize: '1.5rem', color: '#0f172a', lineHeight: '1.2', margin: '0.5rem 0' }}>{organization?.organization_type.replaceAll('_', ' ') ?? '—'}</strong>
          <small style={{ color: '#64748b', fontSize: '0.95rem' }}>Strictly isolated to {organization?.ownership_domain ?? 'your organization domain'}</small>
        </article>
      </section>

      <section className="glass-card" style={{ padding: 'clamp(2rem, 5vw, 3rem)', marginBottom: '3rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '1rem', marginBottom: '2rem' }}>
          <div>
            <p className="eyebrow">Scholarship registry</p>
            <h2 style={{ fontSize: 'clamp(1.5rem, 3vw, 2rem)', margin: '0.5rem 0', color: '#0f172a' }}>Your published and draft programmes</h2>
          </div>
          <button className="modern-button-primary" type="button" onClick={() => setShowForm((value) => !value)}>
            {showForm ? 'Close form' : 'Create scholarship'}
          </button>
        </div>

        {showForm && (
          <form className="modern-large-form" style={{ background: 'rgba(255,255,255,0.7)', padding: '2rem', borderRadius: '1rem', marginBottom: '2rem', border: '1px solid rgba(0,0,0,0.05)' }} onSubmit={(event) => void createScholarship(event)}>
            <div className="form-section-title" style={{ marginBottom: '1.5rem' }}><span style={{ color: 'var(--green)', fontWeight: 'bold' }}>01</span><div style={{ marginLeft: '1rem' }}><h3 style={{ margin: 0 }}>Programme identity</h3><p style={{ margin: 0, color: '#64748b' }}>Every field remains owned by your organization.</p></div></div>
            <div className="form-grid" style={{ display: 'grid', gap: '1rem', gridTemplateColumns: '1fr 1fr', marginBottom: '1rem' }}>
              <label>Scholarship title<input className="modern-input" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required /></label>
              <label>Academic year<input className="modern-input" value={form.academic_year} onChange={(event) => setForm({ ...form, academic_year: event.target.value })} required /></label>
            </div>
            <label style={{ display: 'block', marginBottom: '1rem' }}>Short summary<textarea className="modern-input" rows={2} value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} required /></label>
            <div className="form-grid" style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', marginBottom: '2rem' }}>
              <label>Scope<input className="modern-input" value={form.scope} onChange={(event) => setForm({ ...form, scope: event.target.value })} /></label>
              <label>States<input className="modern-input" value={form.states} onChange={(event) => setForm({ ...form, states: event.target.value })} /></label>
              <label>Education levels<input className="modern-input" value={form.education} onChange={(event) => setForm({ ...form, education: event.target.value })} /></label>
              <label>Courses<input className="modern-input" value={form.courses} onChange={(event) => setForm({ ...form, courses: event.target.value })} /></label>
              <label>Categories<input className="modern-input" value={form.categories} onChange={(event) => setForm({ ...form, categories: event.target.value })} /></label>
            </div>
            
            <div className="form-section-title" style={{ marginBottom: '1.5rem', borderTop: '1px solid rgba(0,0,0,0.1)', paddingTop: '1.5rem' }}><span style={{ color: 'var(--green)', fontWeight: 'bold' }}>02</span><div style={{ marginLeft: '1rem' }}><h3 style={{ margin: 0 }}>Benefit and dates</h3><p style={{ margin: 0, color: '#64748b' }}>These values appear directly in student results.</p></div></div>
            <label style={{ display: 'block', marginBottom: '1rem' }}>Benefit summary<textarea className="modern-input" rows={2} value={form.benefit} onChange={(event) => setForm({ ...form, benefit: event.target.value })} /></label>
            <div className="form-grid" style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', marginBottom: '2rem' }}>
              <label>Minimum benefit<input className="modern-input" type="number" value={form.minimum} onChange={(event) => setForm({ ...form, minimum: event.target.value })} /></label>
              <label>Maximum benefit<input className="modern-input" type="number" value={form.maximum} onChange={(event) => setForm({ ...form, maximum: event.target.value })} /></label>
              <label>Opens<input className="modern-input" type="datetime-local" value={form.opens} onChange={(event) => setForm({ ...form, opens: event.target.value })} /></label>
              <label>Deadline<input className="modern-input" type="datetime-local" value={form.deadline} onChange={(event) => setForm({ ...form, deadline: event.target.value })} /></label>
            </div>
            
            <div className="form-section-title" style={{ marginBottom: '1.5rem', borderTop: '1px solid rgba(0,0,0,0.1)', paddingTop: '1.5rem' }}><span style={{ color: 'var(--green)', fontWeight: 'bold' }}>03</span><div style={{ marginLeft: '1rem' }}><h3 style={{ margin: 0 }}>Provider-supplied source</h3><p style={{ margin: 0, color: '#64748b' }}>AI may use only the evidence your organization supplies and confirms here.</p></div></div>
            <div className="form-grid" style={{ display: 'grid', gap: '1rem', gridTemplateColumns: '1fr 1fr', marginBottom: '1rem' }}>
              <label>Official source URL<input className="modern-input" type="url" placeholder="https://provider.gov.in/scholarships/programme" value={form.sourceUrl} onChange={(event) => setForm({ ...form, sourceUrl: event.target.value })} required /></label>
              <label>Helpdesk URL<input className="modern-input" type="url" placeholder="https://provider.gov.in/help" value={form.helpdeskUrl} onChange={(event) => setForm({ ...form, helpdeskUrl: event.target.value })} required /></label>
            </div>
            <label style={{ display: 'block', marginBottom: '1.5rem' }}>Eligibility and application source text<textarea className="modern-input" rows={6} value={form.sourceText} onChange={(event) => setForm({ ...form, sourceText: event.target.value })} required /></label>
            
            <button className="modern-button-primary" style={{ width: '100%', fontSize: '1.1rem', padding: '1rem' }} disabled={busy} type="submit">{busy ? 'Creating draft…' : 'Create owner draft'}</button>
          </form>
        )}

        <div style={{ display: 'grid', gap: '1rem' }}>
          {scholarships.map((item) => (
            <div className="glass-card modern-hover-lift" key={item.version_id} style={{ padding: '1.5rem', display: 'grid', gridTemplateColumns: '1fr auto auto', gap: '2rem', alignItems: 'center' }}>
              <div>
                <strong style={{ display: 'block', fontSize: '1.2rem', color: '#0f172a', marginBottom: '0.25rem' }}>{item.title}</strong>
                <p style={{ color: '#64748b', margin: 0, fontSize: '0.95rem' }}>{item.summary}</p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span style={{ display: 'block', fontSize: '0.85rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 'bold' }}>Status</span>
                <span className={`status-dot status-${item.publication_status.toLowerCase()}`} style={{ fontWeight: 'bold' }}>{item.publication_status.replaceAll('_', ' ')}</span>
              </div>
              <div style={{ minWidth: '160px', textAlign: 'right' }}>
                {item.publication_status === 'DRAFT' ? (
                  <button className="modern-button-secondary" style={{ width: '100%' }} type="button" disabled={busy} onClick={() => void publishVersion(item.version_id)}>Publish directly</button>
                ) : (
                  <span style={{ display: 'inline-block', padding: '0.5rem 1rem', background: '#f8fafc', borderRadius: '0.5rem', color: '#94a3b8', fontSize: '0.9rem', width: '100%', textAlign: 'center' }}>No action needed</span>
                )}
              </div>
            </div>
          ))}
          {scholarships.length === 0 && <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>No scholarships created yet.</div>}
        </div>
      </section>

      <section className="glass-card" style={{ padding: 'clamp(2rem, 5vw, 3rem)' }}>
        <div style={{ marginBottom: '2rem' }}>
          <p className="eyebrow">Student application review</p>
          <h2 style={{ fontSize: 'clamp(1.5rem, 3vw, 2rem)', margin: '0.5rem 0', color: '#0f172a' }}>Student applications</h2>
          <p style={{ color: '#64748b' }}>Application review and provider decisions remain separate from scholarship publication.</p>
        </div>
        
        <div style={{ display: 'grid', gap: '1rem' }}>
          {applications.length === 0 ? (
            <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>No applications have reached this organization.</div>
          ) : applications.map((application) => (
            <div className="glass-card modern-hover-lift" key={application.id} style={{ padding: '1.5rem', display: 'grid', gridTemplateColumns: 'auto 1fr auto auto', gap: '2rem', alignItems: 'center' }}>
              <span className={`status-dot status-${application.status.toLowerCase()}`} style={{ fontWeight: 'bold' }}>{application.status.replaceAll('_', ' ')}</span>
              <div>
                <strong style={{ display: 'block', fontSize: '1.2rem', color: '#0f172a', marginBottom: '0.25rem' }}>{application.scholarship_title}</strong>
                <small style={{ color: '#64748b', fontSize: '0.95rem' }}>Student applicant</small>
              </div>
              <time style={{ color: '#64748b', fontSize: '0.9rem' }}>{new Date(application.updated_at).toLocaleDateString('en-IN')}</time>
              <div style={{ display: 'flex', gap: '1rem', minWidth: '160px', justifyContent: 'flex-end' }}>
                {['SUBMITTED', 'RESUBMITTED'].includes(application.status) && <button className="modern-button-primary" onClick={() => void reviewApplication(application, 'UNDER_ORGANIZATION_REVIEW')}>Begin review</button>}
                {application.status === 'UNDER_ORGANIZATION_REVIEW' && <><button className="modern-button-secondary" onClick={() => void reviewApplication(application, 'CORRECTION_REQUESTED')}>Request correction</button><button className="modern-button-primary" style={{ background: '#16a34a', borderColor: '#15803d' }} onClick={() => void reviewApplication(application, 'APPROVED')}>Approve application</button></>}
              </div>
            </div>
          ))}
        </div>
      </section>
      </div>
    </main>
  )
}
