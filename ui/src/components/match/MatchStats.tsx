// The match stats sheet of the Stats tab, like a broadcast's: every team figure we compute, up to the video time.
import type { EnrichedEvent, MatchBundle, ModelCard, Side } from '@/api/types'
import { CREST } from '@/lib/format'
import type { TrackingFrame } from './model'
import { modelText, type ModelId } from './modelInfo'

interface Props {
  bundle: MatchBundle
  tracking: TrackingFrame[]
  time: number
  /** interpret/meta.json thresholds; sprints are left out until they load. */
  sprint: { speed: number; minS: number } | null
  models: ModelCard[]
}

const SIDES: Side[] = ['home', 'away']
type Row = [label: string, home: string, away: string, homeShare: number | null, model?: ModelId]

const pct = (a: number, b: number) => (b > 0 ? `${Math.round((100 * a) / b)}%` : '—')

function eventStats(events: EnrichedEvent[], s: Side) {
  const mine = events.filter((e) => e.team === s)
  const other = events.filter((e) => e.team !== s)
  const shots = mine.filter((e) => e.type === 'shot')
  const passes = mine.filter((e) => e.type === 'pass')
  const done = passes.filter((e) => e.outcome === 'complete')
  return {
    goals: mine.filter((e) => e.type === 'goal').length,
    shots: shots.length,
    onTarget: shots.filter((e) => e.on_target).length,
    xg: shots.reduce((a, e) => a + (e.xg ?? 0), 0),
    passes: passes.length,
    done: done.length,
    lines: done.reduce((a, e) => a + (e.lines_broken ?? 0), 0),
    xpass: passes.filter((e) => e.xpass != null).reduce((a, e, _, l) => a + (e.xpass ?? 0) / l.length, 0),
    rated: passes.filter((e) => e.xpass != null).length,
    tackles: mine.filter((e) => e.type === 'tackle').length,
    interceptions: other.filter((e) => e.type === 'pass' && e.outcome === 'intercepted').length,
    setPieces: mine.filter((e) => e.type === 'set_piece').length,
  }
}

/** Distance, top speed and sprints per team from the tracking frames up to the video time. */
function physical(frames: TrackingFrame[], sprint: Props['sprint']) {
  const team = (id: string): Side => (id.startsWith('home') ? 'home' : 'away')
  const out = { home: { dist: 0, top: 0, sprints: 0 }, away: { dist: 0, top: 0, sprints: 0 } }
  const runStart = new Map<string, number>()
  for (let k = 0; k < frames.length; k++) {
    const f = frames[k]
    const prev = k > 0 && frames[k - 1].frame_index === f.frame_index - 1 ? frames[k - 1] : null
    const before = prev ? new Map(prev.players.map((p) => [p.player_id, p])) : null
    for (const p of f.players) {
      if (p.on_pitch === false) continue
      const o = out[team(p.player_id)]
      const q = before?.get(p.player_id)
      if (q) o.dist += Math.hypot(p.x - q.x, p.y - q.y)
      const v = Math.hypot(p.vx ?? 0, p.vy ?? 0)
      o.top = Math.max(o.top, v)
      if (!sprint) continue
      // A sprint: a stretch at or above the match's sprint speed lasting at least sprint_min_s.
      const start = runStart.get(p.player_id)
      if (v >= sprint.speed && prev) { if (start === undefined) runStart.set(p.player_id, f.t_s) }
      else if (start !== undefined) {
        if ((prev ? prev.t_s : f.t_s) - start >= sprint.minS - 1e-9) o.sprints++
        runStart.delete(p.player_id)
      }
    }
  }
  return out
}

