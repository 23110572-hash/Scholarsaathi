import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { SearchIcon } from '../components/Icons'
import { ScholarshipCard } from '../components/ScholarshipCard'
import { useAuth } from '../context/AuthContext'
import { api } from '../lib/api'
import type { OrganizationType, ScholarshipList, ScholarshipQuery } from '../types'

const PAGE_SIZE = 9

const organizationTypes: Array<{ value: OrganizationType | ''; label: string }> = [
  { value: '', label: 'All provider types' },
  { value: 'CENTRAL_GOVERNMENT', label: 'Central Government' },
  { value: 'STATE_GOVERNMENT', label: 'State Government' },
  { value: 'PRIVATE_COMPANY', label: 'Private companies' },
  { value: 'NGO', label: 'NGOs' },
]

const states = [
  ['', 'All India and all states'],
  ['OD', 'Odisha'], ['MH', 'Maharashtra'], ['KA', 'Karnataka'], ['WB', 'West Bengal'],
  ['DL', 'Delhi'], ['TN', 'Tamil Nadu'], ['UP', 'Uttar Pradesh'], ['RJ', 'Rajasthan'],
  ['GJ', 'Gujarat'], ['TG', 'Telangana'], ['KL', 'Kerala'], ['MP', 'Madhya Pradesh'], ['BR', 'Bihar'],
] as const

const educationLevels = [
  ['', 'All education levels'],
  ['DIPLOMA', 'Diploma'],
  ['UNDERGRADUATE', 'Undergraduate'],
  ['POSTGRADUATE', 'Postgraduate'],
] as const

const courseFamilies = [
  ['', 'All course families'],
  ['BTECH', 'B.Tech'], ['BE', 'B.E.'], ['BARCH', 'B.Arch'],
  ['TECHNICAL_DIPLOMA', 'Technical diploma'], ['STEM', 'STEM'],
  ['ALL_UNDERGRADUATE', 'Any undergraduate course'],
  ['ALL_RECOGNIZED_COURSES', 'Any recognized course'],
] as const

function readQuery(params: URLSearchParams): ScholarshipQuery {
  const organizationType = params.get('organization_type') ?? ''
  const allowedOrganization = organizationTypes.some((option) => option.value === organizationType)
  const rawOffset = Number(params.get('offset') ?? 0)
  return {
    q: params.get('q') ?? '',
    state_code: params.get('state_code') ?? '',
    organization_type: allowedOrganization ? organizationType as OrganizationType | '' : '',
    education_level: params.get('education_level') ?? '',
    course: params.get('course') ?? '',
    offset: Number.isFinite(rawOffset) && rawOffset > 0 ? rawOffset : 0,
  }
}

