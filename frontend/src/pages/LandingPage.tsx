import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowIcon, BuildingIcon, SearchIcon } from '../components/Icons'

const providerGroups = [
  ['Central Government', 'CENTRAL_GOVERNMENT'],
  ['State Government', 'STATE_GOVERNMENT'],
  ['Private Companies', 'PRIVATE_COMPANY'],
  ['NGOs', 'NGO'],
] as const

const steps = [
  ['1', 'Search', 'Enter your course, location, scholarship name, or provider.'],
  ['2', 'Check eligibility', 'Read the study level, course, location, benefit, and closing date.'],
  ['3', 'Ask a question', 'Open a scholarship and ask about its requirements on the same page.'],
  ['4', 'Apply', 'Review the requested information before starting an application.'],
]

export function LandingPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  function searchScholarships(event: FormEvent) {
    event.preventDefault()
    const params = new URLSearchParams()
    if (query.trim()) params.set('q', query.trim())
    navigate(`/scholarships${params.size ? `?${params.toString()}` : ''}`)
  }

  return (
    <main className="portal-home">
      <section className="portal-intro">
        <div className="section-pad portal-intro-grid">
          <div className="portal-intro-copy">
            <p className="portal-page-label">Scholarship search</p>
            <h1>Find your eligible scholarship</h1>
            <p>Search by scholarship name, course, location, benefit, or provider.</p>
            <form className="home-search-form" onSubmit={searchScholarships}>
              <label className="sr-only" htmlFor="home-scholarship-search">Search scholarships</label>
              <SearchIcon />
              <input
                id="home-scholarship-search"
                maxLength={120}
                placeholder="Enter scholarship, course, state, or provider"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <button className="button button-primary" type="submit">Search</button>
            </form>
            <div className="portal-intro-actions">
              <Link to="/scholarships">View all scholarships <ArrowIcon /></Link>
              <Link to="/login/student">Student sign in</Link>
            </div>
          </div>
          <aside className="search-help-box">
            <h2>Search using</h2>
            <ul>
              <li>Your State or Union Territory</li>
              <li>Current education level and course</li>
              <li>Scholarship provider or programme name</li>
              <li>Application deadline or benefit</li>
            </ul>
          </aside>
        </div>
      </section>

      <section className="home-section section-pad" aria-labelledby="provider-heading">
        <div className="plain-section-heading">
          <p className="portal-page-label">Browse scholarships</p>
          <h2 id="provider-heading">Select a provider category</h2>
        </div>
        <div className="provider-link-grid">
          {providerGroups.map(([label, value]) => (
            <Link key={value} to={`/scholarships?organization_type=${value}`}>
              <BuildingIcon />
              <span>{label}</span>
              <ArrowIcon />
            </Link>
          ))}
        </div>
      </section>

      <section className="home-process">
        <div className="section-pad">
          <div className="plain-section-heading">
            <p className="portal-page-label">Before applying</p>
            <h2>Follow these steps</h2>
          </div>
          <ol className="plain-step-grid">
            {steps.map(([number, title, copy]) => (
              <li key={number}><span>{number}</span><div><h3>{title}</h3><p>{copy}</p></div></li>
            ))}
          </ol>
        </div>
      </section>

      <section className="home-section section-pad home-question-section">
        <div>
          <p className="portal-page-label">Scholarship questions</p>
          <h2>Ask about a scholarship</h2>
          <p>Open any scholarship to ask about eligibility, benefits, dates, documents, or the application process.</p>
        </div>
        <Link className="button button-primary" to="/scholarships">Choose a scholarship <ArrowIcon /></Link>
      </section>

      <section className="home-account-row section-pad">
        <article><h2>For students</h2><p>Sign in to save scholarships and manage applications.</p><Link to="/login/student">Student sign in <ArrowIcon /></Link></article>
        <article><h2>For providers</h2><p>Manage scholarship records and student applications.</p><Link to="/providers">Provider information <ArrowIcon /></Link></article>
      </section>
    </main>
  )
}
