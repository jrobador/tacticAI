import type { MatchBundle, ModelCard, Side } from '@/api/types'
import { mmss, nameOf, type Names } from '@/lib/format'
import { cn } from '@/lib/utils'
import { modelText, MODEL_NOTE, type ModelId } from './modelInfo'
import { windowAt, type Det, type TrackingFrame } from './model'
import { MatchStats } from './MatchStats'
import { Term } from './Term'

/** Everything the Stats tab needs; the page fills it in and keeps it current with the video. */
export interface StatsTabProps {
  bundle: MatchBundle
  /** tracking.jsonl (empty until it loads, and in mock mode). */
  tracking: TrackingFrame[]
  /** Video time in seconds. */
  time: number
  /** Player focus (a player_id) or null. */
  focusId: string | null
  names: Names
  models: ModelCard[]
  /** The shot, pass or player whose breakdown is open. */
  det: Det | null
  onDet: (d: Det | null) => void
  /** Sprint threshold of the match (interpret/meta.json), null until it loads. */
  sprint: { speed: number; minS: number } | null
  onSeek: (t: number) => void
}

const INK = '#F0F0F0'
const SLATE = '#6B7A94'
const sgn = (v: number, d: number) => `${v < 0 ? '−' : '+'}${Math.abs(v).toFixed(d)}`
const head = 'font-mono text-[10.5px] font-medium uppercase tracking-[.06em] text-dim'
const monoNote = 'font-mono text-[11px] font-medium text-dim'

/** Last frame at or before t (tracking is sorted by time). */
export function frameAt(frames: TrackingFrame[], t: number): TrackingFrame | undefined {
  let lo = 0
  let hi = frames.length - 1
  let best = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (frames[mid].t_s <= t) { best = mid; lo = mid + 1 } else hi = mid - 1
  }
  return frames[best]
}

function Radar({ bundle, tracking, time, focusId, names }: Pick<StatsTabProps, 'bundle' | 'tracking' | 'time' | 'focusId' | 'names'>) {
  const { pitch, teams } = bundle.meta
  const f = frameAt(tracking, time)
  // Home attacks +x (right); the home left back sits at negative y, so y grows downwards on the radar.
  const pos = (x: number, y: number) => ({ left: `${((x + pitch.length_m / 2) / pitch.length_m) * 100}%`, top: `${((y + pitch.width_m / 2) / pitch.width_m) * 100}%` })
  const line = 'absolute border-[1.5px] border-foreground/30'
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-semibold">Radar</span>
        <span className={monoNote}>10 fps{f ? ` · frame ${f.frame_index}` : ''}</span>
      </div>
      <div className="relative aspect-[105/68] w-full overflow-hidden rounded-lg border-[1.5px] border-foreground/30 bg-[#0f1b2f]">
        <span className="absolute inset-y-0 left-1/2 w-[1.5px] bg-foreground/30" />
        <span className={cn(line, 'left-1/2 top-1/2 aspect-square w-[17.4%] -translate-x-1/2 -translate-y-1/2 rounded-full')} />
        <span className={cn(line, 'left-0 top-[20.4%] h-[59.2%] w-[15.7%] border-l-0')} />
        <span className={cn(line, 'right-0 top-[20.4%] h-[59.2%] w-[15.7%] border-r-0')} />
        {f?.players.filter((p) => p.on_pitch !== false).map((p) => {
          const home = p.player_id.startsWith('home')
          const focus = p.player_id === focusId
          const sz = focus ? 18 : 14
          return (
            <span
              key={p.player_id} title={nameOf(names, p.player_id)}
              className="absolute grid place-items-center rounded-full border-[1.5px] text-[7px] font-bold leading-none transition-[left,top] duration-100 ease-linear"
              style={{ ...pos(p.x, p.y), width: sz, height: sz, margin: -sz / 2, background: home ? INK : '#0C172A', color: home ? '#0C172A' : INK, borderColor: focus ? '#C6F432' : INK }}
            >{names[p.player_id]?.number}</span>
          )
        })}
        {f && <span className="absolute size-2 rounded-full bg-primary shadow-[0_0_0_3px_rgba(198,244,50,.25)] transition-[left,top] duration-100 ease-linear" style={{ ...pos(f.ball.x, f.ball.y), margin: -4 }} />}
      </div>
      <span className="text-[11px] text-dim">
        {f ? `Filled: ${teams.home.name}, attacking right · Outline: ${teams.away.name}, attacking left · Lime: ball` : 'The tracking file is not loaded.'}
      </span>
    </div>
  )
}


