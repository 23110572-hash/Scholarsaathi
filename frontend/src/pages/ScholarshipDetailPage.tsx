import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowIcon, BookmarkIcon, BuildingIcon } from '../components/Icons'
import { useAuth } from '../context/AuthContext'
import { api } from '../lib/api'
import type { ScholarshipDetail, ScholarshipQuestionResponse } from '../types'

function formatToken(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatDate(value: string | null): string {
  if (!value) return 'Not available'
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(value))
}

const answerLabels: Record<string, string> = {
  SUPPORTED_BY_PROVIDER_SOURCE: 'Answer',
  MORE_INFORMATION_NEEDED: 'More information needed',
  PROVIDER_CONFIRMATION_REQUIRED: 'Check with the provider',
}

export function ScholarshipDetailPage() {
  const { scholarshipId } = useParams()
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [scholarship, setScholarship] = useState<ScholarshipDetail | null>(null)
  const [question, setQuestion] = useState('What are the main eligibility requirements?')
  const [answer, setAnswer] = useState<ScholarshipQuestionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [asking, setAsking] = useState(false)
  const [starting, setStarting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!scholarshipId) return
    api<ScholarshipDetail>(`/api/scholarships/${scholarshipId}`)
      .then(setScholarship)
      .catch((caught: unknown) => setLoadError(caught instanceof Error ? caught.message : 'Scholarship not found'))
      .finally(() => setLoading(false))
  }, [scholarshipId])

  function requireStudent(intent: 'apply' | 'save'): boolean {
    setActionError('')
    setNotice('')
    if (authLoading) return false
    if (!user) {
      navigate('/login/student', { state: { from: `/scholarships/${scholarshipId ?? ''}`, intent } })
      return false
    }
    if (user.realm !== 'STUDENT') {
      setActionError('Use a student account for this action.')
      return false
    }
    return true
  }

  async function askQuestion(event: FormEvent) {
    event.preventDefault()
    if (!scholarshipId) return
    setAsking(true)
    setActionError('')
    setNotice('')
    try {
      setAnswer(await api<ScholarshipQuestionResponse>(`/api/ai/scholarships/${scholarshipId}/questions`, {
        method: 'POST',
        body: JSON.stringify({ question, preferred_language: user?.preferred_language ?? 'en' }),
      }))
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : 'The question could not be answered')
    } finally {
      setAsking(false)
    }
  }

  async function saveScholarship() {
    if (!scholarshipId || !requireStudent('save')) return
    setSaving(true)
    try {
      await api(`/api/student/saved-scholarships/${scholarshipId}`, { method: 'POST' })
      setNotice('Scholarship saved.')
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : 'Could not save this scholarship')
    } finally {
      setSaving(false)
    }
  }

  async function startApplication() {
    if (!scholarshipId || !requireStudent('apply')) return
    setStarting(true)
    try {
      const application = await api<{ id: string }>(`/api/scholarships/${scholarshipId}/applications`, { method: 'POST', body: JSON.stringify({ consent_to_store_application: true }) })
      navigate(`/applications/${application.id}`)
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : 'Could not start application')
      setStarting(false)
    }
  }

  if (loading) return <main className="screen-center"><div className="loader" /><p>Loading scholarship…</p></main>
  if (!scholarship) return <main className="screen-center"><h1>Scholarship unavailable</h1><p>{loadError}</p><Link className="button button-primary" to="/scholarships">Return to scholarships</Link></main>

  const coverage = scholarship.applicable_state_codes.includes('ALL') ? 'All India' : scholarship.applicable_state_codes.join(', ')
  const applicationReady = Boolean(scholarship.application_template_id)
  const studentSignedIn = user?.realm === 'STUDENT'

  return (
    <main className="detail-page simple-detail">
      <section className="detail-hero section-pad">
        <Link className="back-link" to="/scholarships">← Back to scholarships</Link>
        <div className="detail-hero-grid">
          <div>
            <span className="provider-pill">{formatToken(scholarship.organization.organization_type)}</span>
            <p className="detail-provider"><BuildingIcon /> {scholarship.organization.display_name}</p>
            <h1>{scholarship.title}</h1>
            <p className="detail-summary">{scholarship.summary}</p>
            <div className="tag-row detail-tags">{scholarship.category_tags.map((tag) => <span key={tag}>{formatToken(tag)}</span>)}</div>
            <div className="detail-quick-actions">
              <button className="button button-secondary" type="button" disabled={saving || authLoading} onClick={() => void saveScholarship()}><BookmarkIcon /> {saving ? 'Saving…' : studentSignedIn ? 'Save scholarship' : 'Sign in to save'}</button>
              <a className="inline-link" href={scholarship.official_source_url} target="_blank" rel="noreferrer">Open source page <ArrowIcon /></a>
            </div>
          </div>
          <aside className="apply-card">
            <span>Academic year {scholarship.academic_year}</span>
            <h2>{scholarship.benefit_summary}</h2>
            <dl>
              <div><dt>Deadline</dt><dd>{formatDate(scholarship.application_deadline_at)}</dd></div>
              <div><dt>Coverage</dt><dd>{coverage}</dd></div>
              <div><dt>Updated</dt><dd>{formatDate(scholarship.last_provider_confirmed_at)}</dd></div>
            </dl>
            <button className="button button-primary button-full" type="button" onClick={() => void startApplication()} disabled={starting || authLoading || !applicationReady}>
              {starting ? 'Creating application…' : !applicationReady ? 'Application form not available' : studentSignedIn ? 'Start application' : 'Sign in to apply'} <ArrowIcon />
            </button>
            <p>Sign in is required only to start and store an application.</p>
          </aside>
        </div>
      </section>

      <section className="eligibility-overview section-pad" aria-labelledby="eligibility-heading">
        <div className="eligibility-heading"><h2 id="eligibility-heading">Eligibility overview</h2></div>
        <div className="eligibility-grid">
          <article><span>Study level</span><strong>{scholarship.education_levels.map(formatToken).join(', ')}</strong></article>
          <article><span>Courses</span><strong>{scholarship.course_families.map(formatToken).join(', ')}</strong></article>
          <article><span>Location</span><strong>{coverage}</strong></article>
          <article><span>Scope</span><strong>{formatToken(scholarship.scope)}</strong></article>
        </div>
        <div className="knowledge-summary"><div><span>Summary</span><p>{scholarship.knowledge_summary}</p></div></div>
      </section>

      <section className="detail-content section-pad">
        <div className="evidence-column">
          <div className="section-heading left-heading"><h2>Scholarship information</h2><p>Read the sections supplied for this scholarship.</p></div>
          <div className="evidence-list">
            {scholarship.evidence.map((item, index) => (
              <article key={item.citation_id} id={item.citation_id}>
                <div><span>{String(index + 1).padStart(2, '0')}</span><strong>{item.section_title}</strong><small>Section {item.page_number ?? index + 1}</small></div>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
          <div className="provider-contact-row">
            <a className="button button-secondary source-button" href={scholarship.official_source_url} target="_blank" rel="noreferrer">Open source page <ArrowIcon /></a>
            {scholarship.provider_helpdesk_url && <a className="inline-link" href={scholarship.provider_helpdesk_url} target="_blank" rel="noreferrer">Contact provider <ArrowIcon /></a>}
          </div>
          {scholarship.application_fields.length > 0 && (
            <section className="application-preview"><h2>Application requirements</h2><p>Review the information requested before starting.</p><div>{scholarship.application_fields.map((field) => <article key={field.id}><span>{formatToken(field.field_type)}</span><strong>{field.label}</strong><small>{field.required ? 'Required' : 'Optional'}{field.help_text ? ` · ${field.help_text}` : ''}</small></article>)}</div></section>
          )}
        </div>

        <aside className="question-panel">
          <div className="question-panel-heading"><h2>Ask about this scholarship</h2><p>Ask about eligibility, benefits, dates, documents, or how to apply.</p></div>
          <form onSubmit={(event) => void askQuestion(event)}>
            <label>Your question<textarea rows={5} minLength={3} maxLength={1200} value={question} onChange={(event) => setQuestion(event.target.value)} /></label>
            <button className="button button-primary button-full" type="submit" disabled={asking}>{asking ? 'Finding an answer…' : 'Ask ScholarSaathi'}</button>
          </form>
          {answer && (
            <div className="answer-card" aria-live="polite">
              <span>{answerLabels[answer.label] ?? 'Answer'}</span>
              <p>{answer.answer}</p>
              {answer.citations.map((citation) => <a key={citation.citation_id} href={`#${citation.citation_id}`}>Source: {citation.section_title}</a>)}
              {answer.suggested_questions.length > 0 && <div className="question-suggestions">{answer.suggested_questions.map((suggestion) => <button key={suggestion} type="button" onClick={() => setQuestion(suggestion)}>{suggestion}</button>)}</div>}
            </div>
          )}
          {notice && <p className="action-notice">{notice}</p>}
          {actionError && <p className="form-error" role="alert">{actionError}</p>}
          <p className="question-note">Check the source page or contact the provider before applying.</p>
        </aside>
      </section>
    </main>
  )
}
