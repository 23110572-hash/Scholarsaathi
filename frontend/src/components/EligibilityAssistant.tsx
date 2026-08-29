import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, matchPath, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api, ApiError } from '../lib/api'
import type {
  ChatDetailKey,
  ChatExtractedFacts,
  DiscoveryProfile,
  DiscoveryResponse,
  ScholarshipAssessment,
  ScholarshipQuestionResponse,
} from '../types'
import { CloseIcon, SendIcon } from './Icons'

type AssistantReply =
  | { kind: 'discovery'; data: DiscoveryResponse }
  | { kind: 'question'; data: ScholarshipQuestionResponse }

interface ConversationTurn {
  id: number
  question: string
  reply?: AssistantReply
}

/** Eligibility facts gathered so far in this conversation. */
type KnownFacts = Partial<{
  state: string
  education_level: string
  course: string
  course_year: number
  marks_percentage: number
  family_income_range: string
  categories: string[]
}>

const assessmentLabels: Record<ScholarshipAssessment['assessment'], string> = {
  LIKELY_ELIGIBLE: 'Looks like a match',
  POSSIBLY_ELIGIBLE_NEEDS_INFORMATION: 'Might match',
  LIKELY_NOT_ELIGIBLE: 'Probably not a match',
  CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION: 'Not enough to say',
}

const assessmentRank: Record<ScholarshipAssessment['assessment'], number> = {
  LIKELY_ELIGIBLE: 0,
  POSSIBLY_ELIGIBLE_NEEDS_INFORMATION: 1,
  CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION: 2,
  LIKELY_NOT_ELIGIBLE: 3,
}

const questionLabels: Record<ScholarshipQuestionResponse['label'], string> = {
  SUPPORTED_BY_PROVIDER_SOURCE: 'From the provider’s own information',
  MORE_INFORMATION_NEEDED: 'More information needed',
  PROVIDER_CONFIRMATION_REQUIRED: 'Needs provider confirmation',
}

const detailLabels: Record<ChatDetailKey, string> = {
  state: 'State or UT',
  education_level: 'education level',
  course: 'course',
  course_year: 'study year',
  marks_percentage: 'marks percentage',
  family_income_range: 'family income range',
  categories: 'category',
}

function listDetails(keys: ChatDetailKey[]): string {
  const labels = keys.map((key) => detailLabels[key])
  if (labels.length <= 1) return labels.join('')
  return `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}`
}

/** Merges facts the assistant extracted from a reply into the running conversation state. */
function mergeFacts(current: KnownFacts, extracted: ChatExtractedFacts | null): KnownFacts {
  if (!extracted) return current
  const next: KnownFacts = { ...current }
  if (extracted.state) next.state = extracted.state
  if (extracted.education_level) next.education_level = extracted.education_level
  if (extracted.course) next.course = extracted.course
  if (extracted.course_year !== null) next.course_year = extracted.course_year
  if (extracted.marks_percentage !== null) next.marks_percentage = extracted.marks_percentage
  if (extracted.family_income_range) next.family_income_range = extracted.family_income_range
  if (extracted.categories.length > 0) {
    next.categories = Array.from(new Set([...(current.categories ?? []), ...extracted.categories]))
  }
  return next
}

