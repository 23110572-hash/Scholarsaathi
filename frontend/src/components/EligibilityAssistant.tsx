import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, matchPath, useLocation } from 'react-router-dom'
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  LoaderCircle,
  LogIn,
  Mic,
  Send,
  Sparkles,
  Square,
  X,
} from 'lucide-react'
import { APPLICATION_INTENTS_RESUMED_EVENT } from './IntentResumeCoordinator'
import { useAssistant } from '../context/AssistantContext'
import { useAuth } from '../context/AuthContext'
import { useSpeechRecognition } from '../hooks/useSpeechRecognition'
import { api, ApiError } from '../lib/api'
import type {
  ApplicationIntentBatchResponse,
  ApplicationIntentResponse,
  ChatDetailKey,
  ChatExtractedFacts,
  DiscoveryProfile,
  DiscoveryResponse,
  ScholarshipAssessment,
  ScholarshipQuestionResponse,
  StateOption,
  StudentDocumentType,
  StudentProfile,
} from '../types'

type AssistantReply =
  | { kind: 'discovery'; data: DiscoveryResponse }
  | { kind: 'question'; data: ScholarshipQuestionResponse }
  | { kind: 'application'; data: ApplicationIntentBatchResponse }
  | { kind: 'notice'; message: string }

interface ConversationTurn {
  id: number
  question?: string
  reply?: AssistantReply
}

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
  SUPPORTED_BY_PROVIDER_SOURCE: 'From the provider’s published information',
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

const courseLabels: Record<string, string> = {
  BTECH: 'B.Tech',
  BE: 'B.E.',
  BARCH: 'B.Arch',
  BSC: 'B.Sc',
  BCOM: 'B.Com',
  BA: 'B.A.',
  MBBS: 'MBBS',
  TECHNICAL_DIPLOMA: 'Technical diploma',
  STEM: 'STEM',
  ALL_UNDERGRADUATE: 'Any undergraduate course',
  ALL_RECOGNIZED_COURSES: 'Any recognised course',
}

const educationLabels: Record<string, string> = {
  DIPLOMA: 'Diploma',
  UNDERGRADUATE: 'Undergraduate',
  POSTGRADUATE: 'Postgraduate',
  DOCTORAL: 'Doctoral',
  CLASS_11_12: 'Class 11–12',
}

const incomeLabels: Record<string, string> = {
  UP_TO_250000: 'Income up to ₹2.5L',
  '250001_TO_400000': 'Income ₹2.5–4L',
  '400001_TO_600000': 'Income ₹4–6L',
  '600001_TO_800000': 'Income ₹6–8L',
  ABOVE_800000: 'Income above ₹8L',
}

const documentLabels: Record<StudentDocumentType, string> = {
  CLASS_10_MARKSHEET: 'Class 10 marksheet',
  CLASS_12_MARKSHEET: 'Class 12 marksheet',
  CURRENT_MARKSHEET: 'Current marksheet',
  INCOME_CERTIFICATE: 'Income certificate',
  CATEGORY_CERTIFICATE: 'Category certificate',
  DOMICILE_CERTIFICATE: 'Domicile certificate',
  DISABILITY_CERTIFICATE: 'Disability certificate',
}

