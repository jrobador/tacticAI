// Speech-to-text for the New match box. The SDK is loaded on the first click so the main bundle does not carry it.
import { useEffect, useRef, useState } from 'react'
import { ApiError, speechToken } from '@/api/client'

type Recognizer = import('microsoft-cognitiveservices-speech-sdk').SpeechRecognizer

export function useSpeech(onInterim: (text: string) => void, onFinal: (text: string) => void) {
  const [listening, setListening] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const rec = useRef<Recognizer | null>(null)
  const starting = useRef(false)
  const cb = useRef({ onInterim, onFinal })
  cb.current = { onInterim, onFinal }

  // Continuous: pauses do not end it; every recognized phrase adds to `said`. A second click stops and leaves the text in the box.
  const said = useRef('')
  const stop = () => {
    const r = rec.current
    rec.current = null
    setListening(false)
    if (!r) return
    const text = said.current.trim()
    r.stopContinuousRecognitionAsync(() => r.close(), () => r.close())
    if (text) cb.current.onFinal(text)
    else setError("Didn't catch that. Try again or type it.")
  }
  useEffect(() => () => { rec.current?.close() }, [])

  async function toggle() {
    if (rec.current) return stop()
    if (starting.current) return
    starting.current = true
    setError(null)
    setListening(true)
    try {
      const { token, region } = await speechToken()
      const sdk = await import('microsoft-cognitiveservices-speech-sdk')
      const cfg = sdk.SpeechConfig.fromAuthorizationToken(token, region)
      const r = sdk.SpeechRecognizer.FromConfig(cfg, sdk.AutoDetectSourceLanguageConfig.fromLanguages(['en-US', 'es-AR']), sdk.AudioConfig.fromDefaultMicrophoneInput())
      rec.current = r
      said.current = ''
      const join = (more: string) => [said.current, more].filter(Boolean).join(' ')
      r.recognizing = (_, e) => cb.current.onInterim(join(e.result.text))
      r.recognized = (_, e) => {
        if (e.result.reason !== sdk.ResultReason.RecognizedSpeech || !e.result.text.trim()) return
        said.current = join(e.result.text.trim())
        cb.current.onInterim(said.current)
      }
      r.canceled = (_, e) => {
        if (rec.current !== r) return
        rec.current = null
        setListening(false)
        r.close()
        if (e.reason === sdk.CancellationReason.Error) setError('Microphone not available. Check the permission or type it.')
      }
      r.startContinuousRecognitionAsync(undefined, () => {
        if (rec.current === r) { rec.current = null; setListening(false); r.close() }
        setError('Microphone not available. Check the permission or type it.')
      })
    } catch (e) {
      stop()
      setError(e instanceof ApiError && e.status === 503 ? 'Voice input is not configured' : e instanceof ApiError ? "Voice input isn't available right now" : "Didn't catch that. Try again or type it.")
    }
    starting.current = false
  }

  return { listening, error, toggle }
}