export function ScholarshipCatalogPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestKey = searchParams.toString()
  const query = useMemo(() => readQuery(new URLSearchParams(requestKey)), [requestKey])
  const [filters, setFilters] = useState<ScholarshipQuery>(query)
  const [catalog, setCatalog] = useState<ScholarshipList>({ items: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => { setFilters(query) }, [query])

  useEffect(() => {
    const controller = new AbortController()
    const params = new URLSearchParams(requestKey)
    params.set('limit', String(PAGE_SIZE))
    if (!params.has('offset')) params.set('offset', '0')
    setLoading(true)
    setError('')
    api<ScholarshipList>(`/api/scholarships?${params.toString()}`, { signal: controller.signal })
      .then(setCatalog)
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === 'AbortError') return
        setError(caught instanceof Error ? caught.message : 'The scholarship list is temporarily unavailable.')
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [requestKey, retry])

  function applyFilters(event: FormEvent) {
    event.preventDefault()
    const next = new URLSearchParams()
    const cleanQuery = filters.q.trim()
    if (cleanQuery) next.set('q', cleanQuery)
    if (filters.state_code) next.set('state_code', filters.state_code)
    if (filters.organization_type) next.set('organization_type', filters.organization_type)
    if (filters.education_level) next.set('education_level', filters.education_level)
    if (filters.course) next.set('course', filters.course)
    setNotice('')
    setSearchParams(next)
  }

  function clearFilters() {
    setNotice('')
    setSearchParams(new URLSearchParams())
  }

  function changePage(offset: number) {
    const next = new URLSearchParams(searchParams)
    if (offset > 0) next.set('offset', String(offset))
    else next.delete('offset')
    setSearchParams(next)
    window.requestAnimationFrame(() => document.querySelector('.catalog-results')?.scrollIntoView({ behavior: 'smooth' }))
  }

  async function saveScholarship(scholarshipId: string) {
    setNotice('')
    if (!user) {
      navigate('/login/student', { state: { from: `${location.pathname}${location.search}`, intent: 'save', scholarshipId } })
      return
    }
    if (user.realm !== 'STUDENT') {
      setNotice('Use a student account to save this scholarship.')
      return
    }
    try {
      await api(`/api/student/saved-scholarships/${scholarshipId}`, { method: 'POST' })
      setNotice('Scholarship saved.')
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : 'Could not save this scholarship.')
    }
  }

  const activeFilterCount = [query.q, query.state_code, query.organization_type, query.education_level, query.course].filter(Boolean).length
  const firstResult = catalog.total === 0 ? 0 : query.offset + 1
  const lastResult = Math.min(query.offset + catalog.items.length, catalog.total)
  const currentPage = Math.floor(query.offset / PAGE_SIZE) + 1
  const totalPages = Math.max(1, Math.ceil(catalog.total / PAGE_SIZE))

  return (
    <main className="modern-catalog-page">
      <header className="modern-catalog-hero">
        <div className="hero-background-glow"></div>
        <div className="modern-container">
          <p className="hero-subtitle">Scholarships</p>
          <h1 className="hero-title">Find your eligible scholarship</h1>
          <p className="hero-description">Use the search and filters below to narrow the list and find the perfect match for your future.</p>
        </div>
      </header>

      <section className="modern-search-section" aria-label="Search scholarships">
        <form className="modern-search-glass modern-container" onSubmit={applyFilters}>
          <div className="modern-search-main">
            <SearchIcon />
            <label className="sr-only" htmlFor="scholarship-search">Search scholarships</label>
            <input id="scholarship-search" maxLength={120} placeholder="Scholarship name, course, benefit, or provider" value={filters.q} onChange={(event) => setFilters({ ...filters, q: event.target.value })} />
            <button className="modern-button-primary" type="submit">Find scholarships</button>
          </div>
          <div className="modern-filter-grid">
            <label className="modern-filter-label">Location<select value={filters.state_code} onChange={(event) => setFilters({ ...filters, state_code: event.target.value })}>{states.map(([value, label]) => <option key={value || 'all'} value={value}>{label}</option>)}</select></label>
            <label className="modern-filter-label">Provider<select value={filters.organization_type} onChange={(event) => setFilters({ ...filters, organization_type: event.target.value as OrganizationType | '' })}>{organizationTypes.map((option) => <option key={option.value || 'all'} value={option.value}>{option.label}</option>)}</select></label>
            <label className="modern-filter-label">Education<select value={filters.education_level} onChange={(event) => setFilters({ ...filters, education_level: event.target.value })}>{educationLevels.map(([value, label]) => <option key={value || 'all'} value={value}>{label}</option>)}</select></label>
            <label className="modern-filter-label">Course<select value={filters.course} onChange={(event) => setFilters({ ...filters, course: event.target.value })}>{courseFamilies.map(([value, label]) => <option key={value || 'all'} value={value}>{label}</option>)}</select></label>
          </div>
          <div className="catalog-filter-footer mt-4 flex justify-between items-center text-sm font-medium text-slate-500">
            <span>{activeFilterCount ? `${activeFilterCount} filter${activeFilterCount === 1 ? '' : 's'} applied` : 'All scholarships'}</span>
            {activeFilterCount > 0 && <button className="text-orange-500 hover:text-orange-600 transition-colors" type="button" onClick={clearFilters}>Clear filters</button>}
          </div>
        </form>
      </section>

      <section className="modern-results-section" aria-live="polite">
        <div className="modern-results-heading">
          <div><h2>{query.q ? `Results for “${query.q}”` : 'Scholarships'}</h2><p>{activeFilterCount ? 'Results matching the selected filters.' : 'Select a scholarship to check its details.'}</p></div>
          {!loading && !error && <strong>{firstResult}–{lastResult} <span>of {catalog.total}</span></strong>}
        </div>
        {notice && <div className="notice-banner modern-container mb-6"><p>{notice}</p></div>}
        {error && <div className="catalog-error modern-container mb-6" role="alert"><div><h3>Scholarships could not be loaded</h3><p>{error}</p></div><button className="modern-button-secondary" type="button" onClick={() => setRetry((value) => value + 1)}>Try again</button></div>}
        {loading ? (
          <div className="modern-scholarship-grid" aria-label="Loading scholarships">{Array.from({ length: 6 }, (_, index) => <div className="scholarship-skeleton" key={index}><i /><i /><i /><i /></div>)}</div>
        ) : !error && catalog.items.length === 0 ? (
          <div className="empty-state catalog-empty modern-container"><SearchIcon /><h3>No scholarships found</h3><p>Remove a filter or use a broader search term.</p><button className="modern-button-secondary" type="button" onClick={clearFilters}>Show all scholarships</button></div>
        ) : !error ? (
          <div className="modern-scholarship-grid">{catalog.items.map((scholarship) => <ScholarshipCard key={scholarship.id} scholarship={scholarship} onSave={(id) => void saveScholarship(id)} />)}</div>
        ) : null}
        {!loading && !error && catalog.total > PAGE_SIZE && (
          <nav className="modern-pagination" aria-label="Scholarship result pages">
            <button className="modern-button-secondary" type="button" disabled={query.offset === 0} onClick={() => changePage(Math.max(0, query.offset - PAGE_SIZE))}>← Previous</button>
            <span className="text-sm font-medium text-slate-500">Page <strong className="text-slate-900">{currentPage}</strong> of {totalPages}</span>
            <button className="modern-button-secondary" type="button" disabled={query.offset + PAGE_SIZE >= catalog.total} onClick={() => changePage(query.offset + PAGE_SIZE)}>Next →</button>
          </nav>
        )}
      </section>
    </main>
  )
}
