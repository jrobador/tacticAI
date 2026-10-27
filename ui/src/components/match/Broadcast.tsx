// Broadcast mode: the lower-third graphics that go on air over the video by themselves (render/broadcast/rundown.json), the "On air" bar,
// the Studio teleprompter, the 9:16 Reels and the full-time overlay.
import { ChevronLeft, ChevronRight, Download, Film, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { matchFileUrl } from '@/api/client'
import type { Lang, MatchMeta, ReelManifest, Side } from '@/api/types'
import { CREST, minute, mmss, nameOf, type Names } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { BroadcastGraphic, FanView, Rundown, StudioScript } from './data'
import { Countdown } from './Stage'

type Teams = MatchMeta['teams']
type Kind = BroadcastGraphic['type']

/** Which graphic wins when two overlap, and what each is called. */
const PR: Record<Kind, number> = { goal: 6, shot: 5, pass_quality: 4, carry: 3, milestone: 2, player_id: 1 }
const KIND: Record<Kind, [string, string]> = { shot: ['Shot', 'Disparo'], goal: ['Goal', 'Gol'], pass_quality: ['Pass quality', 'Calidad del pase'], carry: ['Carry', 'Conducción'], player_id: ['Player', 'Jugador'], milestone: ['Milestone', 'Hito'] }
const STRIPE: Record<Side, string> = { home: 'linear-gradient(180deg,#F26B1D 0 100%)', away: 'linear-gradient(180deg,#19A79E 0 60%,#0A0F12 60% 100%)' }
const EASE = 'cubic-bezier(.2,.7,.2,1)'
const EASE_OUT = 'cubic-bezier(.4,0,1,1)'
const font = (w: number, cqw: number, fam: 'mono' | 'sans' | 'heading', lh = 1): CSSProperties => ({ fontWeight: w, fontSize: `${cqw}cqw`, lineHeight: lh, fontFamily: `var(--font-${fam})` })

/** A graphic as it airs: from `start` until `end`, which is earlier than its t_out when a more important one cuts it. */
export interface Air { g: BroadcastGraphic; start: number; end: number; cutBy?: BroadcastGraphic }

/** The rundown in air order: a later graphic that starts while another is on air cuts it if it matters more, else it is skipped. */
export function schedule(rd: Rundown | null): Air[] {
  const out: Air[] = []
  let cur: Air | null = null
  for (const g of [...(rd?.graphics ?? [])].sort((a, b) => a.t_in - b.t_in)) {
    if (cur && g.t_in < cur.end) {
      if (PR[g.type] <= PR[cur.g.type]) continue
      cur.end = g.t_in
      cur.cutBy = g
    }
    cur = { g, start: g.t_in, end: g.t_out }
    out.push(cur)
  }
  return out
}
export const airAt = (s: Air[], t: number) => s.find((a) => t >= a.start && t < a.end) ?? null
export const airNext = (s: Air[], t: number) => s.find((a) => a.start > t) ?? null

const gName = (g: BroadcastGraphic, names: Names) =>
  g.type === 'pass_quality' ? `${nameOf(names, g.player_id)} → ${nameOf(names, g.data.to_player_id as string)}` : nameOf(names, g.player_id)

const ord = (n: number, es: boolean, fem: boolean) => {
  if (es) return `${n}.${fem ? 'ª' : 'º'}`
  return `${n}${n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th'}`
}
const EVENT: Record<string, [string, string]> = { shot: ['shot', 'disparo'], tackle: ['tackle', 'recuperación'], pass: ['pass', 'pase'] }

interface View {
  goal: boolean; team: Side; kicker: string; name: string; score: string
  cells: { v: string; u: string; l: string }[]
  status: { text: string; on: boolean } | null
  mile: { text: string; pips: number } | null
  foot: { text: string; pct: number } | null
}

/** What a graphic shows, in the language (decimal comma in Spanish). */
function view(g: BroadcastGraphic, es: boolean, names: Names, teams: Teams): View {
  const L = es ? 1 : 0
  const d = g.data as Record<string, number | boolean | string | null | Record<string, number>>
  const num = (v: unknown) => (es ? String(v).replace('.', ',') : String(v))
  const cells: View['cells'] = []
  const add = (k: string, u: string, en: string, sp: string) => { if (d[k] != null) cells.push({ v: num(d[k]), u, l: es ? sp : en }) }
  const v: View = { goal: g.type === 'goal', team: g.team, kicker: KIND[g.type][L], name: gName(g, names), score: '', cells, status: null, mile: null, foot: null }
  if (g.type === 'goal') {
    const s = d.score as Record<Side, number>
    v.kicker += ` · ${teams[g.team].name}`
    v.score = `${s.home}–${s.away}`
  }
  if (g.type === 'goal' || g.type === 'shot') { add('ball_kmh', 'km/h', 'Ball speed', 'Velocidad'); add('distance_m', 'm', 'Distance', 'Distancia') }
  if (g.type === 'shot') {
    add('xg', '', 'xG', 'xG')
    v.status = { on: !!d.on_target, text: d.on_target ? (es ? 'A puerta' : 'On target') : es ? 'Fuera' : 'Off target' }
  }
  if (g.type === 'pass_quality') {
    add('length_m', 'm', 'Length', 'Longitud')
    add('lines_broken', '', (d.lines_broken as number) > 1 ? 'Lines broken' : 'Line broken', (d.lines_broken as number) > 1 ? 'Líneas superadas' : 'Línea superada')
    add('completion_pct', '%', 'Completion chance', 'Prob. de acierto')
    if (d.harder_than_pct != null) {
      const p = d.harder_than_pct as number
      v.foot = { pct: p, text: es ? `Más difícil que el ${p} % de los pases del partido` : `Harder than ${p} % of the match's passes` }
    }
  }
  if (g.type === 'carry') { add('distance_m', 'm', 'With the ball', 'Con balón'); add('duration_s', 's', 'Time', 'Tiempo') }
  if (g.type === 'player_id') { add('top_kmh', 'km/h', 'Top speed', 'Velocidad máx.'); add('distance_m', 'm', 'Covered', 'Recorridos') }
  if (g.type === 'milestone') {
    const n = d.count as number
    const ev = EVENT[d.event as string] ?? [String(d.event), String(d.event)]
    v.mile = { text: `${ord(n, es, d.event === 'tackle')} ${ev[L]}`, pips: Math.min(n, 10) }
  }
  return v
}

const REEL_GEN_MS = 3000

interface Stage { air: Air | null; st: number; sec: number }

/** The animation stages of the graphic on air (0 out, 1 cell, 2 plate, 3 data and hold, 4 data out, 5 plate out): IN 520 ms, OUT 420 ms.
 *  When another graphic takes over, the current one exits first and the next enters 40 ms after. */
function useStages(air: Air | null, time: number): Stage {
  const [s, setS] = useState<Stage>({ air: null, st: 0, sec: 5 })
  const cur = useRef(s)
  const timeRef = useRef(time)
  useEffect(() => { timeRef.current = time })
  useEffect(() => {
    const timers: number[] = []
    const at = (ms: number, fn: () => void) => { timers.push(window.setTimeout(fn, ms)) }
    const put = (p: Partial<Stage>) => { cur.current = { ...cur.current, ...p }; setS(cur.current) }
    let t = 0
    if (cur.current.air && cur.current.st > 0) {
      at(0, () => put({ st: 4 })); at(200, () => put({ st: 5 })); at(420, () => put({ st: 0 }))
      t = 520
    }
    if (air) {
      at(t, () => put({ air, st: 0, sec: Math.max(0.1, air.end - timeRef.current) }))
      at(t + 40, () => put({ st: 1 })); at(t + 180, () => put({ st: 2 })); at(t + 400, () => put({ st: 3 }))
    } else at(t, () => put({ air: null, st: 0 }))
    return () => timers.forEach(window.clearTimeout)
  }, [air])
  return s
}

/** The lower-third over the video, sized in container units so it scales with any output: bottom left, never wider than 37 % of the frame. */
export function FeedLayer({ air, time, lang, names, teams }: { air: Air | null; time: number; lang: Lang; names: Names; teams: Teams }) {
  const { air: shown, st, sec } = useStages(air, time)
  const v = useMemo(() => (shown ? view(shown.g, lang === 'es', names, teams) : null), [shown, lang, names, teams])
  return (
    <div className="pointer-events-none absolute inset-0 z-[4]" style={{ containerType: 'inline-size' }} aria-hidden={!v}>
      {shown && v && <Lower v={v} playerId={shown.g.player_id} st={st} sec={sec} teams={teams} />}
    </div>
  )
}

function Lower({ v, playerId, st, sec, teams }: { v: View; playerId: string | null; st: number; sec: number; teams: Teams }) {
  const out = st >= 4
  const plateIn = st >= 2 && st <= 4
  const dataIn = st === 3
  const r1h = v.goal ? 5.4 : 4.6
  const cellAnim = (i: number): CSSProperties => ({
    opacity: dataIn ? 1 : 0, transform: dataIn ? 'none' : 'translateY(.8cqw)',
    transition: out ? `opacity 160ms ${EASE_OUT}, transform 180ms ${EASE_OUT}` : `opacity 260ms ease ${i * 60}ms, transform 340ms ${EASE} ${i * 60}ms`,
  })
  const last = cellAnim(v.cells.length + (v.goal ? 1 : 0))
  const cellBox: CSSProperties = { display: 'flex', borderRight: '1px solid rgba(240,240,240,.1)' }
  return (
    <div style={{ position: 'absolute', left: '2.6cqw', bottom: '3.2cqw', display: 'flex', flexDirection: 'column', maxWidth: '37cqw', width: 'max-content' }}>
      <div style={{ display: 'flex', height: `${r1h}cqw` }}>
        <div style={{ position: 'relative', width: `${r1h}cqw`, flex: 'none', background: '#081120', overflow: 'hidden', transform: `scaleY(${st >= 1 ? 1 : 0})`, transformOrigin: 'bottom', transition: `transform ${out ? `180ms ${EASE_OUT}` : `220ms ${EASE}`}` }}>
          {playerId && <img src={`/players/${playerId}.png`} alt="" className="absolute inset-0 size-full object-cover" style={{ objectPosition: 'top' }} onError={(e) => { e.currentTarget.style.display = 'none' }} />}
          <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '.5cqw', background: STRIPE[v.team] }} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', padding: '0 1.6cqw 0 1.3cqw', background: 'rgba(12,23,42,.96)', clipPath: plateIn ? 'inset(0 0 0 0)' : 'inset(0 100% 0 0)', transition: `clip-path ${out ? `220ms ${EASE_OUT}` : `380ms ${EASE}`}` }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '.35cqw', minWidth: 0 }}>
            <span style={{ ...font(700, 0.9, 'mono'), letterSpacing: '.16em', textTransform: 'uppercase', color: '#C6F432', whiteSpace: 'nowrap' }}>{v.kicker}</span>
            <span style={{ ...font(700, v.goal ? 2.6 : 1.95, 'heading'), letterSpacing: '.01em', textTransform: 'uppercase', color: '#F0F0F0', whiteSpace: 'nowrap' }}>{v.name}</span>
          </div>
        </div>
      </div>
      <div style={{ height: '.22cqw', background: '#C6F432', transform: `scaleX(${plateIn ? 1 : 0})`, transformOrigin: 'left', transition: `transform ${out ? `200ms ${EASE_OUT}` : `480ms ${EASE} 60ms`}` }} />
      <div style={{ display: 'flex', alignSelf: 'flex-start', marginLeft: `${r1h}cqw`, maxWidth: `calc(37cqw - ${r1h}cqw)`, overflow: 'hidden', background: 'rgba(20,34,58,.97)', opacity: plateIn ? 1 : 0, transition: `opacity ${out ? 160 : 200}ms` }}>
        {v.goal && (
          <div style={{ ...cellBox, alignItems: 'center', gap: '.7cqw', padding: '0 1.05cqw 0 1cqw', ...cellAnim(0) }}>
            <span style={{ ...font(700, 1.15, 'heading'), color: '#F0F0F0' }}>{teams.home.short}</span>
            <span style={{ ...font(700, 1.9, 'mono'), color: '#C6F432', whiteSpace: 'nowrap' }}>{v.score}</span>
            <span style={{ ...font(700, 1.15, 'heading'), color: '#F0F0F0' }}>{teams.away.short}</span>
          </div>
        )}
        {v.cells.map((c, i) => (
          <div key={c.l} style={{ ...cellBox, flexDirection: 'column', gap: '.3cqw', padding: '.7cqw 1.05cqw .75cqw 1cqw', ...cellAnim(v.goal ? i + 1 : i) }}>
            <span style={{ display: 'flex', alignItems: 'baseline', gap: '.35cqw', whiteSpace: 'nowrap' }}>
              <span style={{ ...font(600, 1.65, 'mono'), color: '#F0F0F0' }}>{c.v}</span>
              <span style={{ ...font(500, 0.95, 'mono'), color: '#A3A8B0' }}>{c.u}</span>
            </span>
            <span style={{ ...font(600, 0.72, 'sans'), letterSpacing: '.08em', textTransform: 'uppercase', color: '#A3A8B0', whiteSpace: 'nowrap' }}>{c.l}</span>
          </div>
        ))}
        {v.status && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '.5cqw', padding: '0 1cqw', ...last }}>
            <span style={{ width: '.9cqw', height: '.9cqw', borderRadius: '50%', boxSizing: 'border-box', border: `.2cqw solid ${v.status.on ? '#C6F432' : '#A3A8B0'}`, background: v.status.on ? '#C6F432' : 'transparent' }} />
            <span style={{ ...font(700, 0.95, 'mono'), letterSpacing: '.1em', textTransform: 'uppercase', color: v.status.on ? '#C6F432' : '#A3A8B0', whiteSpace: 'nowrap' }}>{v.status.text}</span>
          </div>
        )}
        {v.mile && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '1cqw', padding: '.85cqw 1.4cqw', ...last }}>
            <span style={{ ...font(700, 1.65, 'heading'), color: '#F0F0F0', whiteSpace: 'nowrap' }}>{v.mile.text}</span>
            <span style={{ display: 'flex', gap: '.35cqw' }}>{Array.from({ length: v.mile.pips }, (_, i) => <span key={i} style={{ width: '.8cqw', height: '.8cqw', background: '#C6F432' }} />)}</span>
          </div>
        )}
      </div>
      {v.foot && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '1cqw', alignSelf: 'flex-start', marginLeft: `${r1h}cqw`, maxWidth: `calc(37cqw - ${r1h}cqw)`, boxSizing: 'border-box', background: '#C6F432', padding: '.55cqw 1.1cqw', ...last }}>
          <span style={{ position: 'relative', width: '5cqw', height: '.5cqw', background: 'rgba(12,23,42,.25)', flex: 'none' }}>
            <span style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${v.foot.pct}%`, background: '#0C172A' }} />
          </span>
          <span style={{ ...font(600, 0.95, 'sans', 1.25), color: '#0C172A', textWrap: 'pretty' }}>{v.foot.text}</span>
        </div>
      )}
      <div style={{ height: '.18cqw', marginLeft: `${r1h}cqw`, background: 'rgba(198,244,50,.75)', width: dataIn ? `calc(100% - ${r1h}cqw)` : '0%', transition: dataIn ? `width ${sec}s linear` : 'none' }} />
    </div>
  )
}

// goal takeover
/** Full-screen goal over the frozen frame (3 s): dim, lime wipe, the scorer's face and GOAL, the score flipping and the data rail, wipe out. */
export function GoalTakeover({ g, lang, names, teams }: { g: BroadcastGraphic; lang: Lang; names: Names; teams: Teams }) {
  const es = lang === 'es'
  const rm = useMemo(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches, [])
  // 1 dim (20 ms) · 2 wipe (250) · 3 face and GOAL (600) · 4 score and rail (1200) · 5 digit flips (1600) · 6 exit wipe (2500) · 7 gone (2675)
  const [st, setSt] = useState(rm ? 5 : 0)
  useEffect(() => {
    if (rm) return
    const ids = ([[20, 1], [250, 2], [600, 3], [1200, 4], [1600, 5], [2500, 6], [2675, 7]] as const).map(([ms, n]) => window.setTimeout(() => setSt(n), ms))
    return () => ids.forEach(window.clearTimeout)
  }, [rm])
  const d = g.data as { score: Record<Side, number>; ball_kmh?: number; distance_m?: number; assist_player_id?: string | null }
  const before = { ...d.score, [g.team]: d.score[g.team] - 1 }
  const num = (v: number) => (es ? String(v).replace('.', ',') : String(v))
  const tr = (css: string) => (rm ? 'none' : css)
  const show = (from: number, delay = '0ms'): CSSProperties => ({ opacity: st >= from && st < 7 ? 1 : 0, transform: st >= from ? 'none' : 'translateY(1.6cqw)', transition: tr(`opacity 260ms ease ${delay}, transform 420ms ${EASE} ${delay}`) })
  const cells: [string, string, string][] = [[minute(g.clock_s ?? 0), '', es ? 'Minuto' : 'Minute']]
  if (d.ball_kmh != null) cells.push([num(d.ball_kmh), 'km/h', es ? 'Velocidad' : 'Ball speed'])
  if (d.distance_m != null) cells.push([num(d.distance_m), 'm', es ? 'Distancia' : 'Distance'])
  if (d.assist_player_id) cells.push([nameOf(names, d.assist_player_id).toUpperCase(), '', es ? 'Asistencia' : 'Assist'])
  const digit = (side: Side) => {
    const scorer = side === g.team
    const flip = st >= 5
    return (
      <span className="relative inline-block text-center [perspective:30cqw]">
        <span className="invisible">{d.score[side]}</span>
        <span className="absolute inset-0" style={{ transform: scorer && flip ? 'rotateX(-90deg)' : 'none', transition: tr(`transform 300ms ${EASE}`), opacity: scorer && flip ? 0 : 1 }}>{before[side]}</span>
        {scorer && <span className="absolute inset-0 text-primary" style={{ transform: flip ? 'none' : 'rotateX(90deg)', transition: tr(`transform 300ms ${EASE} 120ms`), opacity: flip ? 1 : 0 }}>{d.score[side]}</span>}
      </span>
    )
  }
  return (
    <div className="pointer-events-none absolute inset-0 z-[6] overflow-hidden" style={{ containerType: 'inline-size' }}>
      <div className="absolute inset-0" style={{ backdropFilter: st >= 1 && st < 7 ? 'blur(6px) brightness(.5) saturate(.6)' : 'none', transition: tr('backdrop-filter 250ms ease-out') }} />
      <div className="absolute inset-0 flex items-center gap-[4cqw] px-[7cqw]" style={{ opacity: st >= 7 ? 0 : 1, transition: tr('opacity 150ms') }}>
        <div className="relative h-[31cqw] w-[21cqw] shrink-0 overflow-hidden bg-[#081120]" style={{ clipPath: st >= 3 ? 'inset(0 0 0 0)' : 'inset(0 100% 0 0)', transition: tr(`clip-path 380ms ${EASE}`) }}>
          <img src={`/players/${g.player_id}.png`} alt="" className="absolute inset-0 size-full object-cover object-top" onError={(e) => { e.currentTarget.style.display = 'none' }} />
          <span className="absolute inset-y-0 left-0 w-[.8cqw]" style={{ background: STRIPE[g.team] }} />
        </div>
        <div className="flex min-w-0 flex-col gap-[1.2cqw]">
          <span className="font-mono text-[1.4cqw] font-bold uppercase tracking-[.16em] text-primary" style={show(3)}>{teams[g.team].name}</span>
          <span className="font-heading text-[14cqw] font-extrabold uppercase leading-[.85] tracking-[.01em] text-foreground" style={show(3, '60ms')}>{es ? 'GOL' : 'GOAL'}</span>
          <span className="font-heading text-[3.2cqw] font-bold uppercase leading-none text-foreground" style={show(3, '120ms')}>{nameOf(names, g.player_id)}</span>
          <div className="mt-[1cqw] flex items-center gap-[1.6cqw] font-mono text-[3.4cqw] font-bold" style={show(4)}>
            <span className="font-heading text-[2cqw] font-bold">{teams.home.short}</span>{digit('home')}<span>–</span>{digit('away')}<span className="font-heading text-[2cqw] font-bold">{teams.away.short}</span>
          </div>
          <div className="flex self-start bg-[rgba(20,34,58,.97)]" style={show(4, '80ms')}>
            {cells.map(([v, u, l]) => (
              <div key={l} className="flex flex-col gap-[.4cqw] border-r border-foreground/10 px-[1.4cqw] py-[1cqw]">
                <span className="flex items-baseline gap-[.4cqw] whitespace-nowrap"><span className="font-mono text-[2.2cqw] font-semibold leading-none">{v}</span><span className="font-mono text-[1.1cqw] text-muted-foreground">{u}</span></span>
                <span className="text-[.9cqw] font-semibold uppercase leading-none tracking-[.08em] text-muted-foreground">{l}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="absolute inset-0 bg-primary" style={{ transform: st < 2 ? 'translateX(-100%)' : st < 6 ? 'translateX(100%)' : 'translateX(-100%)', transition: tr(st < 2 || st === 5 ? 'none' : `transform 350ms ${EASE}`), visibility: rm ? 'hidden' : 'visible' }} />
    </div>
  )
}

/** The only other mark on the picture: top right, "REPLAY · VT n" while the studio cues a play. */
export function ReplayTag({ text }: { text: string }) {
  return (
    <div className="pointer-events-none absolute right-[2.2cqw] top-[2cqw] z-[4] flex items-center gap-[.6cqw] bg-[rgba(12,23,42,.92)] px-[1cqw] py-[.6cqw] font-mono text-[1cqw] font-bold tracking-[.12em] text-foreground">
      <span className="size-[.7cqw] bg-primary" />{text}
    </div>
  )
}

/** Under the timeline: what is on air, how long it has left and what comes next. */
export function OnAirBar({ air, next, clean, ft, time, names }: { air: Air | null; next: Air | null; clean: boolean; ft: boolean; time: number; names: Names }) {
  const live = !!air && !clean && !ft
  const pill = clean ? 'CLEAN' : ft ? 'FULL TIME' : air ? 'ON AIR' : 'OFF AIR'
  const title = clean ? 'tacticAI graphics are off on this feed' : ft ? 'Full-time graphic' : air ? `${KIND[air.g.type][0]} · ${gName(air.g, names)}` : 'Nothing on air'
  const sub = clean ? 'The Plus feed and the API keep the same timeline.'
    : ft ? 'Holds 12 s, then the replay starts.'
    : air ? `${Math.max(1, Math.ceil(air.end - time))} s left${air.cutBy ? ` · ends early, ${gName(air.cutBy, names)} comes in` : ''}`
    : next ? `Next: ${gName(next.g, names)} at ${mmss(next.start)}` : 'Full time next'
  return (
    <div className="flex min-h-[22px] flex-wrap items-center gap-3 rounded-[10px] border border-foreground/10 px-3.5 py-2.5">
      <span className={cn('rounded px-[7px] py-1 font-mono text-[10px] font-bold tracking-[.12em]', live ? 'bg-primary text-primary-foreground' : 'bg-foreground/[.08] text-muted-foreground')}>{pill}</span>
      <span className="text-[13px] font-semibold">{title}</span>
      <span className="text-[13px] text-muted-foreground">{sub}</span>
    </div>
  )
}

const KIND_ES: Record<string, string> = { goal: 'Gol', shot: 'Disparo', carry: 'Conducción', pass: 'Pase', tackle: 'Recuperación', chance: 'Ocasión' }

/** The presenter's teleprompter: Open, one VT per segment (Cue seeks the video to its play), Close. */
export function StudioScriptView({ script, cue, onCue }: { script: StudioScript | null; cue: number | null; onCue: (i: number, t: number | null) => void }) {
  if (!script) return <span className="text-[13px] text-dim">This match has no studio script yet: regenerate it to get one.</span>
  const es = script.lang === 'es'
  const blocks = [
    { slug: 'Open', meta: 'Presenter to camera', text: script.opening, t: null as number | null },
    ...script.segments.map((s, i) => ({ slug: `VT ${i + 1}`, meta: `${s.minute}' · ${es ? (KIND_ES[s.kind] ?? s.kind) : s.kind.charAt(0).toUpperCase() + s.kind.slice(1)}`, text: s.text, t: s.t_s })),
    ...(script.closing ? [{ slug: 'Close', meta: 'Presenter to camera', text: script.closing, t: null }] : []),
  ]
  const words = blocks.reduce((n, b) => n + b.text.split(/\s+/).length, 0)
  return (
    <div className="-mx-3.5 -mt-3 flex flex-col">
      <div className="flex items-baseline justify-between gap-2.5 px-4 pb-2.5 pt-3.5">
        <span className="flex flex-col gap-[3px]"><span className="font-heading text-sm font-semibold">Full-time script</span><span className="text-xs text-muted-foreground">Written by the Studio agent · {es ? 'Spanish' : 'English'}</span></span>
        <span className="font-mono text-[11px] text-muted-foreground">≈ {Math.round(words / 2.5)} s read</span>
      </div>
      <div className="border-t border-foreground/10 bg-[#070E1A] pb-6 pt-2">
        {blocks.map((b, i) => {
          const c = cue === i
          return (
            <div key={b.slug} role="button" tabIndex={0} onClick={() => onCue(i, b.t)} onKeyDown={(e) => { if (e.key === 'Enter') onCue(i, b.t) }}
              className={cn('relative flex cursor-pointer flex-col gap-2 border-b border-foreground/[.06] py-3.5 pl-7 pr-[18px]', c && 'bg-primary/5')}>
              <span className={cn('absolute left-2.5 top-11 size-0 border-y-[6px] border-l-8 border-y-transparent border-l-primary', c ? 'opacity-100' : 'opacity-0')} />
              <span className="flex items-center gap-2 font-mono text-[10.5px] font-semibold uppercase tracking-[.1em] text-dim">
                <span className={cn('whitespace-nowrap rounded-[3px] px-1.5 py-0.5 font-bold', c ? 'bg-primary text-primary-foreground' : 'bg-foreground/[.08] text-[#C9CDD2]')}>{b.slug}</span>
                <span className="whitespace-nowrap">{b.meta}</span>
                {b.t != null && <span className={cn('ml-auto whitespace-nowrap', c ? 'text-primary' : 'text-dim')}>{c ? 'Cued ▸' : 'Cue'}</span>}
              </span>
              <span className={cn('text-pretty text-[19px] font-medium leading-[1.5]', c ? 'text-foreground' : 'text-[#8F959E]')}>{b.text}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const REEL_TXT = {
  en: { title: 'Reels', sub: 'Vertical clips for social, cut as the match plays.', gen: 'Generating reel…', empty: 'Reels appear here as goals and shots happen.', dl: 'Download reel', open: 'Open reel', close: 'Close', prev: 'Previous reel', next: 'Next reel', download: 'Download' },
  es: { title: 'Reels', sub: 'Clips verticales para redes, cortados mientras se juega el partido.', gen: 'Generando reel…', empty: 'Los reels aparecen acá a medida que hay goles y remates.', dl: 'Descargar reel', open: 'Abrir reel', close: 'Cerrar', prev: 'Reel anterior', next: 'Reel siguiente', download: 'Descargar' },
}

interface ReelItem { id: string; r: ReelManifest['reels'][number]; kind: string; name: string; clock: string; url: string }

const chip = (goal: boolean) => cn('self-start rounded-[3px] border px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[.1em]', goal ? 'border-primary bg-primary text-primary-foreground' : 'border-foreground/40 text-foreground')
const face = (id: string | null, cls: string) => id && <img src={`/players/${id}.png`} alt="" className={cn('shrink-0 rounded-full bg-[#081120] object-cover object-top', cls)} onError={(e) => { e.currentTarget.style.display = 'none' }} />

/** One 9:16 card: "being generated" for 3 s (lime scan and a filling bar) the first time it shows, then the reel itself; click opens the viewer. */
function ReelCard({ it, lang, done, onDone, onOpen }: { it: ReelItem; lang: Lang; done: boolean; onDone: () => void; onOpen: () => void }) {
  const t = REEL_TXT[lang]
  const rm = useMemo(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches, [])
  const vid = useRef<HTMLVideoElement>(null)
  const [p, setP] = useState(0)
  useEffect(() => {
    if (done) return
    const t0 = performance.now()
    const id = window.setInterval(() => {
      const x = Math.min(1, (performance.now() - t0) / REEL_GEN_MS)
      setP(x)
      if (x >= 1) { window.clearInterval(id); onDone() }
    }, 60)
    return () => window.clearInterval(id)
  }, [done, onDone])
  const hover = (on: boolean) => {
    const v = vid.current
    if (!v || rm) return
    if (on) void v.play().catch(() => {})
    else { v.pause(); v.currentTime = 0 }
  }
  return (
    <div onMouseEnter={() => hover(true)} onMouseLeave={() => hover(false)} className={cn('relative aspect-[9/16] overflow-hidden rounded-lg border bg-[#081120] transition-colors', done ? 'border-foreground/10 hover:border-primary' : 'border-foreground/10')}>
      {done && (
        <>
          <video ref={vid} src={it.url} muted loop playsInline preload="metadata" className="absolute inset-0 size-full object-cover" />
          <button type="button" onClick={onOpen} aria-label={`${t.open}: ${it.kind} ${it.name}`} className="absolute inset-0 cursor-pointer focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary" />
          <a href={it.url} download={`${it.r.graphic_id}-${lang}.mp4`} aria-label={t.dl} title={t.dl} className="absolute right-1.5 top-1.5 grid size-7 place-items-center rounded-[5px] bg-[rgba(12,23,42,.85)] text-foreground hover:bg-primary hover:text-primary-foreground focus-visible:outline-2 focus-visible:outline-primary">
            <Download className="size-3.5" />
          </a>
        </>
      )}
      {!done && (
        <>
          {!rm && <span className="absolute inset-x-0 h-1/3 bg-gradient-to-b from-transparent via-primary/40 to-transparent" style={{ top: `${((p * 3) % 1) * 133 - 33}%` }} />}
          <span className="absolute inset-x-2 bottom-[70px] text-center font-mono text-[10px] font-semibold uppercase tracking-[.1em] text-primary">{t.gen}</span>
          <span className="absolute inset-x-0 bottom-0 h-[3px] bg-foreground/15"><span className="block h-full bg-primary" style={{ width: `${p * 100}%` }} /></span>
        </>
      )}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col gap-1.5 bg-gradient-to-t from-[rgba(12,23,42,.95)] via-[rgba(12,23,42,.7)] to-transparent px-2 pb-2.5 pt-8">
        <span className={chip(it.r.type === 'goal')}>{it.kind}</span>
        <span className="flex items-center gap-1.5">
          {face(it.r.player_id, 'size-5')}
          <span className="min-w-0 flex-1 truncate font-heading text-[12px] font-semibold uppercase">{it.name}</span>
          <span className="font-mono text-[10.5px] text-muted-foreground">{it.clock}</span>
        </span>
      </div>
    </div>
  )
}

/** The big viewer of a reel: a native modal dialog (Esc closes, focus returns to the card), arrows or the keys move between the generated reels. */
function ReelViewer({ items, index, lang, onIndex, onClose }: { items: ReelItem[]; index: number; lang: Lang; onIndex: (i: number) => void; onClose: () => void }) {
  const t = REEL_TXT[lang]
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { ref.current?.showModal() }, [])
  const it = items[index]
  const go = (d: number) => { const i = index + d; if (i >= 0 && i < items.length) onIndex(i) }
  const btn = 'grid size-10 place-items-center rounded-lg border border-foreground/25 bg-[rgba(12,23,42,.9)] text-foreground hover:border-primary hover:text-primary focus-visible:outline-2 focus-visible:outline-primary disabled:opacity-30'
  return (
    <dialog
      ref={ref} onClose={onClose} onClick={(e) => { if (e.target === e.currentTarget) ref.current?.close() }}
      onKeyDown={(e) => { if (e.key === 'ArrowLeft') go(-1); if (e.key === 'ArrowRight') go(1) }}
      className="m-auto max-h-none max-w-none bg-transparent p-4 text-foreground backdrop:bg-[rgba(7,14,26,.85)] backdrop:backdrop-blur-md"
    >
      <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-end">
        <button type="button" onClick={() => go(-1)} disabled={index === 0} aria-label={t.prev} className={cn(btn, 'hidden sm:grid')}><ChevronLeft className="size-5" /></button>
        <video key={it.url} src={it.url} autoPlay muted controls playsInline loop className="aspect-[9/16] h-[min(88vh,900px)] max-w-[90vw] rounded-lg border border-primary bg-black object-cover" />
        <div className="flex w-full flex-col gap-3 sm:w-56 sm:self-end">
          <span className={chip(it.r.type === 'goal')}>{it.kind}</span>
          <span className="flex items-center gap-2.5">
            {face(it.r.player_id, 'size-10')}
            <span className="flex min-w-0 flex-col"><span className="truncate font-heading text-[17px] font-semibold uppercase leading-tight">{it.name}</span><span className="font-mono text-xs text-muted-foreground">{it.clock}</span></span>
          </span>
          <a href={it.url} download={`${it.r.graphic_id}-${lang}.mp4`} className="flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-[13px] font-bold text-primary-foreground hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
            <Download className="size-4" />{t.download}
          </a>
          <div className="flex gap-2 sm:hidden">
            <button type="button" onClick={() => go(-1)} disabled={index === 0} aria-label={t.prev} className={btn}><ChevronLeft className="size-5" /></button>
            <button type="button" onClick={() => go(1)} disabled={index === items.length - 1} aria-label={t.next} className={btn}><ChevronRight className="size-5" /></button>
          </div>
        </div>
        <button type="button" onClick={() => go(1)} disabled={index === items.length - 1} aria-label={t.next} className={cn(btn, 'hidden sm:grid')}><ChevronRight className="size-5" /></button>
      </div>
      <button type="button" onClick={() => ref.current?.close()} aria-label={t.close} className={cn(btn, 'absolute right-4 top-4')}><X className="size-5" /></button>
    </dialog>
  )
}

/** The 9:16 reels of the match goals and shots, newest first: a reel exists once the video has passed its play. */
export function ReelsTab({ reels, matchId, rundown, names, lang, time }: { matchId: string; reels: ReelManifest | null; rundown: Rundown | null; names: Names; lang: Lang; time: number }) {
  const [made, setMade] = useState<Set<string>>(() => new Set())
  const [open, setOpen] = useState<string | null>(null)
  const t = REEL_TXT[lang]
  if (!reels) return <span className="text-[13px] text-dim">This match has no reels yet: regenerate it to get them.</span>
  const items: ReelItem[] = reels.reels.filter((r) => r.files[lang] && time >= r.t_in).sort((a, b) => b.t_in - a.t_in).map((r) => {
    const g = rundown?.graphics.find((x) => x.id === r.graphic_id)
    return { id: `${r.graphic_id}-${lang}`, r, kind: KIND[r.type][lang === 'es' ? 1 : 0].toUpperCase(), name: nameOf(names, r.player_id), clock: g?.clock_s != null ? mmss(g.clock_s) : '', url: matchFileUrl(matchId, r.files[lang] as string) }
  })
  const ready = items.filter((i) => made.has(i.id))
  const at = ready.findIndex((i) => i.id === open)
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5"><span className="font-heading text-sm font-semibold">{t.title}</span><span className="text-xs text-muted-foreground">{t.sub}</span></div>
      {items.length === 0 ? (
        <div className="flex aspect-[9/16] w-1/2 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-foreground/25 p-3 text-center text-muted-foreground">
          <Film className="size-6" /><span className="text-xs leading-snug">{t.empty}</span>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2.5">
          {items.map((it) => <ReelCard key={it.id} it={it} lang={lang} done={made.has(it.id)} onDone={() => setMade((m) => new Set(m).add(it.id))} onOpen={() => setOpen(it.id)} />)}
        </div>
      )}
      {open && at >= 0 && <ReelViewer items={ready} index={at} lang={lang} onIndex={(i) => setOpen(ready[i].id)} onClose={() => setOpen(null)} />}
    </div>
  )
}

interface FullTimeProps {
  s: number; lang: Lang; teams: Teams; score: Record<Side, number>; names: Names; star: string | null; view: FanView | null; opening: string | null
}

/** Full time over the dimmed video: result, the star of the night with his face and award, and the studio's opening. */
export function FullTimeOverlay({ s, lang, teams, score, names, star, view: fan, opening }: FullTimeProps) {
  const es = lang === 'es'
  const p = star ? names[star] : undefined
  const award = star ? fan?.awards.find((a) => a.player_id === star) : undefined
  const team = (side: Side, align: string) => (
    <div className={cn('flex flex-col gap-[1.1cqw]', align)}>
      <img src={CREST[side]} alt="" className="h-[7cqw] w-auto object-contain" />
      <span className="font-heading text-[2.3cqw] font-bold uppercase leading-none tracking-[.01em]">{teams[side].name}</span>
    </div>
  )
  return (
    <div className="absolute inset-0 z-[6] flex flex-col bg-[linear-gradient(180deg,rgba(12,23,42,.55),rgba(12,23,42,.88))] px-[3.6cqw] py-[3.2cqw] backdrop-blur-[6px]">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-[.9cqw] font-mono text-[1.25cqw] font-bold tracking-[.2em] text-primary"><span className="size-[1cqw] bg-primary" />{es ? 'FINAL DEL PARTIDO' : 'FULL TIME'}</span>
        <img src="/tacticai-logo-dark-bg.png" alt="tacticAI" className="h-[2cqw] w-auto" />
      </div>
      <div className="grid flex-1 grid-cols-[1fr_auto_1fr] items-center gap-[4cqw]">
        {team('home', 'items-end text-right')}
        <span className="font-mono text-[9cqw] font-bold leading-none tracking-[-.02em]">{score.home}–{score.away}</span>
        {team('away', 'items-start')}
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] gap-[1.6cqw]">
        <div className="flex bg-[rgba(12,23,42,.96)]">
          {p && star ? (
            <>
              <div className="relative w-[11cqw] shrink-0 self-stretch overflow-hidden bg-[#081120]">
                <img src={`/players/${star}.png`} alt="" className="absolute inset-0 size-full object-cover object-top" onError={(e) => { e.currentTarget.style.display = 'none' }} />
                <span className="absolute inset-y-0 left-0 w-[.5cqw]" style={{ background: STRIPE[p.team] }} />
              </div>
              <div className="flex flex-1 flex-col justify-center gap-[1cqw] px-[1.8cqw] py-[1.6cqw]">
                <span className="font-mono text-[.95cqw] font-bold uppercase tracking-[.16em] text-primary">{es ? 'Figura del partido' : 'Star of the night'}</span>
                <span className="border-b-[.2cqw] border-primary pb-[.6cqw] font-heading text-[3cqw] font-bold uppercase leading-none">{p.name}</span>
                {award && (
                  <span className="self-start bg-primary px-[.7cqw] py-[.4cqw] font-mono text-[.85cqw] font-bold uppercase tracking-[.12em] text-primary-foreground">{award.title} · {award.stat}</span>
                )}
              </div>
            </>
          ) : <span className="p-[1.6cqw] font-mono text-[.95cqw] text-muted-foreground">{teams.home.short} {score.home}–{score.away} {teams.away.short}</span>}
        </div>
        <div className="flex flex-col justify-center gap-[1cqw] bg-[rgba(12,23,42,.8)] px-[2cqw] py-[1.6cqw]">
          <span className="font-mono text-[.95cqw] font-bold uppercase tracking-[.16em] text-muted-foreground">{es ? 'La historia del partido' : 'The story of the match'}</span>
          <span className="text-pretty font-heading text-[2cqw] font-semibold leading-[1.3]">{opening}</span>
        </div>
      </div>
      <span className="absolute bottom-[.9cqw] right-[3.6cqw] font-mono text-[.95cqw] text-dim">{es ? 'Repetición en ' : 'Replay in '}<Countdown s={s} /> s</span>
    </div>
  )
}
