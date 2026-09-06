import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Download, FileCheck2, FileText, ShieldCheck, Trash2, Upload } from 'lucide-react'
import { ArrowIcon, CloseIcon, UserIcon } from '../components/Icons'
import { useAuth } from '../context/AuthContext'
import { api } from '../lib/api'
import { ACCEPTED_PHOTO_TYPES, ImageProcessingError, toSquareAvatarDataUrl } from '../lib/image'
import type {
  StateOption,
  StudentDocument,
  StudentDocumentDownloadResponse,
  StudentDocumentListResponse,
  StudentDocumentType,
  StudentProfile,
  StudentProfileInput,
} from '../types'

const EDUCATION_LEVELS = ['DIPLOMA', 'UNDERGRADUATE', 'POSTGRADUATE', 'DOCTORAL', 'CLASS_11_12'] as const
const COURSES = ['BTECH', 'BE', 'BARCH', 'TECHNICAL_DIPLOMA', 'STEM', 'BSC', 'BCOM', 'BA', 'MBBS', 'OTHER'] as const
const INCOME_RANGES = [
  { value: 'UP_TO_250000', label: 'Up to ₹2.5 lakh' },
  { value: '250001_TO_400000', label: '₹2.5–4 lakh' },
  { value: '400001_TO_600000', label: '₹4–6 lakh' },
  { value: '600001_TO_800000', label: '₹6–8 lakh' },
  { value: 'ABOVE_800000', label: 'Above ₹8 lakh' },
] as const
const CATEGORY_OPTIONS = ['FIRST_GENERATION', 'WOMEN', 'SC', 'ST', 'OBC', 'EWS', 'MINORITY', 'DISABILITY', 'RURAL', 'ORPHAN'] as const
const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'हिन्दी (Hindi)' },
  { value: 'or', label: 'ଓଡ଼ିଆ (Odia)' },
  { value: 'bn', label: 'বাংলা (Bengali)' },
  { value: 'ta', label: 'தமிழ் (Tamil)' },
  { value: 'te', label: 'తెలుగు (Telugu)' },
  { value: 'mr', label: 'मराठी (Marathi)' },
] as const
const GENDERS = [
  { value: 'FEMALE', label: 'Female' },
  { value: 'MALE', label: 'Male' },
  { value: 'NON_BINARY', label: 'Non-binary' },
  { value: 'PREFER_NOT_TO_SAY', label: 'Prefer not to say' },
] as const
const DOCUMENT_TYPES: Array<{ value: StudentDocumentType; label: string; hint: string }> = [
  { value: 'CLASS_10_MARKSHEET', label: 'Class 10 marksheet', hint: 'Board-issued marksheet' },
  { value: 'CLASS_12_MARKSHEET', label: 'Class 12 marksheet', hint: 'Board-issued marksheet' },
  { value: 'CURRENT_MARKSHEET', label: 'Current marksheet', hint: 'Latest semester or academic result' },
  { value: 'INCOME_CERTIFICATE', label: 'Income certificate', hint: 'Current government-issued certificate' },
  { value: 'CATEGORY_CERTIFICATE', label: 'Category certificate', hint: 'SC, ST, OBC or EWS certificate' },
  { value: 'DOMICILE_CERTIFICATE', label: 'Domicile certificate', hint: 'State or UT domicile proof' },
  { value: 'DISABILITY_CERTIFICATE', label: 'Disability certificate', hint: 'Upload only when applicable' },
]

interface ProfileForm {
  full_name: string
  display_alias: string
  date_of_birth: string
  gender: string
  state_code: string
  district: string
  institution_name: string
  board_or_university: string
  education_level: string
  course: string
  specialization: string
  course_year: string
  current_semester: string
  marks_percentage: string
  class_10_percentage: string
  class_10_passing_year: string
  class_12_percentage: string
  class_12_passing_year: string
  family_income_range: string
  categories: string[]
  preferred_language: string
  photo_data_url: string | null
}

const emptyForm: ProfileForm = {
  full_name: '', display_alias: '', date_of_birth: '', gender: '', state_code: '', district: '',
  institution_name: '', board_or_university: '', education_level: '', course: '', specialization: '',
  course_year: '', current_semester: '', marks_percentage: '', class_10_percentage: '',
  class_10_passing_year: '', class_12_percentage: '', class_12_passing_year: '',
  family_income_range: '', categories: [], preferred_language: 'en', photo_data_url: null,
}

