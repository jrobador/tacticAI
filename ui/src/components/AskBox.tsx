import { useState } from 'react'
import { Loader2, MessageCircleQuestion } from 'lucide-react'
import { ApiError, askMatch } from '@/api/client'
import type { AskResponse, Lang } from '@/api/types'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { minute } from '@/lib/format'

function messageOf(e: unknown): { text: string; unavailable: boolean } {
  if (!(e instanceof ApiError)) return { text: 'Something went wrong. Try again.', unavailable: false }
  const retry = (e.detail as { retry_after_s?: number } | null)?.retry_after_s
  if (e.status === 501) return { text: 'Match Q&A is not available yet', unavailable: true }
  if (e.status === 429) return { text: `Too many questions. Try again in ${retry ? `${Math.ceil(retry / 60)} min` : 'a moment'}.`, unavailable: false }
  if (e.status === 503) return { text: 'The model did not answer in time. Try again.', unavailable: false }
  if (e.status === 502) return { text: 'The answer could not be verified, so it is not shown. Try rephrasing.', unavailable: false }
  return { text: e.message, unavailable: false }
}

/** "Ask the match": one question, a verified answer and the moments it cites (click to jump). */
export function AskBox({ matchId, lang, onSeek }: { matchId: string; lang: Lang; onSeek: (t: number) => void }) {
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [unavailable, setUnavailable] = useState(false)

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!question.trim() || busy || unavailable) return
    setBusy(true); setError(null); setAnswer(null)
    try {
      setAnswer(await askMatch(matchId, question.trim(), lang))
    } catch (e) {
      const m = messageOf(e)
      setError(m.text); setUnavailable(m.unavailable)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold"><MessageCircleQuestion className="size-4" /> Ask the match</h2>
        <form onSubmit={submit} className="flex gap-2">
          <Input
            value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={500} disabled={unavailable}
            placeholder="e.g. Show me every goal" aria-label="Ask the match a question"
          />
          <Button type="submit" disabled={busy || unavailable || !question.trim()}>{busy ? <Loader2 className="animate-spin" /> : 'Ask'}</Button>
        </form>
        {error && <Alert>{error}</Alert>}
        {answer && (
          <div className="flex flex-col gap-2 text-sm">
            <p>{answer.answer}</p>
            {answer.moments.length > 0 && (
              <ul className="flex flex-wrap gap-2">
                {answer.moments.map((m) => (
                  <li key={`${m.kind}-${m.insight_id ?? m.event_index}`}>
                    <Button variant="outline" size="sm" onClick={() => onSeek(m.t_s)} aria-label={`Jump to minute ${minute(m.clock_s)}`}>
                      {minute(m.clock_s)} · {m.period === 1 ? '1st half' : '2nd half'}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
