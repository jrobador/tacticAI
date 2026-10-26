// Pure helpers of the New match screen: the chips over the real Recipe fields, titles, change notes and the progress rows.
import type { Catalog, JobState, JobStatus, Recipe, RecipeIssue, Side } from '@/api/types'
import { label } from './format'
import { defaultSituation } from './recipe'

export type Teams = Record<Side, { name: string; short: string }>

export type Msg =
  | { id: number; kind: 'user'; text: string }
  | { id: number; kind: 'writing' }
  | { id: number; kind: 'setup'; recipe: Recipe; note: string; issues: RecipeIssue[]; used?: boolean }
  | { id: number; kind: 'error'; code: string | null; msg: string; todo: string; toMatches?: boolean }
  | { id: number; kind: 'gen'; jobId: string }

/** The job the screen follows. recipe/title are null when the job was opened directly (no chat). */
export interface Gen {
  jobId: string
  title: string | null
  recipe: Recipe | null
  status: JobStatus | null
  error: string | null
}

export interface Opt { value: string; label: string; sub?: string }
export interface Chip {
  key: string
  k: string
  v: string
  cur: string
  opts: Opt[]
  set: (r: Recipe, val: string) => void
}

const SIDES: Side[] = ['home', 'away']

export function chipsOf(r: Recipe, cat: Catalog, teams: Teams): Chip[] {
  const sideOpts: Opt[] = SIDES.map((s) => ({ value: s, label: teams[s].short, sub: teams[s].name }))
  const lo = Math.round(cat.limits.level.min * 20)
  const hi = Math.round(cat.limits.level.max * 20)
  const levels: Opt[] = Array.from({ length: hi - lo + 1 }, (_, i) => (lo + i) / 20).map((l) => ({ value: l.toFixed(2), label: l.toFixed(2) }))
  const chips: Chip[] = []
  for (const s of SIDES) {
    const sh = teams[s].short
    chips.push(
      { key: `${s}f`, k: sh, v: r[s].formation, cur: r[s].formation, opts: cat.formations.map((f) => ({ value: f, label: f })), set: (x, v) => { x[s].formation = v } },
      { key: `${s}s`, k: `${sh} style`, v: label(r[s].style), cur: r[s].style, opts: cat.styles.map((v) => ({ value: v, label: label(v) })), set: (x, v) => { x[s].style = v } },
      { key: `${s}l`, k: `${sh} level`, v: r[s].level.toFixed(2), cur: r[s].level.toFixed(2), opts: levels, set: (x, v) => { x[s].level = Number(v) } },
    )
  }
  chips.push({
    key: 'mode', k: 'Mode', v: r.mode === 'full_match' ? 'Full match' : 'Situation', cur: r.mode,
    opts: [{ value: 'situation', label: 'Situation' }, { value: 'full_match', label: 'Full match', sub: 'Takes about 11 minutes' }],
    set: (x, v) => {
      x.mode = v as Recipe['mode']
      if (v === 'full_match') { x.situation = null; x.steps = 3000 } else { x.situation = x.situation ?? defaultSituation(cat); x.steps = cat.limits.steps_situation }
    },
  })
  const sit = r.situation
  if (!sit) return chips
  const tpl = sit.template ?? 'custom'
  chips.push(
    {
      key: 'sit', k: 'Situation', v: sit.template ? label(sit.template) : 'Custom positions', cur: tpl,
      opts: [...(sit.template ? [] : [{ value: 'custom', label: 'Custom positions' }]), ...cat.templates.map((t) => ({ value: t, label: label(t) }))],
      set: (x, v) => { const s = x.situation!; if (v === 'custom') return; s.template = v; s.positions = null; s.ball = null; s.ball_owner = s.ball_owner ?? 'home' },
    },
    { key: 'ball', k: 'Ball', v: teams[sit.ball_owner ?? 'home'].short, cur: sit.ball_owner ?? 'home', opts: sideOpts, set: (x, v) => { x.situation!.ball_owner = v as Side } },
  )
  const wanted = sit.wanted.length ? sit.wanted : ['']
  wanted.forEach((p, i) => {
    const [name, arg] = p.split(':')
    const spec = cat.wanted.find((w) => w.name === name)
    chips.push({
      key: `want${i}`, k: 'Want', v: name ? label(name) : 'Anything', cur: name,
      opts: [...(wanted.length === 1 ? [{ value: '', label: 'Anything', sub: 'No condition' }] : []), ...cat.wanted.map((w) => ({ value: w.name, label: label(w.name), sub: w.description }))],
      set: (x, v) => {
        const w = x.situation!.wanted
        if (v === '') { w.splice(i); return }
        const t = cat.wanted.find((q) => q.name === v)?.takes
        const owner = x.situation!.ball_owner ?? 'home'
        w[i] = t === 'side' ? `${v}:${owner}` : t === 'player' ? `${v}:${cat.players.find((q) => q.team === owner)?.name ?? ''}` : v
      },
    })
    if (spec?.takes === 'side') {
      chips.push({ key: `want${i}t`, k: 'Team', v: teams[(arg as Side) ?? 'home']?.short ?? arg, cur: arg, opts: sideOpts, set: (x, v) => { x.situation!.wanted[i] = `${name}:${v}` } })
    } else if (spec?.takes === 'player') {
      chips.push({
        key: `want${i}p`, k: 'Player', v: arg, cur: arg,
        opts: cat.players.map((q) => ({ value: q.name, label: q.name, sub: `${teams[q.team].short} #${q.number}` })),
        set: (x, v) => { x.situation!.wanted[i] = `${name}:${v}` },
      })
    }
  })
  return chips
}

