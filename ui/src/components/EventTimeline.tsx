import { useMemo } from 'react'
import type { EnrichedEvent } from '@/api/types'
import { eventKind, eventTitle, isTimelineEvent, minute, type Names } from '@/lib/format'
import { cn } from '@/lib/utils'

const DOT: Record<string, string> = {
  goal: 'size-4 bg-primary ring-2 ring-primary/40',
  shot: 'size-3 border-2 border-primary bg-background',
  tackle: 'size-3 bg-foreground',
  pass: 'size-2.5 bg-muted-foreground',
}
const KIND: Record<string, string> = { goal: 'Goal', shot: 'Shot', tackle: 'Ball won', pass: 'Pass' }

interface Props { events: EnrichedEvent[]; names: Names; duration: number; time: number; onSeek: (t: number) => void }

/** Marks for line-breaking passes, shots (with engine xG), goals and ball wins. A click seeks the video to the event's t_s. */
export function EventTimeline({ events, names, duration, time, onSeek }: Props) {
  const marks = useMemo(() => events.filter(isTimelineEvent), [events])
  return (
    <div className="flex flex-col gap-3">
      <div
        className="relative h-9 cursor-pointer rounded-lg border bg-card"
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect()
          onSeek(Math.min(duration, Math.max(0, ((e.clientX - r.left) / r.width) * duration)))
        }}
      >
        <div className="absolute inset-y-0 left-0 rounded-l-lg bg-muted" style={{ width: `${(time / duration) * 100}%` }} />
        <div className="absolute inset-y-1 w-0.5 bg-primary" style={{ left: `${(time / duration) * 100}%` }} />
        {marks.map((e, i) => (
          <button
            key={i} type="button" title={`${minute(e.clock_s)} ${eventTitle(e, names)}`}
            aria-label={`${minute(e.clock_s)} ${eventTitle(e, names)}`}
            onClick={(ev) => { ev.stopPropagation(); onSeek(e.t_s) }}
            className={cn('absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full', DOT[eventKind(e)], e.team === 'away' && eventKind(e) === 'pass' && 'opacity-70')}
            style={{ left: `${(e.t_s / duration) * 100}%` }}
          />
        ))}
      </div>
      <ul className="flex max-h-44 flex-col gap-1 overflow-y-auto pr-1" aria-label="Events">
        {marks.map((e, i) => {
          const past = e.t_s <= time
          return (
            <li key={i}>
              <button
                type="button" onClick={() => onSeek(e.t_s)}
                className={cn('flex w-full items-center gap-3 rounded-md border px-3 py-1.5 text-left text-sm hover:border-primary', !past && 'text-muted-foreground')}
              >
                <span className="w-9 font-semibold tabular-nums">{minute(e.clock_s)}</span>
                <span className={cn('inline-block shrink-0 rounded-full', DOT[eventKind(e)])} aria-hidden />
                <span className="w-16 shrink-0 text-xs text-muted-foreground">{KIND[eventKind(e)]}</span>
                <span className="truncate">{eventTitle(e, names)}</span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
