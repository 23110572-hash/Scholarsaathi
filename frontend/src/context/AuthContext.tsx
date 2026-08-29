import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { PropsWithChildren } from 'react'
import { api, ApiError } from '../lib/api'
import type { AccountRealm, SessionUser, StudentRegistrationInput } from '../types'

interface AuthContextValue {
  user: SessionUser | null
  loading: boolean
  login: (realm: 'student' | 'organization', email: string, password: string) => Promise<SessionUser>
  registerStudent: (input: StudentRegistrationInput) => Promise<SessionUser>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<SessionUser | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setUser(await api<SessionUser>('/api/auth/me'))
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) {
        console.warn('Unable to restore the current session')
      }
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const login = useCallback(
    async (realm: 'student' | 'organization', email: string, password: string) => {
      const sessionUser = await api<SessionUser>(`/api/auth/${realm}/login`, {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      setUser(sessionUser)
      return sessionUser
    },
    [],
  )

  const registerStudent = useCallback(async (input: StudentRegistrationInput) => {
    const sessionUser = await api<SessionUser>('/api/auth/student/register', {
      method: 'POST',
      body: JSON.stringify(input),
    })
    if (sessionUser.realm !== 'STUDENT') {
      throw new Error('The server did not create a student account')
    }
    setUser(sessionUser)
    return sessionUser
  }, [])

  const logout = useCallback(async () => {
    await api<{ message: string }>('/api/auth/logout', { method: 'POST' })
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, login, registerStudent, logout, refresh }),
    [user, loading, login, registerStudent, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return context
}

export function destinationForRealm(realm: AccountRealm): string {
  return realm === 'STUDENT' ? '/student' : '/organization'
}
