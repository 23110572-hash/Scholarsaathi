import { useCallback, useEffect, useRef, useState } from 'react'

type RecognitionState = 'idle' | 'listening' | 'stopping' | 'error'

interface SpeechRecognitionAlternativeLike {
  transcript: string
}

interface SpeechRecognitionResultLike {
  isFinal: boolean
  length: number
  [index: number]: SpeechRecognitionAlternativeLike
}

interface SpeechRecognitionEventLike {
  resultIndex: number
  results: {
    length: number
    [index: number]: SpeechRecognitionResultLike
  }
}

interface SpeechRecognitionErrorLike {
  error: string
}

interface SpeechRecognitionLike {
  continuous: boolean
  interimResults: boolean
  lang: string
  onstart: (() => void) | null
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: SpeechRecognitionErrorLike) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike

type SpeechWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor
  webkitSpeechRecognition?: SpeechRecognitionConstructor
}

const languageLocales: Record<string, string> = {
  en: 'en-IN',
  hi: 'hi-IN',
  or: 'or-IN',
  bn: 'bn-IN',
  ta: 'ta-IN',
  te: 'te-IN',
  mr: 'mr-IN',
}

function recognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === 'undefined') return null
  const speechWindow = window as SpeechWindow
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null
}

function errorMessage(code: string): string {
  if (code === 'not-allowed' || code === 'service-not-allowed') {
    return 'Microphone permission was denied. Allow microphone access or continue typing.'
  }
  if (code === 'no-speech') return 'I could not hear anything. Please try speaking again.'
  if (code === 'audio-capture') return 'No working microphone was found.'
  if (code === 'network') return 'Voice recognition is unavailable right now. You can still type.'
  return 'Voice recognition stopped unexpectedly. Please try again.'
}

export function useSpeechRecognition(
  language: string,
  onFinalTranscript: (transcript: string) => void,
) {
  const [state, setState] = useState<RecognitionState>('idle')
  const [interimTranscript, setInterimTranscript] = useState('')
  const [error, setError] = useState('')
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const callbackRef = useRef(onFinalTranscript)
  callbackRef.current = onFinalTranscript
  const supported = recognitionConstructor() !== null

  const abort = useCallback(() => {
    recognitionRef.current?.abort()
    recognitionRef.current = null
    setInterimTranscript('')
    setState('idle')
  }, [])

  const stop = useCallback(() => {
    if (!recognitionRef.current) return
    setState('stopping')
    recognitionRef.current.stop()
  }, [])

  const start = useCallback(() => {
    const Constructor = recognitionConstructor()
    if (!Constructor || state === 'listening' || state === 'stopping') return

    setError('')
    setInterimTranscript('')
    const recognition = new Constructor()
    recognition.continuous = false
    recognition.interimResults = true
    recognition.lang = languageLocales[language] ?? 'en-IN'
    recognition.onstart = () => setState('listening')
    recognition.onresult = (event) => {
      let interim = ''
      let finalText = ''
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index]
        if (!result) continue
        const text = result[0]?.transcript ?? ''
        if (result.isFinal) finalText += text
        else interim += text
      }
      setInterimTranscript(interim.trim())
      if (finalText.trim()) callbackRef.current(finalText.trim())
    }
    recognition.onerror = (event) => {
      setError(errorMessage(event.error))
      setState('error')
    }
    recognition.onend = () => {
      recognitionRef.current = null
      setInterimTranscript('')
      setState((current) => (current === 'error' ? 'error' : 'idle'))
    }
    recognitionRef.current = recognition
    try {
      recognition.start()
    } catch {
      recognitionRef.current = null
      setState('error')
      setError('The microphone could not start. Please try again or continue typing.')
    }
  }, [language, state])

  useEffect(() => abort, [abort])

  return {
    supported,
    state,
    listening: state === 'listening' || state === 'stopping',
    interimTranscript,
    error,
    start,
    stop,
    abort,
  }
}
