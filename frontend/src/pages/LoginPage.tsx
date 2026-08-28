import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { BuildingIcon, UserIcon } from '../components/Icons'
import { destinationForRealm, useAuth } from '../context/AuthContext'

function safeReturnPath(value: unknown): string | null {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return null
  return value
}

export function LoginPage() {
  const { realm } = useParams()
  const isOrganization = realm === 'organization'
  const selectedRealm = isOrganization ? 'organization' : 'student'
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const locationState = location.state as { from?: unknown } | null
  const returnTo = !isOrganization ? safeReturnPath(locationState?.from) : null
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (realm !== 'student' && realm !== 'organization') {
    return <Navigate to="/login/student" replace />
  }
  if (user) {
    const destination = user.realm === 'STUDENT' && returnTo ? returnTo : destinationForRealm(user.realm)
    return <Navigate to={destination} replace />
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const session = await login(selectedRealm, email, password)
      const destination = session.realm === 'STUDENT' && returnTo ? returnTo : destinationForRealm(session.realm)
      navigate(destination, { replace: true })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to sign in')
    } finally {
      setSubmitting(false)
    }
  }

  const AccountIcon = isOrganization ? BuildingIcon : UserIcon

  return (
    <main className={isOrganization ? 'auth-page provider-auth-page' : 'auth-page student-auth-page'}>
      <section className="auth-story">
        <div className="auth-story-inner">
          <div className="auth-audience-mark"><AccountIcon /></div>
          <p className="section-kicker">{isOrganization ? 'Provider account' : 'Student account'}</p>
          <h1>{isOrganization ? 'Manage your scholarships' : 'Manage your scholarship activity'}</h1>
          <p>
            {isOrganization
              ? 'Sign in to add, update, publish, or pause scholarships for your organization.'
              : 'Sign in to save scholarships and manage your applications.'}
          </p>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-form-wrap">
          <Link className="back-link" to={isOrganization ? '/providers' : '/scholarships'}>
            ← Back to {isOrganization ? 'provider information' : 'scholarships'}
          </Link>

          <div className="single-realm-badge">
            <AccountIcon />
            <span>{isOrganization ? 'Provider account' : 'Student account'}</span>
          </div>

          <div className="auth-heading">
            <p>{isOrganization ? 'Provider sign in' : 'Student sign in'}</p>
            <h2>Sign in</h2>
            <span>
              {isOrganization
                ? 'Use your organization-owner account.'
                : 'Use your student account.'}
            </span>
          </div>

          <form className="auth-form" onSubmit={(event) => void handleSubmit(event)}>
            <label>
              Email address
              <input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </label>
            <label>
              Password
              <input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="button button-primary button-full" type="submit" disabled={submitting}>
              {submitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>
      </section>
    </main>
  )
}
