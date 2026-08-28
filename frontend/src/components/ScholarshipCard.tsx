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
    <article className="scholarship-card">
      <div className="card-topline">
        <span className="provider-pill">
          {providerLabels[scholarship.organization.organization_type] ?? 'Provider'}
        </span>
      </div>

      <div className="card-provider-row">
        <span className="provider-monogram" aria-hidden="true">{scholarship.organization.display_name.charAt(0)}</span>
        <div>
          <p className="card-provider">{scholarship.organization.display_name}</p>
        </div>
      </div>

      <div className="card-copy">
        <Link className="card-title-link" to={`/scholarships/${scholarship.id}`}>
          <h3>{scholarship.title}</h3>
        </Link>
        <p className="card-summary">{scholarship.summary}</p>
      </div>

      {assessment && (
        <div className={`assessment assessment-${assessment.assessment.toLowerCase()}`}>
          <div>
            <strong>{assessmentLabels[assessment.assessment]}</strong>
          </div>
          <p>{assessment.summary}</p>
        </div>
      )}

      <div className="card-meta-row" aria-label="Scholarship coverage and audience">
        <span>{formatCoverage(scholarship)}</span>
        <span>{education || 'See eligibility'}</span>
        <span>{scholarship.academic_year}</span>
      </div>

      <div className="tag-row" aria-label="Scholarship categories">
        {scholarship.category_tags.slice(0, 3).map((tag) => (
          <span key={tag}>{formatToken(tag)}</span>
        ))}
      </div>

      <dl className="card-facts">
        <div>
          <dt>Support</dt>
          <dd>{scholarship.benefit_summary}</dd>
        </div>
      </dl>

      <div className={deadline.urgent ? 'card-deadline urgent' : 'card-deadline'}>
        <span>Application deadline</span>
        <strong>{deadline.urgency}</strong>
        <small>{deadline.date}</small>
      </div>

      <div className="card-actions">
        <Link className="inline-link" to={`/scholarships/${scholarship.id}`}>
          View full details <ArrowIcon />
        </Link>
        {onSave && (
          <button
            className="card-save-button"
            type="button"
            aria-label={`Save ${scholarship.title}`}
            onClick={() => onSave(scholarship.id)}
          >
            <BookmarkIcon /> <span>Save</span>
          </button>
        )}
      </div>
    </article>
  )
}