function formFromProfile(profile: StudentProfile): ProfileForm {
  return {
    full_name: profile.full_name ?? '',
    display_alias: profile.display_alias ?? '',
    date_of_birth: profile.date_of_birth ?? '',
    gender: profile.gender ?? '',
    state_code: profile.state_code ?? '',
    district: profile.district ?? '',
    institution_name: profile.institution_name ?? '',
    board_or_university: profile.board_or_university ?? '',
    education_level: profile.education_level ?? '',
    course: profile.course ?? '',
    specialization: profile.specialization ?? '',
    course_year: profile.course_year === null ? '' : String(profile.course_year),
    current_semester: profile.current_semester === null ? '' : String(profile.current_semester),
    marks_percentage: profile.marks_percentage === null ? '' : String(profile.marks_percentage),
    class_10_percentage: profile.class_10_percentage === null ? '' : String(profile.class_10_percentage),
    class_10_passing_year: profile.class_10_passing_year === null ? '' : String(profile.class_10_passing_year),
    class_12_percentage: profile.class_12_percentage === null ? '' : String(profile.class_12_percentage),
    class_12_passing_year: profile.class_12_passing_year === null ? '' : String(profile.class_12_passing_year),
    family_income_range: profile.family_income_range ?? '',
    categories: profile.categories,
    preferred_language: profile.preferred_language || 'en',
    photo_data_url: profile.photo_data_url,
  }
}

function trimmedOrNull(value: string): string | null {
  const trimmed = value.trim()
  return trimmed || null
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
    date_of_birth: trimmedOrNull(form.date_of_birth),
    gender: trimmedOrNull(form.gender),
    state_code: trimmedOrNull(form.state_code),
    district: trimmedOrNull(form.district),
    institution_name: trimmedOrNull(form.institution_name),
    board_or_university: trimmedOrNull(form.board_or_university),
    education_level: trimmedOrNull(form.education_level),
    course: trimmedOrNull(form.course),
    specialization: trimmedOrNull(form.specialization),
    course_year: numberOrNull(form.course_year),
    current_semester: numberOrNull(form.current_semester),
    marks_percentage: numberOrNull(form.marks_percentage),
    class_10_percentage: numberOrNull(form.class_10_percentage),
    class_10_passing_year: numberOrNull(form.class_10_passing_year),
    class_12_percentage: numberOrNull(form.class_12_percentage),
    class_12_passing_year: numberOrNull(form.class_12_passing_year),
    family_income_range: trimmedOrNull(form.family_income_range),
    categories: form.categories,
    preferred_language: form.preferred_language || 'en',
    photo_data_url: form.photo_data_url,
  }
}

