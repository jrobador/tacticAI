import { useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { activeJobId, ApiError, createJob, matchFileUrl, MOCK } from '@/api/client'
import type { Catalog, LibraryEntry, MatchSummary, Side, TemplatePreview } from '@/api/types'
import { CREST, DEFAULT_TEAMS } from '@/lib/format'
import { playTitle, type Teams } from '@/lib/newMatch'
import { Alert } from '@/components/ui/alert'
import { go, matchesPreset } from '@/lib/nav'
import { cn } from '@/lib/utils'

export interface MatchesData {
  matches: MatchSummary[]
  entries: LibraryEntry[]
}

// Formation layouts (percent of the pitch, own goal on the left, goalkeeper added in dots()): layout only, not data.
const D4 = [[18, 15], [17, 38], [17, 62], [18, 85]], D3 = [[17, 25], [16, 50], [17, 75]], D5 = [[20, 8], [16, 28], [15, 50], [16, 72], [20, 92]]
const FORMS: Record<string, number[][]> = {
  '4-4-2': [...D4, [32, 15], [31, 38], [31, 62], [32, 85], [45, 38], [45, 62]],
  '4-3-3': [...D4, [31, 30], [29, 50], [31, 70], [44, 18], [46, 50], [44, 82]],
  '4-2-3-1': [...D4, [28, 38], [28, 62], [38, 18], [39, 50], [38, 82], [47, 50]],
  '4-1-4-1': [...D4, [26, 50], [35, 15], [34, 38], [34, 62], [35, 85], [47, 50]],
  '3-5-2': [...D3, [30, 8], [29, 32], [27, 50], [29, 68], [30, 92], [45, 38], [45, 62]],
  '3-4-3': [...D3, [30, 12], [29, 38], [29, 62], [30, 88], [44, 20], [46, 50], [44, 80]],
  '5-3-2': [...D5, [30, 30], [29, 50], [30, 70], [43, 38], [43, 62]],
  '5-4-1': [...D5, [31, 15], [30, 38], [30, 62], [31, 85], [44, 50]],
}
const dots = (home: string, away: string) => [
  ...(FORMS[home] ? [[5, 50], ...FORMS[home]] : []).map(([x, y]) => ({ x, y, home: true })),
  ...(FORMS[away] ? [[5, 50], ...FORMS[away]] : []).map(([x, y]) => ({ x: 100 - x, y: 100 - y, home: false })),
]

export interface Card {
  key: string
  title: string
  /** Crests next to the title (the team with the ball, or both for a whole match). */
  crests: Side[]
  home: string
  away: string
  tag: string | null
  video: boolean
  generated: boolean
  /** render/thumb.jpg of the recorded match. */
  thumb: string | null
  /** Start of the play for the mini pitch: ball in metres (centre origin, home attacks +x), team with the ball and the template players. */
  play: { ball: { x: number; y: number }; owner: Side; preview?: TemplatePreview } | null
  open: () => void
}

const thumbOf = (matchId: string | null) => (matchId && !MOCK ? matchFileUrl(matchId, 'render/thumb.jpg') : null)

export function entryCard(e: LibraryEntry, teams: Teams, catalog: Catalog | null, open: () => void): Card {
  const preview = catalog?.template_previews[e.template]?.[e.ball_owner]
  return {
    key: e.entry_id, title: playTitle(e.template, e.ball_owner, e.wanted[0], teams), crests: [e.ball_owner], home: e.home.formation, away: e.away.formation,
    tag: e.wanted[0]?.startsWith('goal') ? 'GOAL' : 'SHOT', video: !!e.match_id, generated: false, thumb: thumbOf(e.match_id),
    play: preview ? { ball: preview.ball, owner: e.ball_owner, preview } : null, open,
  }
}

const PW = 105, PH = 68
const px = (x: number) => x + PW / 2, py = (y: number) => y + PH / 2

/** Mini pitch of a play: teams (home filled, away outlined), the ball where the play starts and the attack direction of the team with it. */
function MiniPitch({ c }: { c: Card }) {
  const p = c.play
  const players = p?.preview
    ? [...p.preview.home.map((d) => ({ x: px(d.x), y: py(d.y), home: true })), ...p.preview.away.map((d) => ({ x: px(d.x), y: py(d.y), home: false }))]
    : dots(c.home, c.away).map((d) => ({ x: (d.x * PW) / 100, y: (d.y * PH) / 100, home: d.home }))
  const dir = p?.owner === 'away' ? -1 : 1
  const bx = p ? px(p.ball.x) : 0, by = p ? py(p.ball.y) : 0
  const x2 = Math.min(PW - 2, Math.max(2, bx + dir * 16))
  return (
    <svg viewBox={`0 0 ${PW} ${PH}`} className="absolute inset-0 size-full" aria-hidden>
      <g fill="none" stroke="currentColor" strokeWidth=".5" className="text-foreground/30">
        <line x1={PW / 2} x2={PW / 2} y1="0" y2={PH} />
        <circle cx={PW / 2} cy={PH / 2} r="7" />
        <rect x="0" y="14" width="16" height="40" /><rect x={PW - 16} y="14" width="16" height="40" />
      </g>
      {players.map((d, j) => (
        <circle key={j} cx={d.x} cy={d.y} r="1.7" strokeWidth=".7" className="stroke-foreground" fill={d.home ? '#f0f0f0' : '#0c172a'} />
      ))}
      {p && (
        <g className="text-primary" stroke="currentColor" fill="currentColor">
          <line x1={bx} y1={by} x2={x2} y2={by} strokeWidth="1.1" strokeLinecap="round" />
          <path d={`M${x2 + dir * 1.8} ${by} l${-dir * 3.2} -2.2 v4.4 z`} stroke="none" />
          <circle cx={bx} cy={by} r="2.2" stroke="#0c172a" strokeWidth=".7" />
        </g>
      )}
    </svg>
  )
}

/** One card of the Matches grid; the New match screen reuses it for its templates. */
export function CardButton({ c, i, disabled }: { c: Card; i: number; disabled?: boolean }) {
  const [bad, setBad] = useState(false)
  return (
  <button
    type="button" onClick={c.open} disabled={disabled}
    style={{ animationDelay: `${(i % 4) * 60}ms` }}
    className="rise flex flex-col gap-2.5 rounded-[14px] border border-foreground/10 bg-panel p-2.5 text-left transition-[border-color,transform] hover:border-primary active:scale-[.985] disabled:opacity-60"
  >
    <span className="relative block aspect-[105/68] w-full overflow-hidden rounded-[7px] border border-foreground/20 bg-[#0f1b2f]">
      {c.thumb && !bad ? <img src={c.thumb} alt="" loading="lazy" onError={() => setBad(true)} className="size-full object-cover" /> : <MiniPitch c={c} />}
    </span>
    <span className="flex flex-col gap-0.5">
      <span className="flex items-center gap-1.5 text-[13.5px] font-semibold">
        {c.crests.map((s) => <img key={s} src={CREST[s]} alt="" className="size-4 flex-none object-contain" />)}
        <span className="truncate">{c.title}</span>
      </span>
      <span className="font-mono text-[11px] text-dim">{c.home} vs {c.away}</span>
    </span>
    <span className="flex min-h-[22px] flex-wrap items-center gap-2">
      {c.tag && (
        <span className={cn('rounded border px-1.5 py-0.5 font-mono text-[10px] font-bold tracking-[.05em]', c.tag === 'GOAL' ? 'border-primary bg-primary text-primary-foreground' : 'border-foreground/30')}>{c.tag}</span>
      )}
      {c.video && <span className="flex items-center gap-1 text-[10.5px] font-semibold"><span className="text-[8px]">▶</span>Video</span>}
      {c.generated && <span className="text-[10.5px] font-semibold text-primary">● Generated</span>}
    </span>
  </button>
  )
}

const FILTERS = [['all', 'All'], ['generated', 'Generated'], ['templates', 'Templates'], ['video', 'With video']] as const
type Filter = (typeof FILTERS)[number][0]
const SHOWN = 24

/** Generated matches first (a template recording is listed once, as its template), then the library. */
export function Matches({ data, error, catalog }: { data: MatchesData | null; error: string | null; catalog: Catalog | null }) {
  const teams: Teams = data?.matches[0]?.teams ?? DEFAULT_TEAMS
  const [filter, setFilter] = useState<Filter>(((matchesPreset.value as Filter | null) ?? 'all'))
  useEffect(() => { matchesPreset.value = null }, [])
  const [all, setAll] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<{ text: string; jobId?: string } | null>(null)

  async function record(e: LibraryEntry) {
    if (busy) return
    setBusy(true)
    setNotice(null)
    try {
      const r = await createJob({ library_id: e.entry_id })
      go(r.kind === 'existing' ? `/matches/${r.match_id}` : `/jobs/${r.job_id}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setNotice({ text: 'A match is already being generated', jobId: activeJobId(err) ?? undefined })
      else setNotice({ text: err instanceof Error ? err.message : String(err) })
    } finally {
      setBusy(false)
    }
  }

  const cards: Card[] = data
    ? [
        ...data.matches.filter((m) => !m.library_id).map((m): Card => ({
          key: m.match_id, title: `${m.teams.home.short} vs ${m.teams.away.short}`, crests: ['home', 'away'], thumb: thumbOf(m.match_id), play: null,
          home: m.formations.home, away: m.formations.away, tag: null, video: true, generated: true, open: () => go(`/matches/${m.match_id}`),
        })),
        ...data.entries.map((e) => entryCard(e, teams, catalog, () => (e.match_id ? go(`/matches/${e.match_id}`) : void record(e)))),
      ]
    : []
  const nGen = cards.filter((c) => c.generated).length
  const shown = cards.filter((c) => filter === 'all' || (filter === 'generated' ? c.generated : filter === 'video' ? c.video : !c.generated))
  const counts: Record<Filter, string> = { all: ` · ${cards.length}`, generated: ` · ${nGen}`, templates: ` · ${cards.length - nGen}`, video: '' }

  return (
    <section className="mx-auto flex w-full max-w-[1600px] flex-col gap-5 px-7 pb-14 pt-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[30px] font-semibold leading-[1.1] tracking-[-0.025em]">Matches</h1>
        </div>
        <div className="flex flex-wrap gap-0.5 rounded-[10px] border border-foreground/10 bg-panel p-[3px]">
          {FILTERS.map(([k, l]) => (
            <button
              key={k} type="button" onClick={() => { setFilter(k); setAll(false) }} aria-pressed={filter === k}
              className={cn('rounded-[7px] px-[11px] py-1.5 text-[12.5px] font-semibold', filter === k ? 'bg-[#22304a] text-foreground' : 'text-muted-foreground hover:text-foreground')}
            >
              {l}{data ? counts[k] : ''}
            </button>
          ))}
        </div>
      </div>

      {notice && (
        <Alert>
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium">{notice.text}</p>
            {notice.jobId && <a className="text-primary underline" href={`#/jobs/${notice.jobId}`}>See its progress</a>}
          </div>
        </Alert>
      )}
      {error && <Alert><AlertTriangle className="mt-0.5 size-4 shrink-0" /><p>{error}</p></Alert>}
      {!data && !error && <p className="text-sm text-muted-foreground">Loading matches...</p>}

      {data && filter === 'generated' && nGen === 0 && (
        <div className="flex flex-col items-start gap-2.5 rounded-[14px] border border-dashed border-foreground/20 p-7">
          <span className="font-heading text-base font-semibold">No generated matches yet</span>
          <span className="text-[13.5px] text-muted-foreground">Describe a play in New match.</span>
          <a href="#/" className="rounded-lg border border-foreground/25 px-[13px] py-2 text-[13px] font-semibold hover:border-primary hover:text-primary">New match</a>
        </div>
      )}

      <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-3">
        {shown.slice(0, all ? shown.length : SHOWN).map((c, i) => (
          <CardButton key={c.key} c={c} i={i} disabled={busy} />
        ))}
      </div>
      {shown.length > SHOWN && (
        <button type="button" onClick={() => setAll((v) => !v)} className="self-center rounded-[9px] border border-foreground/20 px-4 py-[9px] text-[13px] font-semibold hover:border-foreground/45">
          {all ? 'Show fewer' : `Show all ${shown.length}`}
        </button>
      )}
    </section>
  )
}
