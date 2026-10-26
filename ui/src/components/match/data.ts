// Data hooks of the match page. All of it comes from the API or the match files; nothing is computed from samples.
import { useEffect, useState } from 'react'
import { getClipManifest, getHeatmaps, getInsights, getJob, getModels, getOverlays, getRecap, listMatches, loadMatch, matchFileUrl, MOCK } from '@/api/client'
import type { ClipManifest, Insight, JobStatus, Lens, MatchBundle, MatchSummary, ModelCard, OverlaysResponse, Recap } from '@/api/types'
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

/** explain/insights.jsonl and render/clips/manifest.json; they only exist once Explain and Render ran (`enabled`). */
export function useExplainFiles(matchId: string, enabled: boolean) {
  const [insights, setInsights] = useState<Insight[]>([])
  const [manifest, setManifest] = useState<ClipManifest | null>(null)
  useEffect(() => {
    if (!enabled) return
    let live = true
    getInsights(matchId).then((r) => live && setInsights(r)).catch(() => {})
    getClipManifest(matchId).then((r) => live && setManifest(r)).catch(() => {})
    return () => { live = false }
  }, [matchId, enabled])
  return { insights, manifest }
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
  interpretMeta: { weights?: { momentum?: Record<string, number> } } | null
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
      getClipManifest(matchId).catch(() => null),
    ]).then(([job, interpretMeta, explainMeta, log, seqs, variants, recaps, plans, heat, clips]) => {
      if (!live) return
      const tools = log ? log.flatMap((l) => { try { return [(JSON.parse(l) as { tool: string }).tool] } catch { return [] } }) : null
      setInfo({ job, interpretMeta, explainMeta, tools, sequences: seqs ? seqs.length : null, variants, recaps, plans, heatmaps: heat ? Object.keys(heat.players).length : null, clips: clips ? clips.clips.length : null })
    })
    return () => { live = false }
  }, [matchId, enabled, info])
  return info
}
