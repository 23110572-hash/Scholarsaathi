import { Link } from 'react-router-dom'
import type { Scholarship, ScholarshipAssessment } from '../types'
import { ArrowIcon, BookmarkIcon } from './Icons'

interface ScholarshipCardProps {
  scholarship: Scholarship
  assessment?: ScholarshipAssessment | undefined
  onSave?: ((scholarshipId: string) => void) | undefined
}

const providerLabels: Record<string, string> = {
  CENTRAL_GOVERNMENT: 'Central Government',
  STATE_GOVERNMENT: 'State Government',
  PRIVATE_COMPANY: 'Private Company',
  NGO: 'NGO',
}

const assessmentLabels: Record<string, string> = {
  LIKELY_ELIGIBLE: 'Likely match',
  POSSIBLY_ELIGIBLE_NEEDS_INFORMATION: 'More information needed',
  LIKELY_NOT_ELIGIBLE: 'Likely not a match',
  CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION: 'Provider confirmation required',
}

function formatToken(value: string): string {
  return value
    .replaceAll('_', ' ')
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatDeadline(value: string | null): { date: string; urgency: string; urgent: boolean } {
  if (!value) return { date: 'Not published', urgency: 'Check provider details', urgent: false }
  const deadline = new Date(value)
  const days = Math.ceil((deadline.getTime() - Date.now()) / 86_400_000)
  const date = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(deadline)
  if (days < 0) return { date, urgency: 'Deadline passed', urgent: true }
  if (days === 0) return { date, urgency: 'Closes today', urgent: true }
  if (days <= 21) return { date, urgency: `${days} days left`, urgent: true }
  return { date, urgency: `Closes ${date}`, urgent: false }
}

function formatCoverage(scholarship: Scholarship): string {
  if (scholarship.applicable_state_codes.includes('ALL')) return 'All India'
  return scholarship.applicable_state_codes.join(', ')
}

export function ScholarshipCard({ scholarship, assessment, onSave }: ScholarshipCardProps) {
  const deadline = formatDeadline(scholarship.application_deadline_at)
  const education = scholarship.education_levels.slice(0, 2).map(formatToken).join(' · ')

  return (
    <article className="modern-card">
      <div className="modern-card-header">
        <span className="modern-provider-pill">
          {providerLabels[scholarship.organization.organization_type] ?? 'Provider'}
        </span>
      </div>

      <div className="modern-card-body">
        <div className="modern-card-provider">
          <span className="modern-provider-avatar" aria-hidden="true">{scholarship.organization.display_name.charAt(0)}</span>
          <span>{scholarship.organization.display_name}</span>
        </div>

        <Link className="modern-card-title" to={`/scholarships/${scholarship.id}`}>
          <h3>{scholarship.title}</h3>
        </Link>
        <p className="modern-card-summary">{scholarship.summary}</p>

        {assessment && (
          <div className={`assessment assessment-${assessment.assessment.toLowerCase()} mb-4`}>
            <div>
              <strong>{assessmentLabels[assessment.assessment]}</strong>
            </div>
            <p>{assessment.summary}</p>
          </div>
        )}

        <div className="modern-tag-row" aria-label="Scholarship categories">
          <span className="modern-tag" title="Coverage">{formatCoverage(scholarship)}</span>
          <span className="modern-tag" title="Education">{education || 'See eligibility'}</span>
          <span className="modern-tag" title="Academic Year">{scholarship.academic_year}</span>
          {scholarship.category_tags.slice(0, 2).map((tag) => (
            <span className="modern-tag" key={tag}>{formatToken(tag)}</span>
          ))}
        </div>
      </div>

      <div className="modern-card-footer">
        <div className="modern-deadline">
          <span className="modern-deadline-label">Application deadline</span>
          <strong className={deadline.urgent ? 'modern-deadline-value urgent' : 'modern-deadline-value'}>{deadline.urgency}</strong>
          <small className="text-xs text-slate-500 mt-1">{deadline.date}</small>
        </div>

        <div className="flex flex-col gap-2 items-end">
          <Link className="modern-action-link" to={`/scholarships/${scholarship.id}`}>
            View full details <ArrowIcon />
          </Link>
          {onSave && (
            <button
              className="text-xs font-semibold text-slate-500 hover:text-orange-500 transition-colors flex items-center gap-1"
              type="button"
              aria-label={`Save ${scholarship.title}`}
              onClick={() => onSave(scholarship.id)}
            >
              <BookmarkIcon /> Save
            </button>
          )}
        </div>
      </div>
    </article>
  )
}
