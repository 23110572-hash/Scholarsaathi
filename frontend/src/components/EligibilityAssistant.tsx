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
  ChatTurn,
  ConversationFieldValues,
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
  gender: string
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
  gender: 'gender',
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
  if (extracted.gender) next.gender = extracted.gender
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
    ...(profile.gender ? { gender: profile.gender } : {}),
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

const APPLY_SUGGESTION = 'Apply for this scholarship'
const APPLY_WAVE_SIZE = 3

/** Provider form bindings the workflow reports as missing, in student-facing words. */
const bindingLabels: Record<string, string> = {
  state_code: 'State or UT',
  course: 'course',
  course_year: 'study year',
  marks_percentage: 'marks percentage',
  family_income_range: 'family income range',
  // Legacy provider templates can report the raw form key instead of a profile binding.
  academic_score: 'marks percentage',
  domicile_state: 'State or UT',
  family_income_band: 'family income range',
}

/** Set when an apply request needs sign-in, so the resumed result is shown in chat. */
const APPLY_RESUME_KEY = 'scholarsaathi:resume-apply-in-chat'

/** Which known fact answers a provider form binding the workflow reported as missing. */
const bindingFactKeys: Record<string, keyof KnownFacts> = {
  state_code: 'state',
  domicile_state: 'state',
  course: 'course',
  course_year: 'course_year',
  marks_percentage: 'marks_percentage',
  academic_score: 'marks_percentage',
  family_income_range: 'family_income_range',
  family_income_band: 'family_income_range',
}

/** Chat-stated values for one submission. Never written to the student profile. */
function conversationFieldsFromFacts(facts: KnownFacts): ConversationFieldValues {
  return {
    ...(facts.state ? { state_code: facts.state } : {}),
    ...(facts.course ? { course: facts.course } : {}),
    ...(facts.course_year !== undefined ? { course_year: facts.course_year } : {}),
    ...(facts.marks_percentage !== undefined ? { marks_percentage: facts.marks_percentage } : {}),
    ...(facts.family_income_range ? { family_income_range: facts.family_income_range } : {}),
  }
}

function replyToHistoryText(reply: AssistantReply): string {
  if (reply.kind === 'notice') return reply.message
  if (reply.kind === 'question') return reply.data.answer
  if (reply.kind === 'application') {
    return reply.data.items
      .map((item) => `${item.scholarship_title}: ${item.assistant_message}`)
      .join(' | ')
  }
  if (reply.data.mode === 'CONVERSATION') return reply.data.introduction ?? ''
  const titles = reply.data.candidates.map((candidate) => candidate.title).join('; ')
  return `${reply.data.introduction ?? ''}${titles ? ` Matches shown: ${titles}` : ''}`.trim()
}

/** Whole-session transcript so the model never treats a turn as a new conversation. */
function buildHistory(turns: ConversationTurn[]): ChatTurn[] {
  const history: ChatTurn[] = []
  turns.forEach((turn) => {
    if (turn.question) history.push({ role: 'STUDENT', text: turn.question.slice(0, 900) })
    if (turn.reply) {
      const text = replyToHistoryText(turn.reply).slice(0, 900)
      if (text) history.push({ role: 'ASSISTANT', text })
    }
  })
  return history.slice(-24)
}

