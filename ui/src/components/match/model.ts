// Shared types, constants and small helpers of the match page (#/matches/:id).
import type { Club, Insight, Lang, Lens, Metric, MetricValue, MatchBundle } from '@/api/types'
import { fmtMetric, resolve, unitLabel } from '@/lib/overlays'

export interface Profile { lens: Lens; lang: Lang; club: Club; player: string | null; metric: Metric }
export const DEFAULT_PROFILE: Profile = { lens: 'fan', lang: 'en', club: 'neutral', player: null, metric: 'pressure' }

/** Keys of the concept cards (prototype CONCEPTS). The card itself is built by another batch; `onConcept` opens it. */
export type ConceptKey =
  | 'xg' | 'xpass' | 'vaep' | 'pressure' | 'lines' | 'momentum' | 'importance' | 'checked' | 'phase' | 'events' | 'template' | 'mode' | 'audience'
export type OnConcept = (key: ConceptKey, e: React.MouseEvent) => void

/** What the Stats tab has open: a shot or a pass (index into events) or a player. */
export type Det = { kind: 'shot' | 'pass'; i: number } | { kind: 'player'; id: string }

export type Tab = 'moments' | 'stats' | 'onair' | 'ask'

/** One line of tracking.jsonl (only the fields the page reads). */
export interface TrackingFrame {
  frame_index: number
  t_s: number
  clock_s: number
  period: number
  ball: { x: number; y: number; z?: number }
  players: { player_id: string; x: number; y: number; role?: string; on_pitch?: boolean }[]
}

export const PRIMARY_AUDIENCES: { id: Lens; name: string }[] = [
  { id: 'analyst', name: 'Analyst' }, { id: 'fan', name: 'Fan' }, { id: 'broadcast', name: 'Broadcast' },
]
export const MORE_AUDIENCES: { id: Lens; name: string }[] = [
  { id: 'first_match', name: 'Newcomer' }, { id: 'one_metric', name: 'Stat Spotlight' },
]
export const AUDIENCE_NAME: Record<Lens, string> = {
  analyst: 'Analyst', fan: 'Fan', broadcast: 'Broadcast', first_match: 'Newcomer', one_metric: 'Stat Spotlight',
}
export const LENSES: Lens[] = ['analyst', 'fan', 'broadcast', 'first_match', 'one_metric']

/** Thresholds of src/tacticai/personalize/domain/lenses.py; the line is the text of the prototype's AUD_RULES. */
export const AUDIENCE_RULE: Record<Lens, { min: number; line: string }> = {
  analyst: { min: 0.3, line: 'moments with importance 0.3 or more, up to 3 overlays at once, every metric.' },
  fan: { min: 0.6, line: '0.6 or more, one overlay at a time, the main metric only, emotional tone.' },
  first_match: { min: 0.5, line: '0.5 or more, one at a time, explains the concept before the number.' },
  broadcast: { min: 0.3, line: '0.3 or more, a queue to approve instead of overlays, analyst text.' },
  one_metric: { min: 0.2, line: '0.2 or more, only the moments of the chosen metric, plus its strip.' },
}
export const CLUB_BONUS = 0.15
export const PLAYER_BONUS = 0.25

/** The metric options of GET /overlays (render/domain/director.py METRIC_KINDS) and the kinds each one keeps. */
export const SPOTLIGHT_METRICS: { id: Metric; label: string; kinds: string[] }[] = [
  { id: 'pressure', label: 'Pressure', kinds: ['pressure_spell'] },
  { id: 'xg', label: 'xG', kinds: ['goal_or_chance'] },
  { id: 'possession', label: 'Possession', kinds: [] },
  { id: 'goals_added', label: 'Goals added', kinds: ['lines_broken', 'goal_or_chance'] },
]

export const KIND_LABEL: Record<string, string> = {
  goal_or_chance: 'Goal or chance', lines_broken: 'Lines broken', pressure_spell: 'Pressure spell', momentum_shift: 'Momentum shift',
}
export const KIND_CONCEPT: Record<string, ConceptKey> = { goal_or_chance: 'xg', lines_broken: 'lines', pressure_spell: 'pressure' }
export const kindLabel = (kind: string) => KIND_LABEL[kind] ?? kind

/** Concept behind a metric key of an insight (the pressure keys are the same for every pressure spell). */
const METRIC_CONCEPT: Record<string, ConceptKey> = {
  xg: 'xg', lines_broken: 'lines', value: 'pressure', match_mean: 'pressure', before: 'pressure', after: 'pressure', mean_momentum: 'momentum',
}
const METRIC_NAME: Record<string, string> = {
  xg: 'xG', lines_broken: 'Lines broken', passes: 'Passes', duration_s: 'Duration', value: 'Pressure index', match_mean: 'Pressure, match mean',
  before: 'Pressure before', after: 'Pressure after', mean_momentum: 'Mean momentum',
}

