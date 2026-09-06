import { useEffect, useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import { api } from '../lib/api'
import type { ApplicationIntentBatchResponse } from '../types'

export const APPLICATION_INTENTS_RESUMED_EVENT = 'scholarsaathi:application-intents-resumed'

/** Claims anonymous apply requests after sign-in and safely resumes every pending workflow. */
export function IntentResumeCoordinator() {
  const { user, loading } = useAuth()
  const resumedForRef = useRef<string | null>(null)

  useEffect(() => {
    if (loading || user?.realm !== 'STUDENT' || resumedForRef.current === user.id) return
    resumedForRef.current = user.id
    void api<ApplicationIntentBatchResponse>('/api/student/application-intents/resume', {
      method: 'POST',
    })
      .then((result) => {
        if (result.items.length > 0) {
          window.dispatchEvent(
            new CustomEvent<ApplicationIntentBatchResponse>(APPLICATION_INTENTS_RESUMED_EVENT, {
              detail: result,
            }),
          )
        }
      })
      .catch(() => {
        // A pending action remains durable on the server and can be retried on the next session.
        resumedForRef.current = null
      })
  }, [loading, user])

  useEffect(() => {
    if (!user) resumedForRef.current = null
  }, [user])

  return null
}
