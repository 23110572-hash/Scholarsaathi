export type AccountRealm = 'STUDENT' | 'ORGANIZATION_MEMBER'
export type OrganizationType =
  | 'CENTRAL_GOVERNMENT'
  | 'STATE_GOVERNMENT'
  | 'PRIVATE_COMPANY'
  | 'NGO'

export interface OrganizationSummary {
  id: string
  display_name: string
  organization_type: OrganizationType
  ownership_domain: string
  jurisdiction_state_code: string | null
  member_role: string | null
}

export interface SessionUser {
  id: string
  login_identifier: string
  realm: AccountRealm
  display_alias: string | null
  preferred_language: string | null
  organization: OrganizationSummary | null
}

export interface StudentRegistrationInput {
  email: string
  password: string
  password_confirmation: string
  display_alias?: string
  preferred_language: string
}

export interface StateOption {
  code: string
  name: string
  is_union_territory: boolean
}

/** Sent to PUT /api/student/profile. The endpoint replaces the whole profile, so every
 *  field must be present on each save or omitted fields are cleared. */
export interface StudentProfileInput {
  full_name: string | null
  display_alias: string | null
  state_code: string | null
  education_level: string | null
  course: string | null
  course_year: number | null
  marks_percentage: number | null
  family_income_range: string | null
  categories: string[]
  preferred_language: string
  photo_data_url: string | null
}

export interface StudentProfile extends StudentProfileInput {
  completeness: number
  updated_at: string | null
}

export interface SavedScholarshipResponse {
  scholarship_id: string
  saved: boolean
}

export interface Scholarship {
  id: string
  version_id: string
  slug: string
  title: string
  summary: string
  academic_year: string
  scope: string
  applicable_state_codes: string[]
  education_levels: string[]
  course_families: string[]
  category_tags: string[]
  benefit_summary: string
  benefit_amount_min: number | null
  benefit_amount_max: number | null
  application_deadline_at: string | null
  official_source_url: string
  last_provider_confirmed_at: string
  publication_status: string
  organization: OrganizationSummary
}

export interface ScholarshipList {
  items: Scholarship[]
  total: number
}

export interface DiscoveryProfile {
  message?: string
  state?: string
  education_level?: string
  course?: string
  course_year?: number
  marks_percentage?: number
  family_income_range?: string
  categories?: string[]
  preferred_language: string
}

export interface Evidence {
  citation_id: string
  section_title: string
  page_number: number | null
  text: string
}

export interface ApplicationField {
  id: string
  field_key: string
  label: string
  help_text: string
  field_type: 'TEXT' | 'NUMBER' | 'DATE' | 'SELECT' | 'MULTISELECT' | 'CHECKBOX' | 'TEXTAREA'
  required: boolean
  options: string[] | null
  sort_order: number
}

export interface ScholarshipDetail extends Scholarship {
  knowledge_summary: string
  provider_helpdesk_url: string
  evidence: Evidence[]
  application_template_id: string | null
  application_fields: ApplicationField[]
}

export type AssessmentLabel =
  | 'LIKELY_ELIGIBLE'
  | 'POSSIBLY_ELIGIBLE_NEEDS_INFORMATION'
  | 'LIKELY_NOT_ELIGIBLE'
  | 'CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION'

export interface AIClaim {
  statement: string
  citation_ids: string[]
}

export interface ScholarshipAssessment {
  scholarship_version_id: string
  assessment: AssessmentLabel
  confidence: number
  summary: string
  matching_points: AIClaim[]
  possible_conflicts: AIClaim[]
  missing_information: string[]
  next_steps: string[]
  warning: string
}

export type ChatIntent =
  | 'GREETING'
  | 'SMALL_TALK'
  | 'GENERAL_QUESTION'
  | 'SHARING_DETAILS'
  | 'SCHOLARSHIP_SEARCH'
  | 'OUT_OF_SCOPE'

export type ChatDetailKey =
  | 'state'
  | 'education_level'
  | 'course'
  | 'course_year'
  | 'marks_percentage'
  | 'family_income_range'
  | 'categories'

/** Eligibility facts the assistant picked out of the student's own words this turn. */
export interface ChatExtractedFacts {
  state: string | null
  education_level: string | null
  course: string | null
  course_year: number | null
  marks_percentage: number | null
  family_income_range: string | null
  categories: string[]
}

export interface DiscoveryResponse {
  ai_available: boolean
  model: string | null
  notice: string
  candidates: Scholarship[]
  introduction: string | null
  assessments: ScholarshipAssessment[]
  /** CONVERSATION turns carry a reply only: no candidates, no assessments. */
  mode: 'CONVERSATION' | 'ASSESSMENT'
  intent: ChatIntent | null
  requested_details: ChatDetailKey[]
  suggested_replies: string[]
  extracted: ChatExtractedFacts | null
}

export interface ScholarshipQuestionResponse {
  ai_available: boolean
  model: string | null
  label:
    | 'SUPPORTED_BY_PROVIDER_SOURCE'
    | 'MORE_INFORMATION_NEEDED'
    | 'PROVIDER_CONFIRMATION_REQUIRED'
  answer: string
  citations: Evidence[]
  suggested_questions: string[]
}

export interface ApplicationListItem {
  id: string
  status: string
  scholarship_title: string
  organization_name: string
  updated_at: string
}

export interface ApplicationDetail {
  id: string
  status: string
  scholarship_id: string
  scholarship_title: string
  organization_name: string
  consent_recorded_at: string | null
  submitted_at: string | null
  fields: ApplicationField[]
  answered_field_ids: string[]
  events: Array<{
    event_type: string
    safe_message: string
    created_at: string
  }>
}

export interface ScholarshipQuery {
  q: string
  state_code: string
  organization_type: OrganizationType | ''
  education_level: string
  course: string
  offset: number
}
