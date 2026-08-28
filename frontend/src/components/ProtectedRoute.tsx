import type { PropsWithChildren } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import type { AccountRealm } from '../types'

interface ProtectedRouteProps extends PropsWithChildren {
  realm: AccountRealm
}

export function ProtectedRoute({ realm, children }: ProtectedRouteProps) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <main className="screen-center" aria-live="polite">
        <div className="loader" />
        <p>Restoring your secure session…</p>
      </main>
    )
  }

  if (!user || user.realm !== realm) {
    const loginRealm = realm === 'STUDENT' ? 'student' : 'organization'
    const returnPath = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to={`/login/${loginRealm}`} state={{ from: returnPath }} replace />
  }

  return children
}
