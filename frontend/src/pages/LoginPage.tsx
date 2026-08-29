import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { BuildingIcon, UserIcon } from '../components/Icons'
import { destinationForRealm, useAuth } from '../context/AuthContext'
import { ApiError } from '../lib/api'

type StudentAuthMode = 'signin' | 'register'

function safeReturnPath(value: unknown): string | null {
  if (typeof value !== 'string' || !value.startsWith('/')) return null
  try {
    const target = new URL(value, window.location.origin)
    if (target.origin !== window.location.origin) return null
    return `${target.pathname}${target.search}${target.hash}`
  } catch {
    return null
  }
}

export function LoginPage() {
  const { realm } = useParams()
  const isOrganization = realm === 'organization'
  const selectedRealm = isOrganization ? 'organization' : 'student'
  const { user, login, registerStudent } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const locationState = location.state as { from?: unknown } | null
  const returnTo = !isOrganization ? safeReturnPath(locationState?.from) : null
  const requestedMode = new URLSearchParams(location.search).get('mode')
  const [studentMode, setStudentMode] = useState<StudentAuthMode>(requestedMode === 'register' ? 'register' : 'signin')
  const [displayAlias, setDisplayAlias] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirmation, setPasswordConfirmation] = useState('')
  const [preferredLanguage, setPreferredLanguage] = useState('en')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const isRegistering = !isOrganization && studentMode === 'register'

  if (realm !== 'student' && realm !== 'organization') {
    return <Navigate to="/login/student" replace />
  }
  if (user) {
    const destination = user.realm === 'STUDENT' && returnTo ? returnTo : destinationForRealm(user.realm)
    return <Navigate to={destination} replace />
  }

  function changeStudentMode(mode: StudentAuthMode) {
    setStudentMode(mode)
    setPassword('')
    setPasswordConfirmation('')
    setError('')
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError('')

    if (isRegistering && password !== passwordConfirmation) {
      setError('Passwords do not match.')
      return
    }

    setSubmitting(true)
    try {
      const session = isRegistering
        ? await registerStudent({
            email,
            password,
            password_confirmation: passwordConfirmation,
            ...(displayAlias.trim() ? { display_alias: displayAlias.trim() } : {}),
            preferred_language: preferredLanguage,
          })
        : await login(selectedRealm, email, password)
      const destination = session.realm === 'STUDENT' && returnTo ? returnTo : destinationForRealm(session.realm)
      navigate(destination, { replace: true })
    } catch (caught) {
      if (isRegistering && caught instanceof ApiError && caught.status === 409) {
        setError('An account already uses this email. Choose Sign in instead.')
      } else if (caught instanceof ApiError && caught.status === 429) {
        setError('Too many account creation attempts. Please wait and try again.')
      } else {
        setError(caught instanceof Error ? caught.message : isRegistering ? 'Unable to create account' : 'Unable to sign in')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const AccountIcon = isOrganization ? BuildingIcon : UserIcon
  const heading = isRegistering ? 'Create your student account' : 'Sign in'

  return (
    <main className="modern-auth-page">
      <div className="modern-auth-overlay"></div>
      
      <section className="modern-auth-container">
        <div className="modern-auth-card">
          <Link className="modern-back-link" to={isOrganization ? '/providers' : '/scholarships'}>
            ← Back to {isOrganization ? 'provider information' : 'scholarships'}
          </Link>

          <div className="modern-auth-header">
            <img src="/logo.png" alt="ScholarSaathi Logo" className="modern-auth-logo" />
            <h2>{heading}</h2>
            <p>
              {isOrganization
                ? 'Use your organization-owner account.'
                : isRegistering
                  ? 'Use an email you can access and create a secure password.'
                  : 'Use your student account.'}
            </p>
          </div>

          {!isOrganization && (
            <div className="modern-auth-switch" role="group" aria-label="Student account access">
              <button className={studentMode === 'signin' ? 'active' : ''} type="button" aria-pressed={studentMode === 'signin'} onClick={() => changeStudentMode('signin')}>Sign in</button>
              <button className={studentMode === 'register' ? 'active' : ''} type="button" aria-pressed={studentMode === 'register'} onClick={() => changeStudentMode('register')}>Create account</button>
            </div>
          )}

          <form className="modern-auth-form" onSubmit={(event) => void handleSubmit(event)}>
            {isRegistering && (
              <div className="modern-form-group">
                <label>Display name <small>(Optional)</small></label>
                <input type="text" autoComplete="name" maxLength={80} value={displayAlias} onChange={(event) => setDisplayAlias(event.target.value)} />
              </div>
            )}
            
            <div className="modern-form-group">
              <label>Email address</label>
              <input type="email" autoComplete="email" maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} required />
            </div>

            <div className="modern-form-group">
              <label>Password</label>
              <input type="password" autoComplete={isRegistering ? 'new-password' : 'current-password'} minLength={8} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} required />
              {isRegistering && <span className="modern-help-text">Use at least 8 characters.</span>}
            </div>

            {isRegistering && (
              <>
                <div className="modern-form-group">
                  <label>Confirm password</label>
                  <input type="password" autoComplete="new-password" minLength={8} maxLength={128} value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} required />
                </div>
                <div className="modern-form-group">
                  <label>Preferred language</label>
                  <select value={preferredLanguage} onChange={(event) => setPreferredLanguage(event.target.value)}>
                    <option value="en">English</option>
                    <option value="hi">Hindi</option>
                    <option value="or">Odia</option>
                  </select>
                </div>
              </>
            )}

            {error && <p className="modern-form-error" role="alert">{error}</p>}
            
            <button className="modern-button-primary" type="submit" disabled={submitting}>
              {submitting ? (isRegistering ? 'Creating account…' : 'Signing in…') : (isRegistering ? 'Create account' : 'Sign in')}
            </button>
          </form>

          {!isOrganization && (
            <div className="modern-auth-footer">
              <p>
                {isRegistering ? 'Already have an account?' : 'New to ScholarSaathi?'}
              </p>
              <button type="button" onClick={() => changeStudentMode(isRegistering ? 'signin' : 'register')}>
                {isRegistering ? 'Sign in instead' : 'Create an account'}
              </button>
            </div>
          )}
        </div>
      </section>
    </main>
  )
}
