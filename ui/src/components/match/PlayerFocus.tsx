// Favourite player mode: a live card on the video that follows one player the whole match, from the tracking and the events.
// Every line is computed by code at the video time (an LLM cannot answer ten times a second).
import type { EnrichedEvent, RosterPlayer, Side } from '@/api/types'
import { CREST, eventTitle, type Names } from '@/lib/format'
import type { TrackingFrame } from './model'

interface Props {
  playerId: string
  roster: RosterPlayer[]
  tracking: TrackingFrame[]
  events: EnrichedEvent[]
  time: number
  names: Names
  es?: boolean
  /** The match's sprint speed (interpret/meta.json); null until it loads. */
  sprint: { speed: number; minS: number } | null
}

/** Pitch half-length used for the thirds: the keepers stand at x = ±55 in the tracking. */
const THIRD_X = 17.5
/** Seconds a milestone or an action of the player stays on the card. */
const FLASH_S = 3
/** Distance milestones, in metres. */
const MILESTONE_M = 250

interface Run { dist: number; top: number; sprints: number; distAt: number[]; topAt: number }

/** Distance, top speed and sprints of one player up to `time`, plus when each milestone and the latest top speed happened. */
function runOf(id: string, frames: TrackingFrame[], time: number, sprint: Props['sprint']): Run {
  const r: Run = { dist: 0, top: 0, sprints: 0, distAt: [], topAt: -1 }
  let prev: { x: number; y: number; f: number } | null = null
  let runStart: number | null = null
  let lastT = 0
  for (const f of frames) {
    if (f.t_s > time) break
    const p = f.players.find((q) => q.player_id === id)
    if (!p || p.on_pitch === false) { prev = null; continue }
    if (prev && prev.f === f.frame_index - 1) {
      const before = Math.floor(r.dist / MILESTONE_M)
      r.dist += Math.hypot(p.x - prev.x, p.y - prev.y)
      if (Math.floor(r.dist / MILESTONE_M) > before) r.distAt.push(f.t_s)
    }
    const v = Math.hypot(p.vx ?? 0, p.vy ?? 0)
    if (v > r.top + 0.05) { r.top = v; r.topAt = f.t_s }
    if (sprint) {
      if (v >= sprint.speed) { if (runStart === null) runStart = f.t_s }
      else if (runStart !== null) { if (lastT - runStart >= sprint.minS - 1e-9) r.sprints++; runStart = null }
    }
    prev = { x: p.x, y: p.y, f: f.frame_index }
    lastT = f.t_s
  }
  return r
}

/** What the player is doing right now, in plain words, from his speed, where he is and where he is heading. */
function statusOf(p: { x: number; vx?: number; vy?: number }, side: Side, sprint: Props['sprint'], es: boolean): { doing: string; where: string } {
  const v = Math.hypot(p.vx ?? 0, p.vy ?? 0)
  const thr = sprint?.speed ?? 7
  // ponytail: running/jogging cut at fixed fractions of the match's sprint speed; tune if the labels feel off on video
  const doing = es ? (v >= thr ? 'Sprintando' : v >= 0.55 * thr ? 'Corriendo' : v >= 0.2 * thr ? 'Trotando' : 'Quieto en su puesto')
    : v >= thr ? 'Sprinting' : v >= 0.55 * thr ? 'Running' : v >= 0.2 * thr ? 'Jogging' : 'Holding his position'
  const dir = side === 'home' ? 1 : -1 // home attacks +x
  const ax = p.x * dir
  const forward = (p.vx ?? 0) * dir
  const where = es ? (ax > THIRD_X ? 'en el último tercio' : ax < -THIRD_X ? 'en su propio tercio' : 'en el medio')
    : ax > THIRD_X ? 'in the final third' : ax < -THIRD_X ? 'in his own third' : 'in midfield'
  const move = v < 0.2 * thr ? '' : es ? (forward > 1.5 ? 'subiendo ' : forward < -1.5 ? 'retrocediendo ' : 'cruzando ')
    : forward > 1.5 ? 'pushing forward ' : forward < -1.5 ? 'dropping back ' : 'moving across '
  return { doing, where: `${move}${where}` }
}