export function titleOf(r: Recipe, teams: Teams): string {
  if (r.mode === 'full_match' || !r.situation) return `Full match · ${teams.home.short} vs ${teams.away.short}`
  const s = r.situation
  const w = s.wanted[0]
  const res = !w ? 'attack' : w.startsWith('goal') ? 'goal' : 'shot'
  return `${s.template ? label(s.template) : 'Custom situation'} · ${teams[s.ball_owner ?? 'home'].short} ${res}`
}

/** "Updated: BKA style → High press · Want → Goal by team." Empty when nothing differs. */
export function changesNote(before: Recipe, after: Recipe, cat: Catalog, teams: Teams): string[] {
  const old = new Map(chipsOf(before, cat, teams).map((c) => [c.key, c.cur]))
  return chipsOf(after, cat, teams).filter((c) => old.get(c.key) !== c.cur).map((c) => `${c.k} → ${c.v}`)
}

// ---- progress ----
export const STAGES: [JobState, string][] = [
  ['searching', 'Searching the engine'], ['rendering', 'Recording'], ['analyzing', 'Analysing'], ['agents', 'Agents'], ['explaining', 'Explaining'],
  ['personalizing', 'Personalising'], ['directing', 'Directing'], ['rendering_assets', 'Rendering assets'], ['done', 'Done'],
]

export interface Row {
  label: string
  state: 'todo' | 'active' | 'done' | 'failed'
  /** Seconds: elapsed for the active row, duration for a finished one, total on Done. null: nothing to show. */
  secs: number | null
  total: boolean
  seed: string | null
  word: string
}

/** One row per stage, built from the job state and `stages` (start time of each state). `now` is ms. */
export function stageRows(s: JobStatus | null, now: number): Row[] {
  const st = s?.stages ?? {}
  const t = (k: string): number | null => (st[k] ? Date.parse(st[k]) : null)
  const state = s?.state ?? 'queued'
  const failed = state === 'failed' || state === 'no_winner'
  let last = 0
  STAGES.forEach(([k], i) => { if (t(k) !== null) last = i })
  const cur = state === 'done' ? 9 : Math.max(0, STAGES.findIndex(([k]) => k === state))
  return STAGES.map(([k, text], i): Row => {
    const start = t(k)
    const nextStart = STAGES.slice(i + 1).map(([n]) => t(n)).find((v) => v !== null) ?? null
    const isFailed = failed && i === last
    const done = !failed ? i < cur : i < last
    const active = !failed && i === cur && state !== 'done'
    const rowState: Row['state'] = isFailed ? 'failed' : done || (state === 'done' && i === 8) ? 'done' : active ? 'active' : 'todo'
    let secs: number | null = null
    let total = false
    if (i === 8) {
      const q = t('queued')
      if (state === 'done' && q !== null && start !== null) { secs = (start - q) / 1000; total = true }
    } else if (start !== null) {
      const end = isFailed ? (t(state) ?? now) : nextStart
      if (end !== null) secs = (end - start) / 1000
      else if (active) secs = (now - start) / 1000
    }
    let seed: string | null = null
    if (i === 0 && rowState !== 'todo') {
      if (active && s?.progress) seed = `seed ${s.progress.done} of ${s.progress.total}`
      else if (s?.search) seed = `${s.search.met} of ${s.search.seeds} seeds matched`
    }
    const word = rowState === 'failed' ? 'Failed' : rowState === 'done' ? (i === 8 ? '' : 'Done') : rowState === 'active' ? (state === 'queued' ? 'Queued' : 'Running') : ''
    return { label: text, state: rowState, secs, total, seed, word }
  })
}
