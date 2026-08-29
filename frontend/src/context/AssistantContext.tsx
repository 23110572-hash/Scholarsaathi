import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { PropsWithChildren } from 'react'

interface AssistantContextValue {
  open: boolean
  /** Opens the assistant panel, optionally queueing a question to send immediately. */
  openAssistant: (question?: string) => void
  closeAssistant: () => void
  toggleAssistant: () => void
  /** A question waiting to be sent, consumed once by the assistant. */
  pendingQuestion: string | null
  clearPendingQuestion: () => void
}

const AssistantContext = createContext<AssistantContextValue | null>(null)

/**
 * The floating assistant lives outside the route tree, so pages cannot reach it by props.
 * This shares just enough state for a page to open it and hand it a question to ask.
 */
export function AssistantProvider({ children }: PropsWithChildren) {
  const [open, setOpen] = useState(false)
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null)

  const openAssistant = useCallback((question?: string) => {
    if (question?.trim()) setPendingQuestion(question.trim())
    setOpen(true)
  }, [])

  const closeAssistant = useCallback(() => {
    setOpen(false)
    setPendingQuestion(null)
  }, [])

  const toggleAssistant = useCallback(() => {
    setOpen((current) => !current)
  }, [])

  const clearPendingQuestion = useCallback(() => setPendingQuestion(null), [])

  const value = useMemo(
    () => ({
      open,
      openAssistant,
      closeAssistant,
      toggleAssistant,
      pendingQuestion,
      clearPendingQuestion,
    }),
    [open, openAssistant, closeAssistant, toggleAssistant, pendingQuestion, clearPendingQuestion],
  )

  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>
}

export function useAssistant(): AssistantContextValue {
  const context = useContext(AssistantContext)
  if (!context) {
    throw new Error('useAssistant must be used inside AssistantProvider')
  }
  return context
}
