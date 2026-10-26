import { useState } from 'react'
import { ApiError, askMatch } from '@/api/client'
import type { AskMoment, AskResponse, EnrichedEvent, Insight, Lang } from '@/api/types'
import { eventTitle, mmss, type Names } from '@/lib/format'
import { go } from '@/lib/nav'
import { momentText, type Texts } from './MomentsTab'
import { kindLabel } from './model'

function messageOf(e: unknown): string {
  if (!(e instanceof ApiError)) return 'Something went wrong. Try again.'
  const retry = (e.detail as { retry_after_s?: number } | null)?.retry_after_s
  if (e.status === 501) return 'Match Q&A is not available yet'
  if (e.status === 429) return `Too many questions. Try again in ${retry ? `${Math.ceil(retry / 60)} min` : 'a moment'}.`
  if (e.status === 503) return 'The model did not answer in time. Try again.'
  if (e.status === 502) return 'The answer could not be verified, so it is not shown. Try rephrasing.'
  return e.message
}

interface Props {
  matchId: string
  lang: Lang
  examples: string[]
  placeholder: string
  insights: Insight[]
  events: EnrichedEvent[]
  names: Names
  texts: Texts
  onSeek: (t: number) => void
}

/** Match Q&A: the answer is a list of moments; a click jumps the video. */
export function AskTab({ matchId, lang, examples, placeholder, insights, events, names, texts, onSeek }: Props) {
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const ask = async (q: string) => {
    if (!q.trim() || busy) return
    setBusy(true); setError(null); setAnswer(null)
    try {
      setAnswer(await askMatch(matchId, q.trim(), lang))
    } catch (e) {
      setError(messageOf(e))
    } finally {
      setBusy(false)
    }
  }

  const row = (m: AskMoment): { title: string; detail: string } => {
    if (m.kind === 'insight') {
      const i = insights.find((x) => x.insight_id === m.insight_id)
      return i ? { title: kindLabel(i.kind), detail: momentText(i, texts) } : { title: 'Moment', detail: '' }
    }
    const e = m.event_index == null ? undefined : events[m.event_index]
    return e ? { title: eventTitle(e, names), detail: '' } : { title: 'Event', detail: '' }
  }

  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-xs leading-normal text-dim">Ask about this match. Answers are moments; click one to jump the video.</span>
      <form className="flex gap-1.5" onSubmit={(e) => { e.preventDefault(); void ask(question) }}>
        <input
          value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={500} aria-label="Ask the match a question" placeholder={placeholder}
          className="min-w-0 flex-1 rounded-[9px] border border-foreground/20 bg-background px-[11px] py-[9px] text-[13.5px] outline-none focus:border-primary"
        />
        <button type="submit" disabled={busy || !question.trim()} className="rounded-[9px] border border-foreground/20 bg-[#152034] px-3 text-[13px] font-semibold hover:border-primary hover:text-primary disabled:opacity-50">
          {busy ? 'Asking…' : 'Ask'}
        </button>
      </form>
      <div className="flex flex-wrap gap-1.5">
        {examples.map((q) => (
          <button
            key={q} type="button" onClick={() => { setQuestion(q); void ask(q) }}
            className="rounded-full border border-foreground/15 px-[9px] py-[5px] text-left text-xs font-medium text-muted-foreground hover:border-foreground/40 hover:text-foreground"
          >
            {q}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="rounded-[10px] border border-foreground/20 px-3 py-2 text-[12.5px] text-muted-foreground">{error}</p>}
      {answer && answer.moments.length > 0 && (
        <div className="flex flex-col">
          <span className="pb-1.5 pt-1 font-mono text-[10.5px] font-semibold uppercase tracking-[.05em] text-primary">Match Q&A · {answer.answer}</span>
          {answer.moments.map((m) => {
            const r = row(m)
            return (
              <button
                key={`${m.kind}-${m.insight_id ?? m.event_index}`} type="button" onClick={() => onSeek(m.t_s)}
                className="-mx-1.5 grid grid-cols-[44px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-md border-0 border-t border-foreground/10 px-1.5 py-[9px] text-left hover:bg-[#16223a]"
              >
                <span className="font-mono text-[11.5px] font-medium text-primary">{mmss(m.clock_s)}</span>
                <span className="flex flex-col gap-0.5"><span className="text-[13px] font-semibold">{r.title}</span>{r.detail && <span className="text-xs text-muted-foreground">{r.detail}</span>}</span>
                <span className="text-[11.5px] font-semibold text-muted-foreground">Jump</span>
              </button>
            )
          })}
        </div>
      )}
      {answer && answer.moments.length === 0 && (
        <div role="alert" className="grid grid-cols-[26px_minmax(0,1fr)] items-start gap-2.5 rounded-xl border-[1.5px] border-foreground bg-[#141f33] px-3.5 py-3">
          <span className="grid size-[26px] place-items-center rounded-md bg-foreground text-[13px] font-bold leading-none text-background">✕</span>
          <div className="flex flex-col gap-1">
            <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[.06em]">Error · TAI-QA-001</span>
            <span className="font-heading text-sm font-semibold">No moments matched</span>
            <span className="text-[12.5px] leading-normal text-muted-foreground">Ask about shots, goals, line-breaking passes, pressure or ball wins, or name a player.</span>
            <button type="button" onClick={() => go('/arch')} className="self-start py-0.5 text-xs font-semibold text-primary hover:text-foreground">About TAI-QA-001 →</button>
          </div>
        </div>
      )}
    </div>
  )
}