export function MatchStats({ bundle, tracking, time, sprint, models }: Props) {
  const events = bundle.events.filter((e) => e.t_s <= time)
  const ev = { home: eventStats(events, 'home'), away: eventStats(events, 'away') }

  // Possession, pressure and final-third entries from the open-play windows already played.
  let held = 0, played = 0
  const press = { home: [0, 0], away: [0, 0] }
  const entries = { home: 0, away: 0 }
  for (const w of bundle.timeline) {
    const end = Math.min(w.end_t_s, time)
    if (end <= w.start_t_s) continue
    const d = end - w.start_t_s
    if (w.home.possession_share != null) { held += w.home.possession_share * d; played += d }
    for (const s of SIDES) {
      const p = w[s].pressure
      if (p != null) { press[s][0] += p * d; press[s][1] += d }
      if (w.end_t_s <= time) entries[s] += w[s].final_third_entries
    }
  }
  const poss = played > 0 ? Math.round((100 * held) / played) : null
  const ph = physical(tracking.filter((f) => f.t_s <= time), sprint)
  const pr = (s: Side) => (press[s][1] > 0 ? press[s][0] / press[s][1] : null)

  const n = (s: Side, k: keyof typeof ev.home) => ev[s][k]
  const share = (h: number, a: number) => (h + a > 0 ? h / (h + a) : null)
  const rows: Row[] = [
    ['Goals', String(n('home', 'goals')), String(n('away', 'goals')), share(n('home', 'goals'), n('away', 'goals'))],
    ['Possession', poss == null ? '—' : `${poss}%`, poss == null ? '—' : `${100 - poss}%`, poss == null ? null : poss / 100],
    ['xG', ev.home.xg.toFixed(2), ev.away.xg.toFixed(2), share(ev.home.xg, ev.away.xg), 'xg_v1'],
    ['Shots', String(ev.home.shots), String(ev.away.shots), share(ev.home.shots, ev.away.shots)],
    ['Shots on target', String(ev.home.onTarget), String(ev.away.onTarget), share(ev.home.onTarget, ev.away.onTarget)],
    ['Passes', String(ev.home.passes), String(ev.away.passes), share(ev.home.passes, ev.away.passes)],
    ['Pass accuracy', pct(ev.home.done, ev.home.passes), pct(ev.away.done, ev.away.passes), null],
    ['Avg xPass', ev.home.rated ? ev.home.xpass.toFixed(2) : '—', ev.away.rated ? ev.away.xpass.toFixed(2) : '—', null, 'xpass_v1'],
    ['Lines broken', String(ev.home.lines), String(ev.away.lines), share(ev.home.lines, ev.away.lines)],
    ['Final-third entries', String(entries.home), String(entries.away), share(entries.home, entries.away)],
    ['Tackles won', String(ev.home.tackles), String(ev.away.tackles), share(ev.home.tackles, ev.away.tackles)],
    ['Interceptions', String(ev.home.interceptions), String(ev.away.interceptions), share(ev.home.interceptions, ev.away.interceptions)],
    ['Pressure index', pr('home')?.toFixed(2) ?? '—', pr('away')?.toFixed(2) ?? '—', null],
    ['Set pieces', String(ev.home.setPieces), String(ev.away.setPieces), share(ev.home.setPieces, ev.away.setPieces)],
    ['Distance covered', `${(ph.home.dist / 1000).toFixed(2)} km`, `${(ph.away.dist / 1000).toFixed(2)} km`, share(ph.home.dist, ph.away.dist)],
    ['Top speed', `${(ph.home.top * 3.6).toFixed(1)} km/h`, `${(ph.away.top * 3.6).toFixed(1)} km/h`, null],
    ...(sprint ? [['Sprints', String(ph.home.sprints), String(ph.away.sprints), share(ph.home.sprints, ph.away.sprints)] as Row] : []),
  ]
  const teams = bundle.meta.teams

  return (
    <div className="flex flex-col gap-1.5">
      <div className="grid grid-cols-[1fr_auto_1fr] items-center pb-1 font-heading text-[15px] font-semibold">
        <span className="flex items-center gap-2" title={teams.home.name}><img src={CREST.home} alt="" className="size-7 object-contain" />{teams.home.short}</span>
        <span className="font-mono text-[10.5px] font-medium uppercase tracking-[.06em] text-dim">Match stats</span>
        <span className="flex items-center justify-end gap-2" title={teams.away.name}>{teams.away.short}<img src={CREST.away} alt="" className="size-7 object-contain" /></span>
      </div>
      {rows.map(([label, h, a, s, model]) => (
        <div key={label} className="flex flex-col gap-1 border-t border-foreground/[.06] py-1.5">
          <div className="grid grid-cols-[64px_1fr_64px] items-baseline text-[14px] tabular-nums">
            <span className="font-semibold">{h}</span>
            {model ? (
              <span className="cursor-help text-center text-[12.5px] text-muted-foreground underline decoration-dotted underline-offset-[3px]" title={(() => { const t = modelText(models.find((m) => m.id === model), model); return `Our model ${t.id}. ${t.trained} ${t.score}`.trim() })()}>{label}</span>
            ) : <span className="text-center text-[12.5px] text-muted-foreground">{label}</span>}
            <span className="text-right font-semibold">{a}</span>
          </div>
          {s !== null && (
            <div className="flex h-1 gap-0.5 overflow-hidden rounded-full">
              {/* Each side in its club colour (as in Broadcast): a grey away bar read as an empty line at 100%. */}
              <span className="h-full rounded-full bg-[#F26B1D] transition-[width] duration-500" style={{ width: `${s * 100}%` }} />
              <span className="h-full flex-1 rounded-full bg-[#19A79E]" />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
