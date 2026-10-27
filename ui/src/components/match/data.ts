// Data hooks of the match page. All of it comes from the API or the match files; nothing is computed from samples.
import { useEffect, useState } from 'react'
import { getHeatmaps, getInsights, getJob, getModels, getOverlays, getRecap, listMatches, loadMatch, matchFileUrl, MOCK } from '@/api/client'
import type { ReelManifest, Club, Insight, JobStatus, Lang, Lens, MatchBundle, MatchSummary, ModelCard, OverlaysResponse, Recap, Side } from '@/api/types'
import type { Profile, TrackingFrame } from './model'

/** The match package. `error` is set when a required file is missing. */
export function useBundle(matchId: string) {
  const [bundle, setBundle] = useState<MatchBundle | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    loadMatch(matchId).then((b) => live && setBundle(b)).catch((e: Error) => live && setError(e.message))
    return () => { live = false }
  }, [matchId])
  return { bundle, error }
}

/** /overlays for one lens. The previous result stays on screen until the new one arrives, so a change crossfades. */
export function useOverlays(matchId: string, lens: Lens, p: Profile): OverlaysResponse | null {
  const [res, setRes] = useState<OverlaysResponse | null>(null)
  const metric = lens === 'one_metric' ? p.metric : null
  useEffect(() => {
    let live = true
    getOverlays(matchId, { lens, lang: p.lang, club: p.club, player: p.player, metric })
      .then((r) => live && setRes(r)).catch(() => live && setRes({ available: false }))
    return () => { live = false }
  }, [matchId, lens, p.lang, p.club, p.player, metric])
  return res
}

/** explain/insights.jsonl; it only exists once Explain ran (`enabled`). */
export function useExplainFiles(matchId: string, enabled: boolean) {
  const [insights, setInsights] = useState<Insight[]>([])
  useEffect(() => {
    if (!enabled) return
    let live = true
    getInsights(matchId).then((r) => live && setInsights(r)).catch(() => {})
    return () => { live = false }
  }, [matchId, enabled])
  return { insights }
}

/** personalize/variants/<lens>_<lang>_<club>.json: the text of every moment for the audience, language and side. */
export function useVariants(matchId: string, lens: Lens, p: Profile, enabled: boolean) {
  const [state, setState] = useState<{ key: string; texts: Record<string, { title: string; text: string }> } | null>(null)
  const textLens = lens === 'broadcast' || lens === 'one_metric' ? 'analyst' : lens
  const key = `${textLens}_${p.lang}_${p.club}`
  useEffect(() => {
    if (!enabled || MOCK) return
    let live = true
    fetch(matchFileUrl(matchId, `personalize/variants/${key}.json`))
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { texts?: Record<string, { title: string; text: string }> } | null) => live && setState({ key, texts: d?.texts ?? {} }))
      .catch(() => live && setState({ key, texts: {} }))
    return () => { live = false }
  }, [matchId, key, enabled])
  return state?.texts ?? null
}

/** The recap of the audience, language and side (per text lens, not per player). */
export function useRecap(matchId: string, p: Profile, enabled: boolean) {
  const [state, setState] = useState<{ key: string; recap: Recap | null } | null>(null)
  const key = `${p.lens}|${p.lang}|${p.club}`
  useEffect(() => {
    if (!enabled) return
    let live = true
    getRecap(matchId, p.lens, p.lang, p.club).then((r) => live && setState({ key, recap: r })).catch(() => live && setState({ key, recap: null }))
    return () => { live = false }
  }, [matchId, key, enabled, p.lens, p.lang, p.club])
  return { recap: state?.key === key ? state.recap : null, loading: state?.key !== key }
}

/** Who wrote a fan text: the Supporter agent (passed the contract and the Fan judge) or the fallback line of data. */
type FanSource = 'agent' | 'fallback'
/** What the reader feels about a moment (personalize/domain/fan_perspective.py). */
export type FanStance = 'celebrate' | 'suffer' | 'anguish' | 'relief' | 'frustration' | 'blame_ours' | 'scare' | 'gloat' | 'taunt' | 'dominate'
  | 'under_siege' | 'uplift' | 'worry' | 'show_off' | 'humiliation' | 'admire' | 'fear' | 'enjoy' | 'wary' | 'roar' | 'dismay' | 'thrill'
