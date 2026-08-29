import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, matchPath, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api, ApiError } from '../lib/api'
import type {
  DiscoveryProfile,
  DiscoveryResponse,
  Scholarship,
  ScholarshipAssessment,
  ScholarshipQuestionResponse,
} from '../types'
import { ChatIcon, CloseIcon, SendIcon, SparkIcon } from './Icons'

type AssistantReply =
  | { kind: 'discovery'; data: DiscoveryResponse }
  | { kind: 'question'; data: ScholarshipQuestionResponse }

interface ConversationTurn {
  id: number
  question: string
  reply?: AssistantReply
}

const assessmentLabels: Record<ScholarshipAssessment['assessment'], string> = {
  LIKELY_ELIGIBLE: 'Potential match',
  POSSIBLY_ELIGIBLE_NEEDS_INFORMATION: 'May match — more details needed',
  LIKELY_NOT_ELIGIBLE: 'May not match',
  CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION: 'Could not determine',
}

const assessmentRank: Record<ScholarshipAssessment['assessment'], number> = {
  LIKELY_ELIGIBLE: 0,
  POSSIBLY_ELIGIBLE_NEEDS_INFORMATION: 1,
  CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION: 2,
  LIKELY_NOT_ELIGIBLE: 3,
}

const questionLabels: Record<ScholarshipQuestionResponse['label'], string> = {
  SUPPORTED_BY_PROVIDER_SOURCE: 'Supported by provider information',
  MORE_INFORMATION_NEEDED: 'More information needed',
  PROVIDER_CONFIRMATION_REQUIRED: 'Provider confirmation required',
}

function conversationContext(questions: string[]): string {
  const recent = questions.slice(-4)
  const message = recent
    .map((question, index) => `${index === recent.length - 1 ? 'Current question' : 'Earlier information'}: ${question}`)
    .join('\n')
  return message.length <= 1200 ? message : message.slice(message.length - 1200)
}

function DiscoveryReply({ data }: { data: DiscoveryResponse }) {
  const assessmentByVersion = new Map(
    data.assessments.map((assessment) => [assessment.scholarship_version_id, assessment]),
  )
  const results = data.candidates
    .map((scholarship) => ({ scholarship, assessment: assessmentByVersion.get(scholarship.version_id) }))
    .sort((left, right) => {
      if (!left.assessment) return 1
      if (!right.assessment) return -1
      return assessmentRank[left.assessment.assessment] - assessmentRank[right.assessment.assessment]
    })

  return (
    <div className="ai-reply-content">
      {data.introduction && <p>{data.introduction}</p>}
      {results.length === 0 ? (
        <p>No active scholarships matched yet. Add your state, course, study year, marks, and family-income range.</p>
      ) : (
        <div className="ai-match-list">
          {results.slice(0, 4).map(({ scholarship, assessment }) => (
            <article className="ai-match-card" key={scholarship.id}>
              <span className={`ai-assessment ai-assessment-${assessment?.assessment.toLowerCase() ?? 'unavailable'}`}>
                {assessment ? assessmentLabels[assessment.assessment] : 'Published candidate'}
              </span>
              <h3>{scholarship.title}</h3>
              <small>{scholarship.organization.display_name}</small>
              <p>{assessment?.summary ?? scholarship.summary}</p>
              {assessment && assessment.missing_information.length > 0 && (
                <p className="ai-missing"><strong>Tell me:</strong> {assessment.missing_information.slice(0, 2).join('; ')}</p>
              )}
              {assessment?.next_steps[0] && <p className="ai-next-step"><strong>Next:</strong> {assessment.next_steps[0]}</p>}
              <Link to={`/scholarships/${scholarship.id}`}>View scholarship</Link>
            </article>
          ))}
        </div>
      )}
      {results.length > 4 && <small>Showing the strongest 4 of {results.length} catalog candidates.</small>}
      <p className="ai-evidence-note">{data.notice}</p>
    </div>
  )
}

