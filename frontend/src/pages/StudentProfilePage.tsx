import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowIcon, CloseIcon, UserIcon } from '../components/Icons'
import { useAuth } from '../context/AuthContext'
import { api } from '../lib/api'
import { ACCEPTED_PHOTO_TYPES, ImageProcessingError, toSquareAvatarDataUrl } from '../lib/image'
import type { StateOption, StudentProfile, StudentProfileInput } from '../types'

const EDUCATION_LEVELS = [
  'DIPLOMA',
  'UNDERGRADUATE',
  'POSTGRADUATE',
  'DOCTORAL',
  'CLASS_11_12',
] as const

const COURSES = [
  'BTECH',
  'BE',
  'BARCH',
  'TECHNICAL_DIPLOMA',
  'STEM',
  'BSC',
  'BCOM',
  'BA',
  'MBBS',
  'OTHER',
] as const

const INCOME_RANGES = [
  { value: 'UP_TO_250000', label: 'Up to ₹2.5 lakh' },
  { value: '250001_TO_400000', label: '₹2.5–4 lakh' },
  { value: '400001_TO_600000', label: '₹4–6 lakh' },
  { value: '600001_TO_800000', label: '₹6–8 lakh' },
  { value: 'ABOVE_800000', label: 'Above ₹8 lakh' },
] as const

const CATEGORY_OPTIONS = [
  'FIRST_GENERATION',
  'WOMEN',
  'SC',
  'ST',
  'OBC',
  'EWS',
  'MINORITY',
  'DISABILITY',
  'RURAL',
  'ORPHAN',
] as const

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'हिन्दी (Hindi)' },
  { value: 'or', label: 'ଓଡ଼ିଆ (Odia)' },
  { value: 'bn', label: 'বাংলা (Bengali)' },
  { value: 'ta', label: 'தமிழ் (Tamil)' },
  { value: 'te', label: 'తెలుగు (Telugu)' },
  { value: 'mr', label: 'मराठी (Marathi)' },
] as const

/** Form state keeps numbers as strings so a cleared input stays empty instead of 0. */
interface ProfileForm {
  full_name: string
  display_alias: string
  state_code: string
  education_level: string
  course: string
  course_year: string
  marks_percentage: string
  family_income_range: string
  categories: string[]
  preferred_language: string
  photo_data_url: string | null
}

const emptyForm: ProfileForm = {
  full_name: '',
  display_alias: '',
  state_code: '',
  education_level: '',
  course: '',
  course_year: '',
  marks_percentage: '',
  family_income_range: '',
  categories: [],
  preferred_language: 'en',
  photo_data_url: null,
}

function formFromProfile(profile: StudentProfile): ProfileForm {
  return {
    full_name: profile.full_name ?? '',
    display_alias: profile.display_alias ?? '',
    state_code: profile.state_code ?? '',
    education_level: profile.education_level ?? '',
    course: profile.course ?? '',
    course_year: profile.course_year === null ? '' : String(profile.course_year),
    marks_percentage: profile.marks_percentage === null ? '' : String(profile.marks_percentage),
    family_income_range: profile.family_income_range ?? '',
    categories: profile.categories,
    preferred_language: profile.preferred_language || 'en',
    photo_data_url: profile.photo_data_url,
  }
}