function DiscoveryReply({ data }: { data: DiscoveryResponse }) {
  // A conversation turn is just a chat message: no cards, no notice footer.
  if (data.mode === 'CONVERSATION') {
    return (
      <div className="ai-reply-content">
        {data.introduction && <p>{data.introduction}</p>}
        {data.requested_details.length > 0 && (
          <p className="ai-detail-request">
            Share your {listDetails(data.requested_details)} and I can compare it against each
            provider’s published rules.
          </p>
        )}
      </div>
    )
  }

  const assessmentByVersion = new Map(
    data.assessments.map((assessment) => [assessment.scholarship_version_id, assessment]),
  )
  // Only surface scholarships the assistant actually reached a conclusion on. Unassessed
  // catalog rows carry no information for the student and only add noise.
  const results = data.candidates
    .filter((scholarship) => assessmentByVersion.has(scholarship.version_id))
    .map((scholarship) => ({
      scholarship,
      assessment: assessmentByVersion.get(scholarship.version_id)!,
    }))
    .sort(
      (left, right) =>
        assessmentRank[left.assessment.assessment] - assessmentRank[right.assessment.assessment],
    )

  return (
    <div className="ai-reply-content">
      {data.introduction && <p>{data.introduction}</p>}
      {results.length === 0 ? (
        <p>
          I could not reach a conclusion on any scholarship with those details yet. Adding your
          marks or family income range usually helps.
        </p>
      ) : (
        <div className="ai-match-list">
          {results.map(({ scholarship, assessment }) => (
            <article className="ai-match-card" key={scholarship.id}>
              <span className={`ai-assessment ai-assessment-${assessment.assessment.toLowerCase()}`}>
                {assessmentLabels[assessment.assessment]}
              </span>
              <h3>{scholarship.title}</h3>
              <small>{scholarship.organization.display_name}</small>
              <p>{assessment.summary}</p>
              {assessment.matching_points[0] && (
                <p className="ai-match-why">
                  <strong>Why:</strong> {assessment.matching_points[0].statement}
                </p>
              )}
              {assessment.assessment !== 'LIKELY_NOT_ELIGIBLE' &&
                assessment.missing_information.length > 0 && (
                  <p className="ai-missing">
                    <strong>Still needed:</strong> {assessment.missing_information[0]}
                  </p>
                )}
              <Link to={`/scholarships/${scholarship.id}`}>Open and ask about this one</Link>
            </article>
          ))}
        </div>
      )}
      {data.requested_details.length > 0 && (
        <p className="ai-detail-request">
          Tell me your {listDetails(data.requested_details)} to sharpen this.
        </p>
      )}
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

/** Seeds the conversation with any filters already applied on the catalog page. */
function factsFromLocation(search: string): KnownFacts {
  const params = new URLSearchParams(search)
  const facts: KnownFacts = {}
  const state = params.get('state_code')?.trim()
  const educationLevel = params.get('education_level')?.trim()
  const course = params.get('course')?.trim()
  if (state?.length === 2) facts.state = state.toUpperCase()
  if (educationLevel) facts.education_level = educationLevel.toUpperCase()
  if (course) facts.course = course.toUpperCase()
  return facts
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
  const [facts, setFacts] = useState<KnownFacts>(() => factsFromLocation(location.search))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const nextId = useRef(1)
  const launcherRef = useRef<HTMLButtonElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const transcriptRef = useRef<HTMLDivElement>(null)

  const openingSuggestions = useMemo(
    () =>
      scholarshipId
        ? ['What are the eligibility requirements?', 'Which documents do I need?', 'When is the deadline?']
        : ['Hello', 'I study BTech in Odisha', 'What documents do I usually need?'],
    [scholarshipId],
  )

  // The assistant's own suggested replies from the most recent turn, if any.
  const latestReply = turns[turns.length - 1]?.reply
  const liveSuggestions =
    latestReply?.kind === 'discovery'
      ? latestReply.data.suggested_replies
      : latestReply?.kind === 'question'
        ? latestReply.data.suggested_questions
        : []

  useEffect(() => {
    setOpen(false)
    setDraft('')
    setTurns([])
    setError('')
    setFacts(factsFromLocation(location.search))
    // Resetting per route keeps a detail-page conversation from leaking into the catalog.
  }, [routeKey, location.search])

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

  async function send(rawMessage: string) {
    const message = rawMessage.trim()
    if (!message || loading) return

    const id = nextId.current++
    setTurns((current) => [...current, { id, question: message }])
    setDraft('')
    setError('')
    setLoading(true)

    try {
      let reply: AssistantReply
      if (scholarshipId) {
        const data = await api<ScholarshipQuestionResponse>(
          `/api/ai/scholarships/${scholarshipId}/questions`,
          {
            method: 'POST',
            body: JSON.stringify({
              question: message,
              preferred_language: user?.preferred_language ?? 'en',
            }),
          },
        )
        reply = { kind: 'question', data }
      } else {
        // Facts accumulated across the conversation travel with every turn, so short
        // messages like "2nd year" still land in the right slot.
        const payload: DiscoveryProfile = {
          ...facts,
          message,
          preferred_language: user?.preferred_language ?? 'en',
        }
        const data = await api<DiscoveryResponse>('/api/ai/discover', {
          method: 'POST',
          body: JSON.stringify(payload),
        })
        setFacts((current) => mergeFacts(current, data.extracted))
        reply = { kind: 'discovery', data }
      }
      setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, reply } : turn)))
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 429) {
        setError('That was a lot of questions at once. Give it a minute and try again.')
      } else {
        setError(
          caught instanceof Error ? caught.message : 'The assistant could not answer right now.',
        )
      }
    } finally {
      setLoading(false)
    }
  }

  const factCount = Object.keys(facts).length
  const canSend = !loading && draft.trim().length >= 2

  return (
    <div className="eligibility-assistant">
      {open && (
        <aside
          className="ai-assistant-panel"
          id="eligibility-assistant-panel"
          aria-labelledby="eligibility-assistant-title"
        >
          <header className="ai-assistant-header">
            <div className="ai-assistant-mark">
              <img
                src="/logo.png"
                alt="ScholarSaathi AI"
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            </div>
            <div>
              <h2 id="eligibility-assistant-title">ScholarSaathi AI</h2>
              <p>{scholarshipId ? 'Ask about this scholarship' : 'Find scholarships that fit you'}</p>
            </div>
            <button
              className="ai-icon-button"
              type="button"
              onClick={closeAssistant}
              aria-label="Close scholarship assistant"
            >
              <CloseIcon />
            </button>
          </header>

          {!scholarshipId && factCount > 0 && (
            <div className="ai-fact-strip" aria-label="Details you have shared">
              {facts.state && <span className="ai-fact-pill">{facts.state}</span>}
              {facts.course && <span className="ai-fact-pill">{facts.course}</span>}
              {facts.education_level && <span className="ai-fact-pill">{facts.education_level}</span>}
              {facts.course_year !== undefined && (
                <span className="ai-fact-pill">Year {facts.course_year}</span>
              )}
              {facts.marks_percentage !== undefined && (
                <span className="ai-fact-pill">{facts.marks_percentage}%</span>
              )}
              {facts.family_income_range && (
                <span className="ai-fact-pill">{facts.family_income_range.replaceAll('_', ' ')}</span>
              )}
              {facts.categories?.map((category) => (
                <span className="ai-fact-pill" key={category}>{category.replaceAll('_', ' ')}</span>
              ))}
            </div>
          )}

          <div
            className="ai-transcript"
            ref={transcriptRef}
            role="log"
            aria-live="polite"
            aria-relevant="additions"
          >
            <div className="ai-message ai-message-assistant">
              <p>
                {scholarshipId
                  ? 'Ask me anything about this scholarship. I answer only from what the provider has published, and I will show you the source.'
                  : 'Hi, I am ScholarSaathi. Tell me a little about your studies and I will look for scholarships that fit. You can also just ask me a general question.'}
              </p>
            </div>

            {turns.map((turn) => (
              <div className="ai-turn" key={turn.id}>
                <div className="ai-message ai-message-user"><p>{turn.question}</p></div>
                {turn.reply && (
                  <div className="ai-message ai-message-assistant">
                    {turn.reply.kind === 'discovery' ? (
                      <DiscoveryReply data={turn.reply.data} />
                    ) : (
                      <QuestionReply data={turn.reply.data} />
                    )}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <p className="ai-thinking" role="status">
                <span className="ai-typing"><i /><i /><i /></span>
              </p>
            )}
            {error && <p className="ai-error" role="alert">{error}</p>}
          </div>

          {!loading && (liveSuggestions.length > 0 || turns.length === 0) && (
            <div className="ai-suggestions" aria-label="Suggested replies">
              {(liveSuggestions.length > 0 ? liveSuggestions : openingSuggestions)
                .slice(0, 3)
                .map((suggestion) => (
                  <button key={suggestion} type="button" onClick={() => void send(suggestion)}>
                    {suggestion}
                  </button>
                ))}
            </div>
          )}

          <form
            className="ai-composer"
            onSubmit={(event) => {
              event.preventDefault()
              void send(draft)
            }}
          >
            <label className="sr-only" htmlFor="eligibility-assistant-input">
              Message ScholarSaathi AI
            </label>
            <textarea
              id="eligibility-assistant-input"
              ref={inputRef}
              rows={2}
              maxLength={1200}
              placeholder={scholarshipId ? 'Ask about this scholarship…' : 'Type a message…'}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  if (canSend) void send(draft)
                }
              }}
              disabled={loading}
            />
            <button type="submit" disabled={!canSend} aria-label="Send message">
              <SendIcon />
            </button>
          </form>
          <p className="ai-privacy-note">
            Never share Aadhaar, PAN, bank details, passwords, or OTPs here.
          </p>
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