function QuestionReply({ data }: { data: ScholarshipQuestionResponse }) {
  return (
    <div className="ai-reply-content">
      <span className="ai-answer-label">{questionLabels[data.label]}</span>
      <p>{data.answer}</p>
      {data.citations.length > 0 && (
        <div className="ai-citations">
          {data.citations.map((citation) => (
            <a key={citation.citation_id} href={`#${citation.citation_id}`}>
              Source: {citation.section_title}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

function profileFromLocation(search: string, message: string, preferredLanguage: string): DiscoveryProfile {
  const params = new URLSearchParams(search)
  const profile: DiscoveryProfile = { message, preferred_language: preferredLanguage }
  const state = params.get('state_code')?.trim()
  const educationLevel = params.get('education_level')?.trim()
  const course = params.get('course')?.trim()
  if (state?.length === 2) profile.state = state
  if (educationLevel) profile.education_level = educationLevel
  if (course) profile.course = course
  return profile
}

export function EligibilityAssistant() {
  const location = useLocation()
  const { user } = useAuth()
  const detailMatch = matchPath('/scholarships/:scholarshipId', location.pathname)
  const isCatalog = location.pathname === '/scholarships'
  const scholarshipId = detailMatch?.params.scholarshipId
  const isVisible = isCatalog || Boolean(scholarshipId)
  const routeKey = scholarshipId ? `detail-${scholarshipId}` : isCatalog ? 'catalog' : 'hidden'
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const [turns, setTurns] = useState<ConversationTurn[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const nextId = useRef(1)
  const launcherRef = useRef<HTMLButtonElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const transcriptRef = useRef<HTMLDivElement>(null)

  const suggestedQuestions = useMemo(
    () => scholarshipId
      ? ['What are the main eligibility requirements?', 'Which documents are required?']
      : ['I study BTech in Odisha. Which scholarships could fit me?', 'What details do you need to check my eligibility?'],
    [scholarshipId],
  )

  useEffect(() => {
    setOpen(false)
    setDraft('')
    setTurns([])
    setError('')
  }, [routeKey])

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        launcherRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [open])

  useEffect(() => {
    if (open && transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
    }
  }, [open, turns, loading])

  if (!isVisible) return null

  function closeAssistant() {
    setOpen(false)
    launcherRef.current?.focus()
  }

  function useSuggestion(suggestion: string) {
    setDraft(suggestion)
    inputRef.current?.focus()
  }

  async function submitQuestion(event: FormEvent) {
    event.preventDefault()
    const question = draft.trim()
    if (!question || loading) return

    const id = nextId.current++
    const questions = [...turns.map((turn) => turn.question), question]
    const context = conversationContext(questions)
    setTurns((current) => [...current, { id, question }])
    setDraft('')
    setError('')
    setLoading(true)

    try {
      let reply: AssistantReply
      if (scholarshipId) {
        const data = await api<ScholarshipQuestionResponse>(`/api/ai/scholarships/${scholarshipId}/questions`, {
          method: 'POST',
          body: JSON.stringify({ question: context, preferred_language: user?.preferred_language ?? 'en' }),
        })
        reply = { kind: 'question', data }
      } else {
        const data = await api<DiscoveryResponse>('/api/ai/discover', {
          method: 'POST',
          body: JSON.stringify(profileFromLocation(location.search, context, user?.preferred_language ?? 'en')),
        })
        reply = { kind: 'discovery', data }
      }
      setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, reply } : turn)))
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 429) {
        setError('Too many AI requests. Please wait a minute and try again.')
      } else {
        setError(caught instanceof Error ? caught.message : 'The assistant could not answer right now.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="eligibility-assistant">
      {open && (
        <aside className="ai-assistant-panel" id="eligibility-assistant-panel" aria-labelledby="eligibility-assistant-title">
          <header className="ai-assistant-header">
            <div className="ai-assistant-mark">
              <img src="/logo.png" alt="ScholarSaathi AI" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
            </div>
            <div>
              <h2 id="eligibility-assistant-title">ScholarSaathi AI</h2>
              <p>{scholarshipId ? 'Ask about this scholarship' : 'Find scholarships that may fit you'}</p>
            </div>
            <button className="ai-icon-button" type="button" onClick={closeAssistant} aria-label="Close scholarship assistant">
              <CloseIcon />
            </button>
          </header>

          <div className="ai-transcript" ref={transcriptRef} role="log" aria-live="polite" aria-relevant="additions">
            <div className="ai-message ai-message-assistant">
              <p>{scholarshipId
                ? 'Ask me about eligibility, benefits, dates, documents, or the application process. I answer from provider-confirmed information.'
                : 'Tell me your state, course, study year, marks, family-income range, and category. I’ll compare your details with provider-confirmed scholarship information.'}</p>
            </div>

            {turns.map((turn) => (
              <div className="ai-turn" key={turn.id}>
                <div className="ai-message ai-message-user"><p>{turn.question}</p></div>
                {turn.reply && (
                  <div className="ai-message ai-message-assistant">
                    {turn.reply.kind === 'discovery'
                      ? <DiscoveryReply data={turn.reply.data} />
                      : <QuestionReply data={turn.reply.data} />}
                  </div>
                )}
              </div>
            ))}
            {loading && <p className="ai-thinking" role="status">ScholarSaathi is checking provider evidence…</p>}
            {error && <p className="ai-error" role="alert">{error}</p>}
          </div>

          {turns.length === 0 && (
            <div className="ai-suggestions" aria-label="Suggested questions">
              {suggestedQuestions.map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => useSuggestion(suggestion)}>{suggestion}</button>
              ))}
            </div>
          )}

          <form className="ai-composer" onSubmit={(event) => void submitQuestion(event)}>
            <label className="sr-only" htmlFor="eligibility-assistant-input">Message ScholarSaathi AI</label>
            <textarea
              id="eligibility-assistant-input"
              ref={inputRef}
              rows={2}
              minLength={3}
              maxLength={1200}
              placeholder={scholarshipId ? 'Ask about this scholarship…' : 'Describe your studies and eligibility details…'}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              disabled={loading}
              required
            />
            <button type="submit" disabled={loading || draft.trim().length < 3} aria-label="Send message">
              <SendIcon />
            </button>
          </form>
        </aside>
      )}

      <button
        className="ai-assistant-launcher"
        ref={launcherRef}
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-label={open ? 'Close scholarship assistant' : 'Open scholarship assistant'}
        aria-expanded={open}
        aria-controls="eligibility-assistant-panel"
      >
        {open ? <CloseIcon /> : <img src="/ai-logo.png" alt="Ask AI" className="ai-launcher-logo" />}
      </button>
    </div>
  )
}