export function PlayerFocus({ playerId, roster, tracking, events, time, names, sprint, es = false }: Props) {
  const me = roster.find((r) => r.player_id === playerId)
  if (!me) return null
  const frame = tracking.filter((f) => f.t_s <= time).at(-1)
  const now = frame?.players.find((p) => p.player_id === playerId)
  const run = runOf(playerId, tracking, time, sprint)
  const status = now ? statusOf(now, me.team, sprint, es) : null

  // The team's top distance so far, to tell when he is the one who has run the most.
  const mates = roster.filter((r) => r.team === me.team && r.role !== 'GK' && r.player_id !== playerId)
  const most = run.dist > 0 && mates.every((m) => runOf(m.player_id, tracking, time, null).dist <= run.dist)

  // The newest thing worth a flash: an action of his, a distance milestone or a new top speed, within FLASH_S.
  const action = events.filter((e) => e.t_s <= time && time - e.t_s < FLASH_S && (e.player_id === playerId || e.to_player_id === playerId || e.intercepted_by === playerId)).at(-1)
  const milestone = run.distAt.filter((t) => time - t < FLASH_S).at(-1)
  const topNew = run.topAt > 1 && time - run.topAt < FLASH_S && run.top >= (sprint?.speed ?? 7)
  const flash = action ? eventTitle(action, names, es)
    : milestone !== undefined ? `${Math.floor(run.dist / MILESTONE_M) * MILESTONE_M} m ${es ? 'recorridos' : 'covered'}`
      : topNew ? `${es ? 'Nueva velocidad máxima' : 'New top speed'}: ${(run.top * 3.6).toFixed(1)} km/h` : null

  return (
    <div className="pointer-events-none absolute right-3 top-3 z-[4] flex w-[min(300px,34%)] flex-col gap-2 rounded-xl border border-primary/50 bg-[rgba(12,23,42,.92)] px-3.5 py-3 backdrop-blur-sm">
      <div className="flex items-center gap-2.5">
        <img src={`/players/${me.player_id}.png`} alt="" className="size-11 flex-none rounded-md object-cover object-top" />
        <span className="flex min-w-0 flex-col">
          <span className="flex items-center gap-1.5 truncate font-heading text-[16px] font-semibold leading-tight"><img src={CREST[me.team]} alt="" className="size-4 flex-none object-contain" />{me.name}</span>
          <span className="font-mono text-[10.5px] uppercase tracking-[.06em] text-dim">#{me.number} · {me.role} · {es ? 'tu jugador' : 'your player'}</span>
        </span>
      </div>
      {status ? (
        <span className="text-[15px] font-semibold leading-snug"><span className="text-primary">{status.doing}</span> <span className="text-foreground">{status.where}</span></span>
      ) : <span className="text-[13px] text-muted-foreground">{es ? 'No está en la cancha ahora.' : 'Not on the pitch right now.'}</span>}
      {flash && <span key={flash} className="fade-in rounded-md bg-primary/15 px-2 py-1 text-[13px] font-semibold text-primary">{flash}</span>}
      <div className="grid grid-cols-3 gap-2 border-t border-foreground/10 pt-2 text-center tabular-nums">
        <span className="flex flex-col"><span className="font-heading text-[16px] font-semibold">{run.dist >= 1000 ? `${(run.dist / 1000).toFixed(2)} km` : `${Math.round(run.dist)} m`}</span><span className="text-[10.5px] text-muted-foreground">{es ? 'recorrido' : 'covered'}</span></span>
        <span className="flex flex-col"><span className="font-heading text-[16px] font-semibold">{(run.top * 3.6).toFixed(1)}</span><span className="text-[10.5px] text-muted-foreground">{es ? 'km/h máx.' : 'top km/h'}</span></span>
        <span className="flex flex-col"><span className="font-heading text-[16px] font-semibold">{sprint ? run.sprints : '—'}</span><span className="text-[10.5px] text-muted-foreground">sprints</span></span>
      </div>
      {most && <span className="text-[12px] text-muted-foreground">{es ? 'El que más corrió de su equipo hasta ahora.' : 'Most distance in his team so far.'}</span>}
    </div>
  )
}