function containsSensitiveInformation(message: string): boolean {
  return /\b(?:aadhaar|aadhar|pan(?:\s+(?:card|number|no))?|bank\s+(?:account|details)|account\s+number|ifsc|upi(?:\s+id)?|otp|password|passcode|cvv|credit\s+card|debit\s+card)\b/i.test(message)
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
  const fallbackCandidates = results.length === 0 ? data.candidates.slice(0, 4) : []

  return (
    <div className="ai-reply-content">
      {data.introduction && <p>{data.introduction}</p>}
      {results.length > 0 ? (
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
      ) : fallbackCandidates.length > 0 ? (
        <div className="ai-match-list">
          {fallbackCandidates.map((scholarship) => (
            <article className="ai-match-card" key={scholarship.id}>
              <div className="ai-match-card-topline">
                <span className="ai-assessment">Catalog match</span>
                {scholarship.application_deadline_at && (
                  <small>{new Date(scholarship.application_deadline_at).toLocaleDateString('en-IN')}</small>
                )}
              </div>
              <h3>{scholarship.title}</h3>
              <small>{scholarship.organization.display_name}</small>
              <p>{scholarship.summary}</p>
              <div className="ai-result-actions">
                <Link to={`/scholarships/${scholarship.id}`}>Review details</Link>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p>I need a little more information before I can suggest a reliable match.</p>
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
                <strong>Please update these documents in your profile:</strong>{' '}
                {item.missing_document_types.map((type) => documentLabels[type]).join(', ')}. I
                cannot accept files in chat, so upload them in your profile and I will continue.
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
  const turnsRef = useRef<ConversationTurn[]>([])
  const [facts, setFacts] = useState<KnownFacts>(() => factsFromLocation(location.search))
  const [stateNames, setStateNames] = useState<Record<string, string>>({})
  const [recentScholarshipIds, setRecentScholarshipIds] = useState<string[]>([])
  const recentScholarshipIdsRef = useRef<string[]>([])
  const [applyQueue, setApplyQueue] = useState<string[]>([])
  const [retryIds, setRetryIds] = useState<string[]>([])
  const profileFactsRef = useRef<KnownFacts>({})
  const [hasProfileFacts, setHasProfileFacts] = useState(false)
  const factsRef = useRef<KnownFacts>({})
  const retryIdsRef = useRef<string[]>([])
  const neededBindingsRef = useRef<string[]>([])
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

  const openingSuggestions = useMemo(() => {
    if (scholarshipId) return ['Am I eligible?', 'Which documents do I need?', APPLY_SUGGESTION]
    // A signed-in student with saved details should be one tap from their matches.
    return hasProfileFacts ? ['Find my eligible scholarships'] : []
  }, [scholarshipId, hasProfileFacts])

  const factPills = useMemo(() => {
    const pills: string[] = []
    if (facts.state) pills.push(stateNames[facts.state] ?? facts.state)
    if (facts.gender && facts.gender !== 'PREFER_NOT_TO_SAY') pills.push(titleCase(facts.gender))
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
    recentScholarshipIdsRef.current = recentScholarshipIds
  }, [recentScholarshipIds])

  useEffect(() => {
    turnsRef.current = turns
  }, [turns])

  useEffect(() => {
    factsRef.current = facts
  }, [facts])

  useEffect(() => {
    retryIdsRef.current = retryIds
  }, [retryIds])

  // Reset only when the assistant changes context (catalog vs a specific scholarship).
  // Filter or query changes must not erase the running conversation.
  useEffect(() => {
    setDraft('')
    setTurns([])
    setError('')
    setRecentScholarshipIds([])
    recentScholarshipIdsRef.current = []
    turnsRef.current = []
    setApplyQueue([])
    setRetryIds([])
    retryIdsRef.current = []
    neededBindingsRef.current = []
    const baseFacts = { ...profileFactsRef.current, ...factsFromLocation(location.search) }
    factsRef.current = baseFacts
    setFacts(baseFacts)
    speech.abort()
  }, [routeKey]) // eslint-disable-line react-hooks/exhaustive-deps

  // A signed-in student's stored profile is the baseline for every turn. It is refetched
  // when the panel opens so profile edits are picked up, and kept in a ref so switching
  // between the catalog and a scholarship page never loses it.
  useEffect(() => {
    if (user?.realm !== 'STUDENT') {
      profileFactsRef.current = {}
      setHasProfileFacts(false)
      return
    }
    let cancelled = false
    void api<StudentProfile>('/api/student/profile')
      .then((profile) => {
        if (cancelled) return
        const profileFacts = factsFromProfile(profile)
        profileFactsRef.current = profileFacts
        setHasProfileFacts(Object.keys(profileFacts).length > 0)
        setFacts((current) => {
          const merged = { ...profileFacts, ...current }
          factsRef.current = merged
          return merged
        })
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [user?.id, open])

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
      // Only report a resumed workflow when the student asked to apply and was sent to
      // sign in. Opening the assistant otherwise must not dump earlier pending requests.
      if (sessionStorage.getItem(APPLY_RESUME_KEY) !== '1') return
      sessionStorage.removeItem(APPLY_RESUME_KEY)
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
    async (ids: string[], question?: string, factsOverride?: KnownFacts) => {
      if (ids.length === 0) {
        const id = nextId.current++
        setTurns((current) => [
          ...current,
          {
            id,
            ...(question ? { question } : {}),
            reply: {
              kind: 'notice',
              message:
                'I do not have any matched scholarships in this chat yet. Share your state, course, study year, marks, and family income and I will find your matches, then apply.',
            },
          },
        ])
        return
      }
      if (loadingRef.current) return
      loadingRef.current = true

      // Apply in small waves so the student sees each result instead of waiting on a
      // long batch, and so every wave carries its own explicit authorization.
      const wave = ids.slice(0, APPLY_WAVE_SIZE)
      const remaining = ids.slice(APPLY_WAVE_SIZE)
      const id = nextId.current++
      setTurns((current) => [
        ...current,
        ...(question ? [{ id: nextId.current++, question }] : []),
        ...(remaining.length > 0
          ? [
              {
                id: nextId.current++,
                reply: {
                  kind: 'notice' as const,
                  message: `Starting with the best ${wave.length} matches for your profile. Once these finish I will continue with the remaining ${remaining.length}.`,
                },
              },
            ]
          : []),
        { id },
      ])
      setDraft('')
      setError('')
      setLoading(true)
      setLoadingLabel(user?.realm === 'STUDENT' ? 'Checking profile and documents…' : 'Saving your request…')
      try {
        const data = await api<ApplicationIntentBatchResponse>('/api/application-intents', {
          method: 'POST',
          body: JSON.stringify({
            scholarship_ids: wave,
            // Read from the override or the ref, never from a captured render value: the
            // detail the student just typed must reach this request in the same tick.
            conversation_fields: conversationFieldsFromFacts(factsOverride ?? factsRef.current),
            explicit_apply_authorization: true,
            authorization_source: 'ASSISTANT_EXPLICIT_APPLY',
          }),
        })
        setTurns((current) =>
          current.map((turn) =>
            turn.id === id ? { ...turn, reply: { kind: 'application', data } } : turn,
          ),
        )
        setApplyQueue(remaining)
        if (data.items.some((item) => item.outcome === 'AUTH_REQUIRED')) {
          sessionStorage.setItem(APPLY_RESUME_KEY, '1')
        }

        // Anything still missing is asked for in chat. The student answers here and the
        // retry reuses those values for the submission without touching their profile.
        const blocked = data.items.filter((item) => item.outcome === 'PROFILE_REQUIRED')
        const needed = Array.from(
          new Set(blocked.flatMap((item) => item.missing_profile_fields)),
        )
        const blockedIds = blocked.map((item) => item.scholarship_id)
        setRetryIds(blockedIds)
        retryIdsRef.current = blockedIds
        neededBindingsRef.current = needed
        if (needed.length > 0) {
          setTurns((current) => [
            ...current,
            {
              id: nextId.current++,
              reply: {
                kind: 'notice',
                message: `To finish ${blocked.length === 1 ? 'this application' : `these ${blocked.length} applications`} I still need your ${needed
                  .map((field) => bindingLabels[field] ?? titleCase(field))
                  .join(', ')}. Tell me here in chat and I will complete ${blocked.length === 1 ? 'it' : 'them'}.`,
              },
            },
          ])
        }
      } catch (caught) {
        setTurns((current) => current.filter((turn) => turn.id !== id))
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
      if (scholarshipId && message.length < 3) {
        setError('Please enter at least three characters for a scholarship question.')
        return
      }
      if (containsSensitiveInformation(message)) {
        const id = nextId.current++
        setTurns((current) => [
          ...current,
          {
            id,
            question: 'Sensitive information removed for your safety.',
            reply: {
              kind: 'notice',
              message: 'Please do not share Aadhaar, PAN, bank, card, password, or OTP details in chat. Upload requested evidence only through the secure document area.',
            },
          },
        ])
        setDraft('')
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
            history: buildHistory(turnsRef.current),
            message,
            preferred_language: user?.preferred_language ?? 'en',
          }
          const data = await api<DiscoveryResponse>('/api/ai/discover', {
            method: 'POST',
            body: JSON.stringify(payload),
          })
          // Merge synchronously so this turn's detail is available immediately, instead of
          // waiting for the next render.
          const nextFacts = mergeFacts(factsRef.current, data.extracted)
          factsRef.current = nextFacts
          setFacts(nextFacts)

          const waitingIds = retryIdsRef.current
          const suppliedNeeded = neededBindingsRef.current.some((binding) => {
            const factKey = bindingFactKeys[binding]
            return factKey !== undefined && nextFacts[factKey] !== undefined
          })

          // Applications are already waiting on a detail and the student just gave it, so
          // finish those rather than starting anything new. This is driven by workflow
          // state and the model's extracted facts, not by reading the student's wording.
          if (waitingIds.length > 0 && suppliedNeeded) {
            loadingRef.current = false
            setLoading(false)
            setTurns((current) => current.filter((turn) => turn.id !== id))
            await performApplication(waitingIds, message, nextFacts)
            return
          }

          // The model decided this turn is an instruction to apply. Prefer applications
          // already waiting on this student before opening new ones.
          if (data.intent === 'APPLY_REQUEST') {
            loadingRef.current = false
            setLoading(false)
            setTurns((current) => current.filter((turn) => turn.id !== id))
            await performApplication(
              waitingIds.length > 0 ? waitingIds : recentScholarshipIdsRef.current,
              message,
              nextFacts,
            )
            return
          }

          const eligibleAssessments = new Set(
            data.assessments
              .filter((item) => item.assessment !== 'LIKELY_NOT_ELIGIBLE')
              .map((item) => item.scholarship_version_id),
          )
          const rankByVersion = new Map(
            data.assessments.map((item) => [
              item.scholarship_version_id,
              assessmentRank[item.assessment],
            ]),
          )
          // Strongest matches first so an "apply to all" wave starts with the best 3.
          const targetIds = data.candidates
            .filter((candidate) => eligibleAssessments.has(candidate.version_id))
            .sort(
              (left, right) =>
                (rankByVersion.get(left.version_id) ?? 9) -
                (rankByVersion.get(right.version_id) ?? 9),
            )
            .slice(0, 12)
            .map((candidate) => candidate.id)
          // Only replace remembered matches when this turn actually produced matches, so a
          // follow-up message never erases what the student is referring to.
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
    [scholarshipId, performApplication, user?.preferred_language, facts],
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

  const canSend = !loading && !speech.listening && draft.trim().length >= (scholarshipId ? 3 : 2)
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

          {factPills.length > 0 && (
            <div className="ai-fact-strip" aria-label="Details being used">
              <span className="ai-fact-strip-label">Your profile</span>
              <div className="ai-fact-scroll">
                {factPills.map((pill) => <span className="ai-fact-pill" key={pill}>{pill}</span>)}
              </div>
              <button
                className="ai-fact-clear"
                type="button"
                onClick={() => {
                  setFacts({ ...profileFactsRef.current })
                  setRecentScholarshipIds([])
                }}
              >
                Clear
              </button>
            </div>
          )}

          <div className="ai-transcript" ref={transcriptRef} role="log" aria-live="polite">
            <div className="ai-welcome">
              {hasProfileFacts ? (
                <>
                  <strong>
                    {user?.display_alias ? `Hello ${user.display_alias},` : 'Hello,'} I already have
                    your saved profile details.
                  </strong>
                  <p>
                    I will use {factPills.slice(0, 4).join(', ')}
                    {factPills.length > 4 ? ` and ${factPills.length - 4} more` : ''}. You do not
                    need to type them again.
                  </p>
                </>
              ) : (
                <strong>Hello, how can I help you?</strong>
              )}
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

          {!loading && (applyQueue.length > 0 || retryIds.length > 0) && (
            <div className="ai-suggestions" aria-label="Continue applying">
              {retryIds.length > 0 && (
                <button type="button" onClick={() => void performApplication(retryIds)}>
                  Finish {retryIds.length === 1 ? 'it' : `those ${retryIds.length}`} with my details
                </button>
              )}
              {applyQueue.length > 0 && (
                <button type="button" onClick={() => void performApplication(applyQueue)}>
                  Continue with the next {Math.min(applyQueue.length, APPLY_WAVE_SIZE)}
                </button>
              )}
            </div>
          )}

          {!loading && (liveSuggestions.length > 0 || turns.length === 0) && (
            <div className="ai-suggestions" aria-label="Suggested messages">
              {(liveSuggestions.length > 0 ? liveSuggestions : openingSuggestions).slice(0, 3).map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() =>
                    scholarshipId && suggestion === APPLY_SUGGESTION
                      ? void performApplication([scholarshipId], suggestion)
                      : void send(suggestion)
                  }
                >
                  {suggestion}
                </button>
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
