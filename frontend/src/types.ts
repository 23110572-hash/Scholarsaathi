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

export interface DiscoveryResponse {
  ai_available: boolean
  model: string | null
  notice: string
  candidates: Scholarship[]
  introduction: string | null
  assessments: ScholarshipAssessment[]
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