function Momentum({ bundle, time }: { bundle: MatchBundle; time: number }) {
  const w = bundle.timeline
  if (!w.length) return null
  // Windows are equal parts of open-play time, so the playhead moves inside the window that holds the video time.
  const idx = windowAt(w, time)
  const end = w[idx + 1]?.start_t_s ?? w[idx].end_t_s
  const frac = Math.min(1, Math.max(0, (time - w[idx].start_t_s) / Math.max(0.001, end - w[idx].start_t_s)))
  const { home, away } = bundle.meta.teams
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-semibold"><Term k="momentum">Momentum</Term></span>
        <span className={monoNote}>{w.length} windows</span>
      </div>
      <div className="relative grid h-14 gap-0.5" style={{ gridTemplateColumns: `repeat(${w.length}, minmax(0, 1fr))` }}>
        <span className="absolute inset-x-0 top-1/2 h-px bg-foreground/20" />
        {w.map((x, i) => (
          <span key={x.window} className="relative h-full" title={`Window ${i + 1}: ${sgn(x.momentum, 2)}`}>
            <span
              className="absolute inset-x-0 rounded-[1px]"
              style={{ top: x.momentum >= 0 ? `${50 - x.momentum * 50}%` : '50%', height: `${Math.abs(x.momentum) * 50}%`, background: x.momentum >= 0 ? INK : SLATE, opacity: i === idx ? 1 : 0.6 }}
            />
          </span>
        ))}
        <span className="absolute -inset-y-[3px] -ml-px w-0.5 bg-primary" style={{ left: `${((idx + frac) / w.length) * 100}%` }} />
      </div>
      <span className="text-[11px] leading-normal text-dim">Up: {home.name} · Down: {away.name}. A strip only: momentum shift moments are switched off until they are checked against video.</span>
    </div>
  )
}



const ITEM: Record<string, string> = { pass: 'passes', shot: 'shots', tackle: 'tackles', interception: 'interceptions' }

/** Seconds a player's row stays lit after one of his actions adds VAEP. */
const VAEP_FLASH_S = 2

function Players({ bundle, time, onDet }: { bundle: MatchBundle; time: number; onDet: StatsTabProps['onDet'] }) {
  // VAEP so far: the sum of each rated action up to the video time. At the end of the clip it equals players.json.
  const sofar = new Map<string, number>()
  const lastAt = new Map<string, number>()
  for (const e of bundle.events) {
    if (e.t_s > time || !e.vaep || !e.player_id) continue
    sofar.set(e.player_id, (sofar.get(e.player_id) ?? 0) + e.vaep.total)
    lastAt.set(e.player_id, e.t_s)
  }
  const rated = bundle.players.filter((p) => p.rating.value !== null && p.rating.breakdown.length > 0)
    .map((p) => ({ ...p, now: sofar.get(p.player_id) ?? 0 }))
    .sort((a, b) => b.now - a.now)
  const maxAbs = Math.max(0.001, ...rated.map((p) => Math.abs(p.rating.value ?? 0)))
  return (
    <div className="flex flex-col">
      <div className="flex items-baseline justify-between pb-1">
        <span className="text-sm font-semibold"><Term k="vaep">VAEP (goals added)</Term></span>
      </div>
      {rated.length === 0 && <span className="py-2 text-[12.5px] text-dim">No player has a rated action in this clip.</span>}
      {rated.map((p) => {
        const r = bundle.roster.players.find((x) => x.player_id === p.player_id)
        const v = p.now
        const lit = time - (lastAt.get(p.player_id) ?? -99) < VAEP_FLASH_S
        return (
          <button
            key={p.player_id} type="button" onClick={() => onDet({ kind: 'player', id: p.player_id })}
            className={cn('grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_58px] items-center gap-2.5 rounded-md border-t border-foreground/[.06] px-1 py-2 text-left transition-colors duration-500 hover:bg-[#16223a]', lit && 'bg-primary/15')}
          >
            <span className="flex min-w-0 flex-col gap-px">
              <span className="text-[13px] font-semibold">{r?.name ?? p.player_id}</span>
              <span className="text-[10.5px] text-dim">{bundle.meta.teams[p.team].short}{r ? ` · #${r.number} · ${r.role}` : ''}</span>
            </span>
            <span className="h-[5px] overflow-hidden rounded-[3px] bg-[#1f2b40]"><span className="block h-full transition-[width] duration-500" style={{ width: `${(Math.abs(v) / maxAbs) * 100}%`, background: v > 0 ? '#C6F432' : '#7D838D' }} /></span>
            <span className={cn('text-right font-heading text-sm font-semibold', v > 0 ? 'text-primary' : 'text-muted-foreground')}>{sgn(v, 3)}</span>
          </button>
        )
      })}
    </div>
  )
}

interface DetView { kicker: string; title: string; val: string; unit: string; concept: 'xg' | 'xpass' | 'vaep'; model: ModelId; rows: { l: string; v: string; u: string }[] }