function formatToken(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatBytes(size: number): string {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function StudentProfilePage() {
  const { user, refresh } = useAuth()
  const [form, setForm] = useState<ProfileForm>(emptyForm)
  const [states, setStates] = useState<StateOption[]>([])
  const [documents, setDocuments] = useState<StudentDocument[]>([])
  const [completeness, setCompleteness] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [selectedDocumentType, setSelectedDocumentType] = useState<StudentDocumentType>('INCOME_CERTIFICATE')
  const [documentFile, setDocumentFile] = useState<File | null>(null)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const photoInputRef = useRef<HTMLInputElement>(null)
  const documentInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [profile, stateOptions, documentResult] = await Promise.all([
          api<StudentProfile>('/api/student/profile'),
          api<StateOption[]>('/api/states'),
          api<StudentDocumentListResponse>('/api/student/documents'),
        ])
        if (cancelled) return
        setForm(formFromProfile(profile))
        setCompleteness(profile.completeness)
        setStates(stateOptions)
        setDocuments(documentResult.items)
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : 'Your profile could not be loaded.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
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
    event.target.value = ''
    if (!file) return
    setError('')
    try {
      update('photo_data_url', await toSquareAvatarDataUrl(file))
    } catch (caught) {
      setError(caught instanceof ImageProcessingError ? caught.message : 'That image could not be processed.')
    }
  }

  function validateAcademicValues(): string | null {
    const percentages = [form.marks_percentage, form.class_10_percentage, form.class_12_percentage]
    if (percentages.some((value) => {
      const parsed = numberOrNull(value)
      return parsed !== null && (parsed < 0 || parsed > 100)
    })) return 'Every percentage must be between 0 and 100.'
    const year = numberOrNull(form.course_year)
    if (year !== null && (year < 1 || year > 12)) return 'Current year must be between 1 and 12.'
    const semester = numberOrNull(form.current_semester)
    if (semester !== null && (semester < 1 || semester > 20)) return 'Semester must be between 1 and 20.'
    return null
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setNotice('')
    const validationError = validateAcademicValues()
    if (validationError) { setError(validationError); return }
    setSaving(true)
    try {
      const saved = await api<StudentProfile>('/api/student/profile', {
        method: 'PUT', body: JSON.stringify(payloadFromForm(form)),
      })
      setForm(formFromProfile(saved))
      setCompleteness(saved.completeness)
      setNotice('Profile saved. Any pending scholarship applications were checked automatically.')
      await refresh()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Your profile could not be saved.')
    } finally { setSaving(false) }
  }

  function handleDocumentFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null
    setError('')
    setNotice('')
    if (file && file.size > 10 * 1024 * 1024) {
      event.target.value = ''
      setDocumentFile(null)
      setError('Documents must be 10 MB or smaller.')
      return
    }
    setDocumentFile(file)
  }

  async function uploadDocument(event: FormEvent) {
    event.preventDefault()
    if (!documentFile) { setError('Choose a PDF, PNG or JPEG document first.'); return }
    setUploading(true)
    setError('')
    setNotice('')
    const body = new FormData()
    body.append('document_type', selectedDocumentType)
    body.append('file', documentFile)
    try {
      const uploaded = await api<StudentDocument>('/api/student/documents', { method: 'POST', body })
      setDocuments((current) => [uploaded, ...current])
      setDocumentFile(null)
      if (documentInputRef.current) documentInputRef.current.value = ''
      setNotice('Document stored privately. Pending applications were checked automatically.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The document could not be uploaded.')
    } finally { setUploading(false) }
  }

  async function downloadDocument(document: StudentDocument) {
    setError('')
    try {
      const result = await api<StudentDocumentDownloadResponse>(`/api/student/documents/${document.id}/download`)
      window.open(result.url, '_blank', 'noopener,noreferrer')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The private download could not be opened.')
    }
  }

  async function deleteDocument(document: StudentDocument) {
    if (!window.confirm(`Remove ${document.original_filename}?`)) return
    setError('')
    try {
      await api<{ message: string }>(`/api/student/documents/${document.id}`, { method: 'DELETE' })
      setDocuments((current) => current.filter((item) => item.id !== document.id))
      setNotice('Document removed.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The document could not be removed.')
    }
  }

  if (loading) return <main className="screen-center"><div className="loader" role="status" aria-label="Loading your profile" /></main>

  const initial = (form.full_name || form.display_alias || user?.login_identifier || '?').trim().charAt(0).toUpperCase()
  const currentYear = new Date().getFullYear()

  return (
    <main className="modern-workspace-page">
      <div className="modern-workspace-overlay" />
      <div className="modern-workspace-content">
        <section className="modern-workspace-intro section-pad">
          <div>
            <p className="modern-section-kicker">Student profile</p>
            <h1>Your scholarship profile</h1>
            <p>Complete it once. ScholarSaathi securely reuses these details when you ask it to apply.</p>
          </div>
          <Link className="modern-profile-back" to="/student">Back to workspace <ArrowIcon /></Link>
        </section>

        <section className="modern-profile-shell section-pad">
          <form className="modern-glass-card modern-large-form" onSubmit={(event) => void handleSubmit(event)}>
            <div className="modern-profile-identity">
              <div className="modern-profile-photo">
                {form.photo_data_url ? <img src={form.photo_data_url} alt="Your profile" /> : <span className="modern-profile-initial" aria-hidden="true">{initial}</span>}
              </div>
              <div className="modern-profile-photo-actions">
                <strong>Profile photo</strong>
                <p>A square PNG, JPEG or WebP, resized before it leaves your browser.</p>
                <div className="modern-profile-photo-buttons">
                  <button className="modern-button-secondary" type="button" onClick={() => photoInputRef.current?.click()}>{form.photo_data_url ? 'Change photo' : 'Upload photo'}</button>
                  {form.photo_data_url && <button className="modern-button-ghost" type="button" onClick={() => update('photo_data_url', null)}><CloseIcon /> Remove</button>}
                </div>
                <input ref={photoInputRef} className="sr-only" type="file" accept={ACCEPTED_PHOTO_TYPES.join(',')} onChange={(event) => void handlePhotoChange(event)} />
              </div>
            </div>

            <div className="modern-profile-progress" aria-live="polite">
              <div className="modern-profile-progress-bar"><div className="modern-profile-progress-fill" style={{ width: `${completeness}%` }} /></div>
              <small>{completeness}% complete</small>
            </div>

            <h2 className="modern-profile-legend">Personal details</h2>
            <div className="form-grid compact-grid">
              <label>Full name<input value={form.full_name} maxLength={120} autoComplete="name" placeholder="As printed on academic records" onChange={(event) => update('full_name', event.target.value)} /></label>
              <label>Display name<input value={form.display_alias} maxLength={80} placeholder="Shown inside ScholarSaathi" onChange={(event) => update('display_alias', event.target.value)} /></label>
              <label>Date of birth<input type="date" value={form.date_of_birth} max={new Date().toISOString().slice(0, 10)} onChange={(event) => update('date_of_birth', event.target.value)} /></label>
              <label>Gender<select value={form.gender} onChange={(event) => update('gender', event.target.value)}><option value="">Select</option>{GENDERS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
              <label>State / UT<select value={form.state_code} onChange={(event) => update('state_code', event.target.value)}><option value="">Select State or UT</option>{states.map((state) => <option key={state.code} value={state.code}>{state.name}{state.is_union_territory ? ' (UT)' : ''}</option>)}</select></label>
              <label>District<input value={form.district} maxLength={120} placeholder="Your district" onChange={(event) => update('district', event.target.value)} /></label>
              <label>Preferred language<select value={form.preferred_language} onChange={(event) => update('preferred_language', event.target.value)}>{LANGUAGES.map((language) => <option key={language.value} value={language.value}>{language.label}</option>)}</select></label>
            </div>

            <h2 className="modern-profile-legend">Current studies</h2>
            <div className="form-grid compact-grid">
              <label>Institution<input value={form.institution_name} maxLength={240} placeholder="College, school or university" onChange={(event) => update('institution_name', event.target.value)} /></label>
              <label>Board or university<input value={form.board_or_university} maxLength={240} placeholder="Affiliating board or university" onChange={(event) => update('board_or_university', event.target.value)} /></label>
              <label>Education level<select value={form.education_level} onChange={(event) => update('education_level', event.target.value)}><option value="">Select level</option>{EDUCATION_LEVELS.map((level) => <option key={level} value={level}>{formatToken(level)}</option>)}</select></label>
              <label>Course<select value={form.course} onChange={(event) => update('course', event.target.value)}><option value="">Select course</option>{COURSES.map((course) => <option key={course} value={course}>{formatToken(course)}</option>)}</select></label>
              <label>Specialization<input value={form.specialization} maxLength={120} placeholder="e.g. Computer Science" onChange={(event) => update('specialization', event.target.value)} /></label>
              <label>Current year<input type="number" min={1} max={12} value={form.course_year} placeholder="e.g. 2" onChange={(event) => update('course_year', event.target.value)} /></label>
              <label>Current semester<input type="number" min={1} max={20} value={form.current_semester} placeholder="e.g. 4" onChange={(event) => update('current_semester', event.target.value)} /></label>
              <label>Current percentage<input type="number" min={0} max={100} step="0.01" value={form.marks_percentage} placeholder="e.g. 78.5" onChange={(event) => update('marks_percentage', event.target.value)} /></label>
            </div>

            <h2 className="modern-profile-legend">Academic history</h2>
            <div className="form-grid compact-grid">
              <label>Class 10 percentage<input type="number" min={0} max={100} step="0.01" value={form.class_10_percentage} placeholder="e.g. 86.4" onChange={(event) => update('class_10_percentage', event.target.value)} /></label>
              <label>Class 10 passing year<input type="number" min={1950} max={currentYear + 1} value={form.class_10_passing_year} placeholder={String(currentYear - 5)} onChange={(event) => update('class_10_passing_year', event.target.value)} /></label>
              <label>Class 12 percentage<input type="number" min={0} max={100} step="0.01" value={form.class_12_percentage} placeholder="e.g. 81.2" onChange={(event) => update('class_12_percentage', event.target.value)} /></label>
              <label>Class 12 passing year<input type="number" min={1950} max={currentYear + 1} value={form.class_12_passing_year} placeholder={String(currentYear - 3)} onChange={(event) => update('class_12_passing_year', event.target.value)} /></label>
              <label>Annual family income<select value={form.family_income_range} onChange={(event) => update('family_income_range', event.target.value)}><option value="">Select range</option>{INCOME_RANGES.map((range) => <option key={range.value} value={range.value}>{range.label}</option>)}</select></label>
            </div>

            <fieldset className="modern-profile-categories">
              <legend>Categories that apply to you</legend>
              <p className="modern-profile-hint">Used only to check the eligibility rules published by providers.</p>
              <div className="modern-chip-grid">{CATEGORY_OPTIONS.map((category) => { const checked = form.categories.includes(category); return <label className={checked ? 'modern-chip modern-chip-on' : 'modern-chip'} key={category}><input type="checkbox" checked={checked} onChange={() => toggleCategory(category)} />{formatToken(category)}</label> })}</div>
            </fieldset>

            <button className="modern-button-primary button-full" type="submit" disabled={saving}><UserIcon /> {saving ? 'Saving profile…' : 'Save profile'}</button>
          </form>

          <section className="modern-glass-card student-documents-card" id="documents" aria-labelledby="documents-title">
            <div className="student-documents-heading">
              <span aria-hidden="true"><ShieldCheck size={22} /></span>
              <div>
                <p className="modern-section-kicker">Private document vault</p>
                <h2 id="documents-title">Application documents</h2>
                <p>Encrypted private storage. ScholarSaathi attaches only the documents required for a selected scholarship.</p>
              </div>
            </div>

            <form className="document-upload-form" onSubmit={(event) => void uploadDocument(event)}>
              <div className="document-upload-fields">
                <label>Document type
                  <select value={selectedDocumentType} onChange={(event) => setSelectedDocumentType(event.target.value as StudentDocumentType)}>
                    {DOCUMENT_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                  </select>
                  <small className="document-field-hint">{DOCUMENT_TYPES.find((item) => item.value === selectedDocumentType)?.hint}</small>
                </label>
                <label className="document-file-field">Document file
                  <span className={`document-file-picker${documentFile ? ' has-file' : ''}`}>
                    {documentFile ? <FileCheck2 size={22} /> : <Upload size={22} />}
                    <span className="document-file-copy">
                      <strong>{documentFile?.name ?? 'Choose a file to upload'}</strong>
                      <small>{documentFile ? formatBytes(documentFile.size) : 'PDF, PNG or JPEG · Maximum 10 MB'}</small>
                    </span>
                  </span>
                  <input ref={documentInputRef} className="sr-only" type="file" accept="application/pdf,image/png,image/jpeg" onChange={handleDocumentFileChange} />
                </label>
              </div>
              <div className="document-upload-footer">
                <p><ShieldCheck size={17} /> Private by default and shared only with your selected scholarship application.</p>
                <button className="modern-button-primary" type="submit" disabled={uploading || !documentFile}><Upload size={17} /> {uploading ? 'Uploading privately…' : 'Upload document'}</button>
              </div>
            </form>

            <div className="student-document-list">
              {documents.length === 0 ? <div className="student-document-empty"><FileText size={28} /><strong>No documents uploaded yet</strong><p>Add the documents commonly required for your scholarships.</p></div> : documents.map((document) => <article className="student-document-row" key={document.id}><span className="student-document-icon"><FileText size={20} /></span><div><strong>{DOCUMENT_TYPES.find((item) => item.value === document.document_type)?.label ?? formatToken(document.document_type)}</strong><p>{document.original_filename} · {formatBytes(document.size_bytes)}</p></div><div className="student-document-actions"><button type="button" title="Download document" onClick={() => void downloadDocument(document)} aria-label={`Download ${document.original_filename}`}><Download size={17} /></button><button type="button" title="Delete document" onClick={() => void deleteDocument(document)} aria-label={`Delete ${document.original_filename}`}><Trash2 size={17} /></button></div></article>)}
            </div>
          </section>

          {notice && <div className="success-banner profile-global-banner" role="status">{notice}</div>}
          {error && <div className="error-banner profile-global-banner" role="alert">{error}</div>}
          <p className="modern-sensitive-warning"><ShieldCheck size={16} /> Never upload or enter Aadhaar, PAN, bank details, passwords or OTPs.</p>
        </section>
      </div>
    </main>
  )
}