function titleCase(value: string): string {
  return value
    .replaceAll('_', ' ')
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function listDetails(keys: ChatDetailKey[]): string {
  const labels = keys.map((key) => detailLabels[key])
  if (labels.length <= 1) return labels.join('')
  return `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}`
}

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

function factsFromProfile(profile: StudentProfile): KnownFacts {
  return {
    ...(profile.state_code ? { state: profile.state_code } : {}),
    ...(profile.education_level ? { education_level: profile.education_level } : {}),
    ...(profile.course ? { course: profile.course } : {}),
    ...(profile.course_year !== null ? { course_year: profile.course_year } : {}),
    ...(profile.marks_percentage !== null ? { marks_percentage: profile.marks_percentage } : {}),
    ...(profile.family_income_range ? { family_income_range: profile.family_income_range } : {}),
    ...(profile.categories.length > 0 ? { categories: profile.categories } : {}),
  }
}

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

function isExplicitApplyCommand(message: string): boolean {
  const normalised = message.trim().toLowerCase()
  if (!/\b(apply|submit)\b/.test(normalised)) return false
  return !/\b(how (?:do|can|should) i apply|how to apply|where (?:do|can) i apply|application process|steps to apply)\b/.test(
    normalised,
  )
}

function DiscoveryReply({
  data,
  onApply,
}: {
  data: DiscoveryResponse
  onApply: (scholarshipId: string, title: string) => void
}) {
  if (data.mode === 'CONVERSATION') {
    return (
      <div className="ai-reply-content">
        {data.introduction && <p>{data.introduction}</p>}
        {data.requested_details.length > 0 && (
          <p className="ai-detail-request">
            Share your {listDetails(data.requested_details)} and I can compare the published rules.
          </p>
        )}
      </div>
    )
  }

  const assessmentByVersion = new Map(
    data.assessments.map((assessment) => [assessment.scholarship_version_id, assessment]),
  )
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
        <p>I need a little more information before I can suggest a reliable match.</p>
      ) : (
        <div className="ai-match-list">
          {results.map(({ scholarship, assessment }) => (
            <article className="ai-match-card" key={scholarship.id}>
              <div className="ai-match-card-topline">
                <span
                  className={`ai-assessment ai-assessment-${assessment.assessment.toLowerCase()}`}
                >
                  {assessmentLabels[assessment.assessment]}
                </span>
                {scholarship.application_deadline_at && (
                  <small>{new Date(scholarship.application_deadline_at).toLocaleDateString('en-IN')}</small>
                )}
              </div>
              <h3>{scholarship.title}</h3>
              <small>{scholarship.organization.display_name}</small>
              <p>{assessment.summary}</p>
              {assessment.matching_points[0] && (
                <p className="ai-match-why">{assessment.matching_points[0].statement}</p>
              )}
              <div className="ai-result-actions">
                <Link to={`/scholarships/${scholarship.id}`}>View details</Link>
                {assessment.assessment !== 'LIKELY_NOT_ELIGIBLE' && (
                  <button type="button" onClick={() => onApply(scholarship.id, scholarship.title)}>
                    Apply with AI
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      {data.requested_details.length > 0 && (
        <p className="ai-detail-request">
          Tell me your {listDetails(data.requested_details)} to sharpen these matches.
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

function intentAction(item: ApplicationIntentResponse) {
  if (item.outcome === 'AUTH_REQUIRED') {
    return { to: '/login/student', label: 'Sign in and continue', icon: <LogIn size={15} /> }
  }
  if (item.outcome === 'PROFILE_REQUIRED' || item.outcome === 'DOCUMENTS_REQUIRED') {
    return {
      to: item.outcome === 'DOCUMENTS_REQUIRED' ? '/student/profile#documents' : '/student/profile',
      label: item.outcome === 'DOCUMENTS_REQUIRED' ? 'Upload documents' : 'Complete profile',
      icon: <FileText size={15} />,
    }
  }
  if (item.application_id) {
    return {
      to: `/applications/${item.application_id}`,
      label: 'Track application',
      icon: <CheckCircle2 size={15} />,
    }
  }
  return null
}

function ApplicationReply({ data, returnPath }: { data: ApplicationIntentBatchResponse; returnPath: string }) {
  return (
    <div className="ai-application-results">
      {data.items.map((item) => {
        const action = intentAction(item)
        const submitted = item.outcome === 'SUBMITTED'
        return (
          <article
            className={`ai-application-card ${submitted ? 'ai-application-card-success' : ''}`}
            key={item.intent_id}
          >
            <div className="ai-application-status">
              {submitted ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
              <span>{submitted ? 'Application submitted' : item.assistant_message}</span>
            </div>
            <h3>{item.scholarship_title}</h3>
            {item.missing_profile_fields.length > 0 && (
              <p>
                <strong>Profile needed:</strong>{' '}
                {item.missing_profile_fields.map(titleCase).join(', ')}
              </p>
            )}
            {item.missing_document_types.length > 0 && (
              <p>
                <strong>Documents needed:</strong>{' '}
                {item.missing_document_types.map((type) => documentLabels[type]).join(', ')}
              </p>
            )}
            {action && (
              <Link
                className="ai-application-action"
                to={action.to}
                state={item.outcome === 'AUTH_REQUIRED' ? { from: returnPath } : undefined}
              >
                {action.icon} {action.label}
              </Link>
            )}
          </article>
        )
      })}
    </div>
  )
}

export function EligibilityAssistant() {
  const location = useLocation()
  const { user } = useAuth()
  const detailMatch = matchPath('/scholarships/:scholarshipId', location.pathname)
  const isCatalog = location.pathname === '/scholarships'
  const scholarshipId = detailMatch?.params.scholarshipId
  const isVisible = isCatalog || Boolean(scholarshipId)
  const routeKey = scholarshipId ? `detail-${scholarshipId}` : isCatalog ? 'catalog' : 'hidden'
  const {
    open,
    closeAssistant: closePanel,
    toggleAssistant,
    pendingQuestion,
    clearPendingQuestion,
  } = useAssistant()
  const [draft, setDraft] = useState('')
  const [turns, setTurns] = useState<ConversationTurn[]>([])
  const [facts, setFacts] = useState<KnownFacts>(() => factsFromLocation(location.search))
  const [stateNames, setStateNames] = useState<Record<string, string>>({})
  const [recentScholarshipIds, setRecentScholarshipIds] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingLabel, setLoadingLabel] = useState('Thinking…')
  const [error, setError] = useState('')
  const nextId = useRef(1)
  const loadingRef = useRef(false)
  const launcherRef = useRef<HTMLButtonElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const transcriptRef = useRef<HTMLDivElement>(null)

  const appendVoiceTranscript = useCallback((transcript: string) => {
    setDraft((current) => `${current}${current.trim() ? ' ' : ''}${transcript}`)
  }, [])
  const speech = useSpeechRecognition(user?.preferred_language ?? 'en', appendVoiceTranscript)

  const openingSuggestions = useMemo(
    () =>
      scholarshipId
        ? ['Am I eligible?', 'Which documents do I need?', 'Apply for this scholarship']
        : ['Find scholarships for me', 'I study BTech in Odisha', 'What documents do I need?'],
    [scholarshipId],
  )

  const factPills = useMemo(() => {
    const pills: string[] = []
    if (facts.state) pills.push(stateNames[facts.state] ?? facts.state)
    if (facts.education_level) {
      pills.push(educationLabels[facts.education_level] ?? titleCase(facts.education_level))
    }
    if (facts.course) pills.push(courseLabels[facts.course] ?? titleCase(facts.course))
    if (facts.course_year !== undefined) pills.push(`Year ${facts.course_year}`)
    if (facts.marks_percentage !== undefined) pills.push(`${facts.marks_percentage}%`)
    if (facts.family_income_range) {
      pills.push(incomeLabels[facts.family_income_range] ?? titleCase(facts.family_income_range))
    }
    facts.categories?.forEach((category) => pills.push(titleCase(category)))
    return pills
  }, [facts, stateNames])

  const latestReply = turns[turns.length - 1]?.reply
  const liveSuggestions =
    latestReply?.kind === 'discovery'
      ? latestReply.data.suggested_replies
      : latestReply?.kind === 'question'
        ? latestReply.data.suggested_questions
        : []

  useEffect(() => {
    setDraft('')
    setTurns([])
    setError('')
    setRecentScholarshipIds([])
    setFacts(factsFromLocation(location.search))
    speech.abort()
  }, [routeKey, location.search]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (user?.realm !== 'STUDENT') return
    let cancelled = false
    void api<StudentProfile>('/api/student/profile')
      .then((profile) => {
        if (!cancelled) setFacts((current) => ({ ...factsFromProfile(profile), ...current }))
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [user?.id])

  useEffect(() => {
    if (!open || Object.keys(stateNames).length > 0) return
    let cancelled = false
    void api<StateOption[]>('/api/states')
      .then((options) => {
        if (!cancelled) {
          setStateNames(Object.fromEntries(options.map((option) => [option.code, option.name])))
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [open, stateNames])

  useEffect(() => {
    const handleResumed = (event: Event) => {
      const result = (event as CustomEvent<ApplicationIntentBatchResponse>).detail
      if (!result?.items.length) return
      setTurns((current) => [
        ...current,
        { id: nextId.current++, reply: { kind: 'application', data: result } },
      ])
    }
    window.addEventListener(APPLICATION_INTENTS_RESUMED_EVENT, handleResumed)
    return () => window.removeEventListener(APPLICATION_INTENTS_RESUMED_EVENT, handleResumed)
  }, [])

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        speech.abort()
        closePanel()
        launcherRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [open, closePanel, speech.abort])

  useEffect(() => {
    if (open && transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
    }
  }, [open, turns, loading])

  const performApplication = useCallback(
    async (ids: string[], question: string) => {
      if (ids.length === 0) {
        const id = nextId.current++
        setTurns((current) => [
          ...current,
          {
            id,
            question,
            reply: {
              kind: 'notice',
              message: 'First ask me to find scholarships, then tell me which results to apply for.',
            },
          },
        ])
        return
      }
      if (loadingRef.current) return
      loadingRef.current = true
      const id = nextId.current++
      setTurns((current) => [...current, { id, question }])
      setDraft('')
      setError('')
      setLoading(true)
      setLoadingLabel(user?.realm === 'STUDENT' ? 'Checking profile and documents…' : 'Saving your request…')
      try {
        const data = await api<ApplicationIntentBatchResponse>('/api/application-intents', {
          method: 'POST',
          body: JSON.stringify({
            scholarship_ids: ids.slice(0, 5),
            explicit_apply_authorization: true,
            authorization_source: 'ASSISTANT_EXPLICIT_APPLY',
          }),
        })
        setTurns((current) =>
          current.map((turn) =>
            turn.id === id ? { ...turn, reply: { kind: 'application', data } } : turn,
          ),
        )
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : 'The application request could not be completed.')
      } finally {
        loadingRef.current = false
        setLoading(false)
      }
    },
    [user?.realm],
  )

  const send = useCallback(
    async (rawMessage: string) => {
      const message = rawMessage.trim()
      if (!message || loadingRef.current) return
      if (isExplicitApplyCommand(message)) {
        const targets = scholarshipId ? [scholarshipId] : recentScholarshipIds
        await performApplication(targets, message)
        return
      }

      loadingRef.current = true
      const id = nextId.current++
      setTurns((current) => [...current, { id, question: message }])
      setDraft('')
      setError('')
      setLoading(true)
      setLoadingLabel(scholarshipId ? 'Checking the provider source…' : 'Searching scholarships…')

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
          const assessed = new Set(data.assessments.map((item) => item.scholarship_version_id))
          const targetIds = data.candidates
            .filter((candidate) => assessed.has(candidate.version_id))
            .slice(0, 5)
            .map((candidate) => candidate.id)
          if (targetIds.length > 0) setRecentScholarshipIds(targetIds)
          reply = { kind: 'discovery', data }
        }
        setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, reply } : turn)))
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 429) {
          setError('That was a lot of requests at once. Wait a minute and try again.')
        } else {
          setError(caught instanceof Error ? caught.message : 'The assistant could not answer right now.')
        }
      } finally {
        loadingRef.current = false
        setLoading(false)
      }
    },
    [scholarshipId, recentScholarshipIds, performApplication, user?.preferred_language, facts],
  )

  useEffect(() => {
    if (!open || !pendingQuestion) return
    const question = pendingQuestion
    clearPendingQuestion()
    void send(question)
  }, [open, pendingQuestion, clearPendingQuestion, send])

  if (!isVisible) return null

  function closeAssistant() {
    speech.abort()
    closePanel()
    launcherRef.current?.focus()
  }

  const canSend = !loading && !speech.listening && draft.trim().length >= 2
  const returnPath = `${location.pathname}${location.search}${location.hash}`

  return (
    <div className="eligibility-assistant">
      {open && (
        <aside
          className="ai-assistant-panel"
          id="eligibility-assistant-panel"
          role="dialog"
          aria-modal="false"
          aria-labelledby="eligibility-assistant-title"
        >
          <header className="ai-assistant-header">
            <div className="ai-assistant-mark" aria-hidden="true">
              <img src="/logo.png" alt="" />
            </div>
            <div className="ai-assistant-heading">
              <h2 id="eligibility-assistant-title">ScholarSaathi</h2>
            </div>
            <button className="ai-icon-button" type="button" onClick={closeAssistant} aria-label="Close assistant">
              <X size={19} />
            </button>
          </header>

          {!scholarshipId && factPills.length > 0 && (
            <div className="ai-fact-strip" aria-label="Details being used">
              <span className="ai-fact-strip-label">Your profile</span>
              <div className="ai-fact-scroll">
                {factPills.map((pill) => <span className="ai-fact-pill" key={pill}>{pill}</span>)}
              </div>
              <button className="ai-fact-clear" type="button" onClick={() => setFacts({})}>Clear</button>
            </div>
          )}

          <div className="ai-transcript" ref={transcriptRef} role="log" aria-live="polite">
            <div className="ai-welcome">
              <span><Sparkles size={19} /></span>
              <strong>Hello, how can I help you?</strong>
            </div>

            {turns.map((turn) => (
              <div className="ai-turn" key={turn.id}>
                {turn.question && <div className="ai-message ai-message-user"><p>{turn.question}</p></div>}
                {turn.reply && (
                  <div className="ai-message ai-message-assistant">
                    {turn.reply.kind === 'discovery' && (
                      <DiscoveryReply
                        data={turn.reply.data}
                        onApply={(id, title) => void performApplication([id], `Apply for ${title}`)}
                      />
                    )}
                    {turn.reply.kind === 'question' && <QuestionReply data={turn.reply.data} />}
                    {turn.reply.kind === 'application' && (
                      <ApplicationReply data={turn.reply.data} returnPath={returnPath} />
                    )}
                    {turn.reply.kind === 'notice' && <p>{turn.reply.message}</p>}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="ai-progress" role="status">
                <LoaderCircle size={17} />
                <span>{loadingLabel}</span>
              </div>
            )}
            {error && <p className="ai-error" role="alert">{error}</p>}
          </div>

          {!loading && (liveSuggestions.length > 0 || turns.length === 0) && (
            <div className="ai-suggestions" aria-label="Suggested messages">
              {(liveSuggestions.length > 0 ? liveSuggestions : openingSuggestions).slice(0, 3).map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => void send(suggestion)}>{suggestion}</button>
              ))}
            </div>
          )}

          {(speech.listening || speech.interimTranscript) && (
            <div className="ai-listening" role="status">
              <span className="ai-listening-pulse" />
              <strong>Listening</strong>
              <span>{speech.interimTranscript || 'Speak now…'}</span>
            </div>
          )}
          {(speech.error || (!speech.supported && open)) && (
            <p className="ai-voice-note" role="status">
              {speech.error || 'Voice input is not supported in this browser. You can continue typing.'}
            </p>
          )}

          <form
            className="ai-composer"
            onSubmit={(event) => {
              event.preventDefault()
              void send(draft)
            }}
          >
            <textarea
              id="eligibility-assistant-input"
              ref={inputRef}
              rows={1}
              maxLength={1200}
              aria-label="Message ScholarSaathi"
              placeholder={speech.listening ? 'Listening…' : scholarshipId ? 'Ask or say “apply for me”…' : 'Message ScholarSaathi…'}
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
            <button
              className={`ai-mic-button ${speech.listening ? 'is-listening' : ''}`}
              type="button"
              onClick={speech.listening ? speech.stop : speech.start}
              disabled={!speech.supported || loading}
              aria-label={speech.listening ? 'Stop listening' : 'Speak your message'}
              aria-pressed={speech.listening}
              title={speech.supported ? 'Speak your message' : 'Voice input is unavailable'}
            >
              {speech.listening ? <Square size={17} fill="currentColor" /> : <Mic size={19} />}
            </button>
            <button className="ai-send-button" type="submit" disabled={!canSend} aria-label="Send message">
              <Send size={18} />
            </button>
          </form>
        </aside>
      )}

      <button
        className="ai-assistant-launcher"
        ref={launcherRef}
        type="button"
        onClick={toggleAssistant}
        aria-label={open ? 'Close ScholarSaathi assistant' : 'Open ScholarSaathi assistant'}
        aria-expanded={open}
        aria-controls="eligibility-assistant-panel"
      >
        {open ? <X size={22} /> : <img src="/ai-logo.png" alt="" className="ai-launcher-logo" />}
      </button>
    </div>
  )
}