function detView(d: Det, b: MatchBundle, names: Names): DetView | null {
  const sh = (s: Side) => b.meta.teams[s].short
  if (d.kind === 'player') {
    const p = b.players.find((x) => x.player_id === d.id)
    const r = b.roster.players.find((x) => x.player_id === d.id)
    if (!p || !r || p.rating.value === null) return null
    return {
      kicker: `Player · ${sh(r.team)} #${r.number} · ${r.role}`, title: r.name, val: sgn(p.rating.value, 3), unit: 'VAEP (goals added)', concept: 'vaep', model: 'vaep_v1',
      rows: p.rating.breakdown.map((x) => ({ l: `From ${ITEM[x.item] ?? x.item} (${x.count})`, v: sgn(x.points, 3), u: `offence ${sgn(x.offensive, 3)} · defence ${sgn(x.defensive, 3)}` })),
    }
  }
  const e = b.events[d.i]
  if (!e) return null
  if (d.kind === 'shot') {
    return {
      kicker: `Shot · ${mmss(e.clock_s)}`, title: `${nameOf(names, e.player_id)}, ${e.outcome === 'goal' ? 'scored' : 'no goal'}`, val: (e.xg ?? 0).toFixed(3), unit: 'xG', concept: 'xg', model: 'xg_v1',
      rows: [
        { l: 'Distance to goal', v: e.dist_goal_center_m?.toFixed(1) ?? '—', u: 'm' },
        { l: 'Visible angle', v: e.visible_goal_angle_deg?.toFixed(1) ?? '—', u: '°' },
        { l: 'Defenders in the cone', v: e.defenders_in_cone?.toString() ?? '—', u: '' },
      ],
    }
  }
  return {
    kicker: `Pass · ${mmss(e.clock_s)}`, title: `${nameOf(names, e.player_id)} → ${nameOf(names, e.to_player_id)}, ${e.outcome ?? ''}`, val: (e.xpass ?? 0).toFixed(2), unit: 'xPass', concept: 'xpass', model: 'xpass_v1',
    rows: [
      { l: 'Pass length', v: e.length_m?.toFixed(1) ?? '—', u: 'm' },
      { l: 'Forward gain', v: e.progressive_m?.toFixed(1) ?? '—', u: 'm' },
      { l: 'Pressure on the passer', v: e.pressure == null ? '—' : e.pressure.toFixed(2), u: 'pressure index' },
      { l: 'Lines broken', v: e.lines_broken?.toString() ?? '—', u: '' },
    ],
  }
}

function Detail({ view, models, onBack }: { view: DetView; models: ModelCard[]; onBack: () => void }) {
  const m = modelText(models.find((c) => c.id === view.model), view.model)
  return (
    <div className="flex flex-col gap-3.5">
      <button type="button" onClick={onBack} className="self-start rounded-[7px] border border-foreground/20 px-2.5 py-1.5 text-xs font-semibold hover:border-primary hover:text-primary">← All stats</button>
      <div className="flex flex-col gap-1">
        <span className="font-mono text-[11px] font-semibold uppercase tracking-[.05em] text-primary">{view.kicker}</span>
        <span className="font-heading text-lg font-semibold">{view.title}</span>
      </div>
      <div className="flex items-baseline gap-2.5">
        <span className="font-heading text-[42px] font-semibold leading-none tracking-[-.03em] text-primary">{view.val}</span>
        <Term k={view.concept} className="text-[13px] font-medium text-foreground">{view.unit}</Term>
      </div>
      <div className="flex flex-col">
        <span className={cn(head, 'pb-1.5')}>Breakdown</span>
        {view.rows.map((r) => (
          <div key={r.l} className="flex justify-between gap-3 border-t border-foreground/10 py-2">
            <span className="text-[13px] font-medium text-muted-foreground">{r.l}</span>
            <span className="text-right font-heading text-[15px] font-semibold">{r.v} <span className="font-sans text-[11px] font-medium text-dim">{r.u}</span></span>
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-[9px] rounded-xl border border-foreground/15 bg-[#0f192b] p-3.5">
        <div className="flex items-baseline justify-between"><span className="text-sm font-semibold">Model card · {m.name}</span><span className="font-mono text-[11.5px] text-muted-foreground">{m.id}</span></div>
        <span className="text-[13px] leading-normal">{m.what}</span>
        {(m.trained || m.score) && <span className="text-[13px] leading-normal text-muted-foreground">{m.trained} {m.score}</span>}
        <div className="flex flex-wrap gap-[5px]">
          {m.inputs.map((x) => <span key={x} className="rounded-md border border-foreground/15 px-[7px] py-[3px] text-[11.5px] font-medium text-muted-foreground">{x}</span>)}
        </div>
        <div className="grid grid-cols-[18px_minmax(0,1fr)] items-start gap-2 border-t border-foreground/10 pt-[9px]">
          <span className="text-[11px] font-bold leading-normal">▲</span>
          <span className="text-xs leading-normal text-muted-foreground"><strong className="font-semibold text-foreground">Note</strong> {MODEL_NOTE}</span>
        </div>
      </div>
    </div>
  )
}

export function StatsTab(p: StatsTabProps) {
  const view = p.det ? detView(p.det, p.bundle, p.names) : null
  if (view) return <Detail view={view} models={p.models} onBack={() => p.onDet(null)} />
  return (
    <div className="flex flex-col gap-3.5">
      <MatchStats bundle={p.bundle} tracking={p.tracking} time={p.time} sprint={p.sprint} models={p.models} />
      <Radar {...p} />
      <Momentum bundle={p.bundle} time={p.time} />
      <Players bundle={p.bundle} time={p.time} onDet={p.onDet} />
    </div>
  )
}