/** One fact of the fan view. A "moment" holds the video; a "reaction" is a line of the live feed. */
export interface FanMoment {
  fact_id: string; kind: 'goal' | 'miss' | 'save' | 'mistake' | 'pinned' | 'turn' | 'move' | 'pass' | 'carry' | 'tackle' | 'sprint'
  tier: 'moment' | 'reaction'; stance: FanStance
  t_s: number; minute: number; team: Side; players: string[]; title: string; text: string; source: FanSource
}
export interface FanRating { player_id: string; name: string; team: Side; band: number; label: string; line: string; source: FanSource }
export interface FanAward { award: 'engine' | 'fastest' | 'sprinter' | 'playmaker' | 'rocket'; title: string; player_id: string; name: string; team: Side; stat: string; line: string; source: FanSource }
/** personalize/fan/<lang>_<club>.json: what a supporter reads. */
export interface FanView {
  lang: Lang; club: Club
  /** Seconds a moment card stays on the video. */
  card_s: number
  moments: FanMoment[]
  verdict: { headline: string; text: string; result: 'win' | 'loss' | 'draw' | 'decided'; winner: Side | null; deserved: boolean | null; source: FanSource }
  ratings: FanRating[]
  awards: FanAward[]
  /** For a reader who follows a player: player_id -> fact_id -> his line about that moment. */
  player_lines: Record<string, Record<string, string>>
  ask_examples: string[]
  sources: { agent: number; fallback: number; revised: number }
}

/** The fan view of the language and club; null while it loads or when the match has none (older matches). */
export function useFanView(matchId: string, lang: Lang, club: Club, enabled: boolean): FanView | null {
  const [state, setState] = useState<{ key: string; view: FanView | null } | null>(null)
  const key = `${matchId}|${lang}|${club}`
  useEffect(() => {
    if (!enabled) return
    let live = true
    fileJson<FanView>(matchId, `personalize/fan/${lang}_${club}.json`).then((v) => live && setState({ key, view: v })).catch(() => live && setState({ key, view: null }))
    return () => { live = false }
  }, [matchId, key, lang, club, enabled])
  return state?.key === key ? state.view : null
}

/** One broadcast graphic of render/broadcast/rundown.json: on air from t_in to t_out (video seconds) in its slot of the L-bar. */
export interface BroadcastGraphic {
  id: string; type: 'goal' | 'shot' | 'pass_quality' | 'carry' | 'player_id' | 'milestone'; slot: 'bar' | 'side'
  t_in: number; t_out: number; clock_s: number | null; team: Side; player_id: string | null; data: Record<string, unknown>
}
export interface Rundown { rundown_version: number; match_id: string; graphics: BroadcastGraphic[] }
/** personalize/studio/<lang>.json: what the studio presenter reads at full time, each segment linked to its play. */
export interface StudioScript {
  lang: Lang; opening: string; closing: string; source: 'agent' | 'mixed' | 'fallback'
  segments: { fact_id: string; kind: string; t_s: number; minute: number; team: Side; text: string }[]
}

/** A match file that depends only on the key; null while it loads or when the match has none (older matches). */
function useMatchFile<T>(matchId: string, name: string, enabled: boolean): T | null {
  const [state, setState] = useState<{ key: string; v: T | null } | null>(null)
  const key = `${matchId}|${name}`
  useEffect(() => {
    if (!enabled) return
    let live = true
    fileJson<T>(matchId, name).then((v) => live && setState({ key, v })).catch(() => live && setState({ key, v: null }))
    return () => { live = false }
  }, [matchId, name, key, enabled])
  return state?.key === key ? state.v : null
}
export const useRundown = (matchId: string, enabled: boolean) => useMatchFile<Rundown>(matchId, 'render/broadcast/rundown.json', enabled)
export const useReels = (matchId: string, enabled: boolean) => useMatchFile<ReelManifest>(matchId, 'render/reels/manifest.json', enabled)
/** personalize/fan/facts.json: the match's verdict (verdict.figure is the star player). */
export const useFanFacts = (matchId: string, enabled: boolean) => useMatchFile<{ verdict: { figure: string | null } }>(matchId, 'personalize/fan/facts.json', enabled)
export const useStudio = (matchId: string, lang: Lang, enabled: boolean) => useMatchFile<StudioScript>(matchId, `personalize/studio/${lang}.json`, enabled)

/** tracking.jsonl, once: the match clock of the score bug and the radar of the Stats tab. */
export function useTracking(matchId: string): TrackingFrame[] {
  const [frames, setFrames] = useState<TrackingFrame[]>([])
  useEffect(() => {
    if (MOCK) return
    let live = true
    fetch(matchFileUrl(matchId, 'tracking.jsonl'))
      .then((r) => (r.ok ? r.text() : ''))
      .then((t) => live && setFrames(t.split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l) as TrackingFrame)))
      .catch(() => {})
    return () => { live = false }
  }, [matchId])
  return frames
}

/** The /matches row of this match (library_id tells a template from a generated match). */
export function useSummary(matchId: string): MatchSummary | null {
  const [s, setS] = useState<MatchSummary | null>(null)
  useEffect(() => {
    let live = true
    listMatches().then((l) => live && setS(l.find((m) => m.match_id === matchId) ?? null)).catch(() => {})
    return () => { live = false }
  }, [matchId])
  return s
}