/** Main metric per kind (personalize/domain/lenses.py MAIN_METRIC); the first metric when that one is absent. */
export function mainMetricKey(i: Pick<Insight, 'kind' | 'subtype' | 'metrics'> | undefined, metrics: Record<string, MetricValue>): string | null {
  const m = i && (i.kind === 'lines_broken' ? 'lines_broken' : i.kind === 'goal_or_chance' ? 'xg' : i.kind === 'pressure_spell' ? (i.subtype === 'peak' ? 'value' : 'after') : i.subtype === 'dominance' ? 'mean_momentum' : 'after')
  if (m && metrics[m]) return m
  return Object.keys(metrics)[0] ?? null
}

/** Model behind a metric of an insight, decided by the metric name (explain/domain/moments.py writes xg today; xpass and vaep names are reserved for the models of the same name). */
export const METRIC_MODEL: Record<string, string> = { xg: 'xg_v1', xpass: 'xpass_v1', xpass_difficulty: 'xpass_v1', vaep: 'vaep_v1', goals_added: 'vaep_v1' }

/** Index of the timeline window that holds video time t (the first one before the file starts). */
export const windowAt = (w: { start_t_s: number }[], t: number) => Math.max(0, w.filter((x) => x.start_t_s <= t).length - 1)

export interface Num { key: string; txt: string; u: string; concept: ConceptKey | null }
/** A metric as shown on a card: value (scaled by k for the count-up), its name and the concept behind it. */
export function numOf(key: string, m: MetricValue, k = 1): Num {
  return { key, txt: fmtMetric({ value: m.value * k, unit: m.unit }), u: m.unit === '0-1' ? (METRIC_NAME[key] ?? key) : `${METRIC_NAME[key] ?? key} · ${unitLabel(m.unit)}`, concept: METRIC_CONCEPT[key] ?? null }
}

/** clamp(importance + club bonus + player bonus, 0, 1), the same priority the Director uses. */
export function priority(i: Insight, club: Club, player: string | null): number {
  const bonus = (club !== 'neutral' && i.team === club ? CLUB_BONUS : 0) + (player && i.players.includes(player) ? PLAYER_BONUS : 0)
  return Math.min(1, Math.max(0, i.importance.value + bonus))
}

/** The insight text with its {markers} filled from the metrics: fact then why. */
const stop = (t: string) => (/[.!?]$/.test(t.trim()) ? t.trim() : `${t.trim()}.`)
export const finalText = (i: Insight) => `${stop(resolve(i.text.fact, i.metrics))} ${stop(resolve(i.text.why, i.metrics))}`

/** Segments of the Explainer text: placeholders flagged so the page can draw them apart. */
export function segments(i: Insight): { raw: string; out: string; ph: boolean }[] {
  return `${stop(i.text.fact)} ${stop(i.text.why)}`.split(/(\{\w+\})/).filter(Boolean).map((p) => {
    const k = p.match(/^\{(\w+)\}$/)?.[1]
    const m = k ? i.metrics[k] : undefined
    return { raw: p, out: m ? fmtMetric(m) : p, ph: !!k }
  })
}

/** "tactical note 2 · events 4, 5 · sequence 3": where the numbers of the moment come from. */
export function refText(r: Insight['refs']): string {
  const out: string[] = []
  if (r.note_index != null) out.push(`tactical note ${r.note_index}`)
  if (r.event_indices?.length) out.push(`event${r.event_indices.length > 1 ? 's' : ''} ${r.event_indices.join(', ')}`)
  if (r.sequence_ids?.length) out.push(`sequence${r.sequence_ids.length > 1 ? 's' : ''} ${r.sequence_ids.join(', ')}`)
  return out.join(' · ')
}

export const FACTORS: [keyof Insight['importance']['factors'], string][] = [
  ['rarity', 'Rarity'], ['value', 'Value'], ['score_context', 'Score context'], ['minute', 'Minute'],
]

/** Insights the page shows: the momentum shift moments stay switched off until they are checked against video. */
export const shownInsights = (all: Insight[]) => all.filter((i) => i.kind !== 'momentum_shift').sort((a, b) => a.show_t_s - b.show_t_s)

export const playerLabel = (b: MatchBundle, id: string) => b.roster.players.find((p) => p.player_id === id)?.name ?? id