function trimmedOrNull(value: string): string | null {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function numberOrNull(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

function payloadFromForm(form: ProfileForm): StudentProfileInput {
  return {
    full_name: trimmedOrNull(form.full_name),
    display_alias: trimmedOrNull(form.display_alias),
    state_code: trimmedOrNull(form.state_code),
    education_level: trimmedOrNull(form.education_level),
    course: trimmedOrNull(form.course),
    course_year: numberOrNull(form.course_year),
    marks_percentage: numberOrNull(form.marks_percentage),
    family_income_range: trimmedOrNull(form.family_income_range),
    categories: form.categories,
    preferred_language: form.preferred_language || 'en',
    photo_data_url: form.photo_data_url,
  }
}

function formatToken(value: string): string {
  return value
    .replaceAll('_', ' ')
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function StudentProfilePage() {
  const { user, refresh } = useAuth()
  const [form, setForm] = useState<ProfileForm>(emptyForm)
  const [states, setStates] = useState<StateOption[]>([])
  const [completeness, setCompleteness] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const photoInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [profile, stateOptions] = await Promise.all([
          api<StudentProfile>('/api/student/profile'),
          api<StateOption[]>('/api/states'),
        ])
        if (cancelled) return
        setForm(formFromProfile(profile))
        setCompleteness(profile.completeness)
        setStates(stateOptions)
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : 'Your profile could not be loaded.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  const update = useCallback(<K extends keyof ProfileForm>(key: K, value: ProfileForm[K]) => {
    setForm((current) => ({ ...current, [key]: value }))
    setNotice('')
  }, [])

  function toggleCategory(category: string) {
    setNotice('')
    setForm((current) => ({
      ...current,
      categories: current.categories.includes(category)
        ? current.categories.filter((value) => value !== category)
        : [...current.categories, category],
    }))
  }

  async function handlePhotoChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    // Reset immediately so choosing the same file again still fires a change event.
    event.target.value = ''
    if (!file) return
    setError('')
    setNotice('')
    try {
      update('photo_data_url', await toSquareAvatarDataUrl(file))
    } catch (caught) {
      setError(
        caught instanceof ImageProcessingError
          ? caught.message
          : 'That image could not be processed.',
      )
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setNotice('')

    const marks = numberOrNull(form.marks_percentage)
    if (marks !== null && (marks < 0 || marks > 100)) {
      setError('Marks percentage must be between 0 and 100.')
      return
    }
    const year = numberOrNull(form.course_year)
    if (year !== null && (year < 1 || year > 12)) {
      setError('Current year must be between 1 and 12.')
      return
    }

    setSaving(true)
    try {
      const saved = await api<StudentProfile>('/api/student/profile', {
        method: 'PUT',
        body: JSON.stringify(payloadFromForm(form)),
      })
      setForm(formFromProfile(saved))
      setCompleteness(saved.completeness)
      setNotice('Your profile has been saved.')
      // The header greeting and assistant language come from the session user.
      await refresh()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Your profile could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <main className="screen-center">
        <div className="loader" role="status" aria-label="Loading your profile" />
      </main>
    )
  }

  const initial = (form.full_name || form.display_alias || user?.login_identifier || '?')
    .trim()
    .charAt(0)
    .toUpperCase()

  return (
    <main className="modern-workspace-page">
      <div className="modern-workspace-overlay"></div>
      <div className="modern-workspace-content">
        <section className="modern-workspace-intro section-pad">
          <div>
            <p className="modern-section-kicker">Student profile</p>
            <h1>Your details</h1>
            <p>
              Saved here once, then reused for every scholarship search and eligibility check.
            </p>
          </div>
          <Link className="modern-profile-back" to="/student">
            Back to workspace <ArrowIcon />
          </Link>
        </section>

        <section className="modern-profile-shell section-pad">
          <form className="modern-glass-card modern-large-form" onSubmit={(event) => void handleSubmit(event)}>
            <div className="modern-profile-identity">
              <div className="modern-profile-photo">
                {form.photo_data_url ? (
                  <img src={form.photo_data_url} alt="Your profile photo" />
                ) : (
                  <span className="modern-profile-initial" aria-hidden="true">{initial}</span>
                )}
              </div>
              <div className="modern-profile-photo-actions">
                <strong>Profile photo</strong>
                <p>A square PNG, JPEG, or WebP. It is resized in your browser before saving.</p>
                <div className="modern-profile-photo-buttons">
                  <button
                    className="modern-button-secondary"
                    type="button"
                    onClick={() => photoInputRef.current?.click()}
                  >
                    {form.photo_data_url ? 'Change photo' : 'Upload photo'}
                  </button>
                  {form.photo_data_url && (
                    <button
                      className="modern-button-ghost"
                      type="button"
                      onClick={() => update('photo_data_url', null)}
                    >
                      <CloseIcon /> Remove
                    </button>
                  )}
                </div>
                <input
                  ref={photoInputRef}
                  className="sr-only"
                  type="file"
                  accept={ACCEPTED_PHOTO_TYPES.join(',')}
                  onChange={(event) => void handlePhotoChange(event)}
                  aria-label="Upload a profile photo"
                />
              </div>
            </div>

            <div className="modern-profile-progress" aria-live="polite">
              <div className="modern-profile-progress-bar">
                <div className="modern-profile-progress-fill" style={{ width: `${completeness}%` }} />
              </div>
              <small>{completeness}% complete</small>
            </div>

            <h2 className="modern-profile-legend">About you</h2>
            <div className="form-grid compact-grid">
              <label>
                Full name
                <input
                  value={form.full_name}
                  maxLength={120}
                  autoComplete="name"
                  placeholder="As printed on your academic records"
                  onChange={(event) => update('full_name', event.target.value)}
                />
              </label>
              <label>
                Display name
                <input
                  value={form.display_alias}
                  maxLength={80}
                  placeholder="Shown in the app"
                  onChange={(event) => update('display_alias', event.target.value)}
                />
              </label>
              <label>
                State / UT
                <select
                  value={form.state_code}
                  onChange={(event) => update('state_code', event.target.value)}
                >
                  <option value="">Select your State or UT</option>
                  {states.map((state) => (
                    <option key={state.code} value={state.code}>
                      {state.name}{state.is_union_territory ? ' (UT)' : ''}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Preferred language
                <select
                  value={form.preferred_language}
                  onChange={(event) => update('preferred_language', event.target.value)}
                >
                  {LANGUAGES.map((language) => (
                    <option key={language.value} value={language.value}>{language.label}</option>
                  ))}
                </select>
              </label>
            </div>

            <h2 className="modern-profile-legend">Your studies</h2>
            <div className="form-grid compact-grid">
              <label>
                Education level
                <select
                  value={form.education_level}
                  onChange={(event) => update('education_level', event.target.value)}
                >
                  <option value="">Select a level</option>
                  {EDUCATION_LEVELS.map((level) => (
                    <option key={level} value={level}>{formatToken(level)}</option>
                  ))}
                </select>
              </label>
              <label>
                Course
                <select value={form.course} onChange={(event) => update('course', event.target.value)}>
                  <option value="">Select a course</option>
                  {COURSES.map((course) => (
                    <option key={course} value={course}>{formatToken(course)}</option>
                  ))}
                </select>
              </label>
              <label>
                Current year
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={form.course_year}
                  placeholder="e.g. 2"
                  onChange={(event) => update('course_year', event.target.value)}
                />
              </label>
              <label>
                Marks percentage
                <input
                  type="number"
                  min={0}
                  max={100}
                  step="0.01"
                  value={form.marks_percentage}
                  placeholder="e.g. 78.5"
                  onChange={(event) => update('marks_percentage', event.target.value)}
                />
              </label>
              <label>
                Annual family income
                <select
                  value={form.family_income_range}
                  onChange={(event) => update('family_income_range', event.target.value)}
                >
                  <option value="">Select a range</option>
                  {INCOME_RANGES.map((range) => (
                    <option key={range.value} value={range.value}>{range.label}</option>
                  ))}
                </select>
              </label>
            </div>

            <fieldset className="modern-profile-categories">
              <legend>Categories that apply to you</legend>
              <p className="modern-profile-hint">
                Used only to match you against published eligibility rules.
              </p>
              <div className="modern-chip-grid">
                {CATEGORY_OPTIONS.map((category) => {
                  const checked = form.categories.includes(category)
                  return (
                    <label className={checked ? 'modern-chip modern-chip-on' : 'modern-chip'} key={category}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleCategory(category)}
                      />
                      {formatToken(category)}
                    </label>
                  )
                })}
              </div>
            </fieldset>

            {notice && <div className="success-banner" role="status">{notice}</div>}
            {error && <div className="error-banner" role="alert">{error}</div>}

            <button className="modern-button-primary button-full" type="submit" disabled={saving}>
              <UserIcon /> {saving ? 'Saving your profile…' : 'Save profile'}
            </button>
            <p className="modern-sensitive-warning">
              Do not enter Aadhaar, PAN, bank details, passwords, or OTPs. Providers verify documents
              separately during their own application process.
            </p>
          </form>
        </section>
      </div>
    </main>
  )
}