/** GET /models, once. Empty until it arrives (or if it fails): the cards then show the model name without numbers. */
export function useModels(): ModelCard[] {
  const [models, setModels] = useState<ModelCard[]>([])
  useEffect(() => {
    let live = true
    getModels().then((r) => live && setModels(r.models)).catch(() => {})
    return () => { live = false }
  }, [])
  return models
}

/** How many of the texts of a run came from the agent and how many from the fallback. */
export interface Split { agent: number; fallback: number; files: number }
/** The files that tell how a match was made. Every part is null when its file is missing. */
export interface RunInfo {
  job: JobStatus | null
  interpretMeta: { weights?: { momentum?: Record<string, number> }; thresholds?: { sprint_speed_m_s?: number; sprint_min_s?: number } } | null
  explainMeta: { text_sources?: { agent?: number; template?: number } } | null
  tools: string[] | null
  sequences: number | null
  variants: Split | null
  recaps: Split | null
  plans: Split | null
  heatmaps: number | null
  clips: number | null
}

const fileJson = <T,>(matchId: string, name: string): Promise<T | null> =>
  fetch(matchFileUrl(matchId, name)).then((r) => (r.ok ? (r.json() as Promise<T>) : null)).catch(() => null)
const fileLines = (matchId: string, name: string): Promise<string[] | null> =>
  fetch(matchFileUrl(matchId, name)).then((r) => (r.ok ? r.text() : null)).then((t) => (t === null ? null : t.split('\n').filter((l) => l.trim()))).catch(() => null)

/** Sums `pick` over the files that exist; null when none does. */
async function split(matchId: string, names: string[], pick: (d: Record<string, unknown>) => [number, number]): Promise<Split | null> {
  const all = (await Promise.all(names.map((n) => fileJson<Record<string, unknown>>(matchId, n)))).filter((d): d is Record<string, unknown> => d !== null)
  if (!all.length) return null
  return all.reduce<Split>((s, d) => { const [a, f] = pick(d); return { agent: s.agent + a, fallback: s.fallback + f, files: s.files + 1 } }, { agent: 0, fallback: 0, files: 0 })
}

const TEXT_LENSES = ['analyst', 'fan', 'first_match']
const PLAN_LENSES = ['analyst', 'fan', 'first_match', 'broadcast']
const grid = (lenses: string[], ext: (l: string, lang: string, club: string) => string) =>
  lenses.flatMap((l) => ['en', 'es'].flatMap((lang) => ['neutral', 'home', 'away'].map((c) => ext(l, lang, c))))

/** Loads the run files once `enabled` (the How drawer or a concept card opened). Mock mode has no files: everything stays null. */
export function useRunInfo(matchId: string, enabled: boolean): RunInfo | null {
  const [info, setInfo] = useState<RunInfo | null>(null)
  useEffect(() => {
    if (!enabled || info) return
    if (MOCK) { setInfo({ job: null, interpretMeta: null, explainMeta: null, tools: null, sequences: null, variants: null, recaps: null, plans: null, heatmaps: null, clips: null }); return }
    let live = true
    Promise.all([
      getJob(matchId).catch(() => null),
      fileJson<NonNullable<RunInfo['interpretMeta']>>(matchId, 'interpret/meta.json'),
      fileJson<NonNullable<RunInfo['explainMeta']>>(matchId, 'explain/meta.json'),
      fileLines(matchId, 'interpret/agents_log.jsonl'),
      fileLines(matchId, 'interpret/sequences.jsonl'),
      split(matchId, grid(TEXT_LENSES, (l, lang, c) => `personalize/variants/${l}_${lang}_${c}.json`), (d) => {
        const s = (d.sources ?? {}) as Record<string, number>
        return [s.agent ?? 0, s.template ?? 0]
      }),
      split(matchId, grid(TEXT_LENSES, (l, lang, c) => `personalize/recaps/${l}_${lang}_${c}.json`), (d) => (d.source === 'agent' ? [1, 0] : [0, 1])),
      split(matchId, PLAN_LENSES.flatMap((l) => ['neutral', 'home', 'away'].map((c) => `render/plans/${l}_${c}.json`)), (d) => (d.source === 'agent' ? [1, 0] : [0, 1])),
      getHeatmaps(matchId).catch(() => null),
      fileJson<ReelManifest>(matchId, 'render/reels/manifest.json'),
    ]).then(([job, interpretMeta, explainMeta, log, seqs, variants, recaps, plans, heat, clips]) => {
      if (!live) return
      const tools = log ? log.flatMap((l) => { try { return [(JSON.parse(l) as { tool: string }).tool] } catch { return [] } }) : null
      setInfo({ job, interpretMeta, explainMeta, tools, sequences: seqs ? seqs.length : null, variants, recaps, plans, heatmaps: heat ? Object.keys(heat.players).length : null, clips: clips ? clips.reels.length : null })
    })
    return () => { live = false }
  }, [matchId, enabled, info])
  return info
}
