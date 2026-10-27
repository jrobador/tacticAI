// The latest key events on the video, as a lower third: what just happened, who, and its model number.
import type { EnrichedEvent, MatchMeta, ModelCard } from '@/api/types'
import { eventTitle, isTimelineEvent, mmss, type Names } from '@/lib/format'
import { cn } from '@/lib/utils'
import { modelText, type ModelId } from './modelInfo'

/** Seconds an event stays on the video after it happens (it also stays while the video holds on it). */
export const EVENT_SHOW_S = 4

/** Events worth showing on the video: the timeline ones plus set pieces. */
export const isKeyEvent = (e: EnrichedEvent) => isTimelineEvent(e) || e.type === 'set_piece'

function numOf(e: EnrichedEvent): [string, string, ModelId] | null {
  if (e.type === 'shot' && e.xg != null) return ['xG', e.xg.toFixed(2), 'xg_v1']
  if (e.type === 'pass' && e.xpass != null) return ['xPass', e.xpass.toFixed(2), 'xpass_v1']
  return null
}

/** The number's label; the hover tells which of our trained models gave it and how good it is. */
function ModelLabel({ label, id, models }: { label: string; id: ModelId; models: ModelCard[] }) {
  const t = modelText(models.find((m) => m.id === id), id)
  return (
    <span className="pointer-events-auto flex cursor-help items-center gap-1 text-[11px] text-muted-foreground" title={`${t.id} · ${t.trained} ${t.score}`.trim()}>
      {label}
    </span>
  )
}

export function EventTicker({ events, time, names, teams, models }: { events: EnrichedEvent[]; time: number; names: Names; teams: MatchMeta['teams']; models: ModelCard[] }) {
  const live = events.filter((e) => isKeyEvent(e) && e.t_s <= time && time - e.t_s < EVENT_SHOW_S).slice(-2).reverse() // newest on top
  if (!live.length) return null
  return (
    <div className="pointer-events-none absolute bottom-3 left-1/2 z-[4] flex w-[min(520px,46%)] -translate-x-1/2 flex-col gap-1.5">
      {live.map((e, j) => {
        const num = numOf(e)
        const last = j === 0
        return (
          <div key={`${e.t_s}-${e.type}`} className={cn('fade-in flex items-center gap-3 rounded-[10px] border bg-[rgba(12,23,42,.92)] px-3.5 py-2 backdrop-blur-sm', last ? 'border-primary/60' : 'border-foreground/12 opacity-70')}>
            <span className="font-mono text-[13px] font-semibold text-primary">{mmss(e.clock_s)}</span>
            <span className="flex min-w-0 flex-1 flex-col">
              <span className={cn('font-heading font-semibold leading-snug', last ? 'text-[16px]' : 'text-[13.5px]')}>{eventTitle(e, names)}</span>
              <span className="text-[12px] text-muted-foreground">{teams[e.team].name}</span>
            </span>
            {num && (
              <span className="flex flex-col items-end">
                <span className="font-heading text-[20px] font-semibold leading-none text-primary">{num[1]}</span>
                <ModelLabel label={num[0]} id={num[2]} models={models} />
              </span>
            )}
            {e.vaep && (
              <span className="flex flex-col items-end border-l border-foreground/12 pl-3">
                <span className={cn('font-heading text-[20px] font-semibold leading-none', e.vaep.total > 0 ? 'text-primary' : 'text-muted-foreground')}>{e.vaep.total > 0 ? '+' : ''}{e.vaep.total.toFixed(2)}</span>
                <ModelLabel label="VAEP" id="vaep_v1" models={models} />
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
