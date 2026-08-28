import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ShieldIcon } from '../components/Icons'
import { api } from '../lib/api'
import type { ApplicationDetail, ApplicationField } from '../types'

function FieldInput({ field, value, onChange }: { field: ApplicationField; value: unknown; onChange: (value: unknown) => void }) {
  if (field.field_type === 'CHECKBOX') {
    return <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />
  }
  if (field.field_type === 'SELECT') {
    return <select value={String(value ?? '')} onChange={(event) => onChange(event.target.value)} required={field.required}>
      <option value="">Choose an option</option>
      {field.options?.map((option) => <option key={option} value={option}>{option.replaceAll('_', ' ')}</option>)}
    </select>
  }
  if (field.field_type === 'TEXTAREA') {
    return <textarea rows={4} value={String(value ?? '')} onChange={(event) => onChange(event.target.value)} required={field.required} />
  }
  return <input type={field.field_type === 'NUMBER' ? 'number' : field.field_type === 'DATE' ? 'date' : 'text'} value={String(value ?? '')} onChange={(event) => onChange(event.target.value)} required={field.required} />
}

export function ApplicationPage() {
  const { applicationId } = useParams()
  const [application, setApplication] = useState<ApplicationDetail | null>(null)
  const [answers, setAnswers] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function loadApplication() {
    if (!applicationId) return
    try {
      setApplication(await api<ApplicationDetail>(`/api/applications/${applicationId}`))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Application not found')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void loadApplication() }, [applicationId])

  async function saveAnswers(event: FormEvent) {
    event.preventDefault()
    if (!applicationId) return
    setSaving(true); setError(''); setMessage('')
    try {
      await api(`/api/applications/${applicationId}/answers`, { method: 'PUT', body: JSON.stringify({ answers }) })
      setMessage('Answers encrypted and saved to your application draft.')
      await loadApplication()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save answers')
    } finally { setSaving(false) }
  }

  async function submitApplication() {
    if (!applicationId) return
    setSaving(true); setError(''); setMessage('')
    try {
      await api(`/api/applications/${applicationId}/submit`, { method: 'POST' })
      setMessage('Application submitted to the provider queue.')
      await loadApplication()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not submit application')
    } finally { setSaving(false) }
  }

  if (loading) return <main className="screen-center"><div className="loader" /><p>Opening encrypted application…</p></main>
  if (!application) return <main className="screen-center"><h1>Application unavailable</h1><p>{error}</p></main>

  const editable = ['DRAFT', 'READY_FOR_STUDENT_REVIEW', 'CORRECTION_REQUESTED'].includes(application.status)

  return (
    <main className="application-page section-pad">
      <div className="application-header">
        <Link className="back-link" to={`/scholarships/${application.scholarship_id}`}>← Scholarship details</Link>
        <div><p className="section-kicker">Common application</p><h1>{application.scholarship_title}</h1><p>{application.organization_name}</p></div>
        <span className="large-status">{application.status.replaceAll('_', ' ')}</span>
      </div>
      <div className="privacy-warning"><ShieldIcon /><div><strong>Protect your information</strong><p>Enter only the information requested by this application. Never enter passwords, OTPs, or government-account credentials.</p></div></div>
      <div className="application-layout">
        <form className="application-form" onSubmit={(event) => void saveAnswers(event)}>
          <div className="form-section-title"><span>01</span><div><h2>Student and study information</h2><p>Fields are defined by the provider’s application template.</p></div></div>
          {application.fields.map((field) => (
            <label key={field.id} className={field.field_type === 'CHECKBOX' ? 'checkbox-field' : ''}>
              <span>{field.label}{field.required && <sup>Required</sup>}</span>
              <small>{field.help_text}</small>
              <FieldInput field={field} value={answers[field.id]} onChange={(value) => setAnswers((current) => ({ ...current, [field.id]: value }))} />
              {application.answered_field_ids.includes(field.id) && <em>Saved securely</em>}
            </label>
          ))}
          {error && <div className="error-banner">{error}</div>}
          {message && <div className="success-banner">{message}</div>}
          {editable && <div className="application-actions"><button className="button button-secondary" type="submit" disabled={saving}>Save encrypted draft</button><button className="button button-primary" type="button" disabled={saving} onClick={() => void submitApplication()}>Submit application</button></div>}
        </form>
        <aside className="timeline-card">
          <p className="section-kicker">Application timeline</p>
          <h2>One status, one place</h2>
          <ol>
            {application.events.map((event) => <li key={`${event.event_type}-${event.created_at}`}><i /><div><strong>{event.event_type.replaceAll('_', ' ')}</strong><p>{event.safe_message}</p><time>{new Date(event.created_at).toLocaleString('en-IN')}</time></div></li>)}
          </ol>
          <p className="timeline-note">Application status is updated by the participating provider.</p>
        </aside>
      </div>
    </main>
  )
}
