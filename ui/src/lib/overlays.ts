import type { Insight, MetricValue, Overlay, Trail } from '@/api/types'
import { label } from '@/lib/format'

/** Seconds an overlay keeps rendering after its window, so the exit animation can play. */
export const EXIT_S = 0.4

/** Spec format per unit: integers for counts, 1 decimal for seconds, 2 decimals for probabilities and indices. */
export function fmtMetric(m: MetricValue): string {
  if (['lines', 'passes', 'entries'].includes(m.unit)) return String(Math.round(m.value))
  return m.value.toFixed(m.unit === 's' ? 1 : 2)
}
export const unitLabel = (u: string) => ({ lines: 'lines', passes: 'passes', entries: 'entries', s: 'sec' })[u] ?? u

/** Replaces {marker} with the formatted metric value; an unknown marker stays as it is. */
export const resolve = (text: string, metrics: Record<string, MetricValue>) =>
  text.replace(/\{(\w+)\}/g, (m, k: string) => (metrics[k] ? fmtMetric(metrics[k]) : m))

const METRIC_LABELS: Record<string, string> = {
  lines_broken: 'Lines broken', passes: 'Passes', duration_s: 'Duration', xg: 'Shot quality',
  before: 'Before', after: 'After', value: 'Pressure peak', match_mean: 'Match average',
  mean_momentum: 'Mean momentum', final_third_entries: 'Final-third entries',
}
export const metricLabel = (k: string) => METRIC_LABELS[k] ?? label(k)

/** Where each kind's numbers come from (Interpret outputs). */
export const SOURCE_BY_KIND: Record<string, string> = {
  lines_broken: 'Interpret: line-breaking sequence',
  pressure_spell: 'Interpret: pressure notes',
  goal_or_chance: 'Interpret: events and engine xG',
  momentum_shift: 'Interpret: momentum notes',
}
export const CLAIM_LABELS: Record<string, string> = {
  match_max: 'Highest pressure of the match for this team',
  first_goal: 'First goal of the match',
  equaliser: 'The goal that levels the match',
  go_ahead: 'The goal that puts the team ahead',
}
export const FACTOR_LABELS: Record<string, string> = {
  rarity: 'Rarity', value: 'Value (goals added)', score_context: 'Score context', minute: 'Minute',
}

/** Overlays on screen at time t: show_t_s <= t < show_t_s + duration_s (plus the exit grace). */
export const visibleOverlays = (overlays: Overlay[], t: number) =>
  overlays.filter((o) => t >= o.show_t_s && t < o.show_t_s + o.duration_s + EXIT_S)

/** The overlay the agent trail talks about: the latest one still on screen. */
export function currentOverlay(overlays: Overlay[], t: number): Overlay | null {
  const live = overlays.filter((o) => t >= o.show_t_s && t < o.show_t_s + o.duration_s)
  return live.length ? live.reduce((a, b) => (b.show_t_s >= a.show_t_s ? b : a)) : null
}

/** "Explainer wrote this · Lens adapted it · Director placed it", or "template" / "rules" when code stepped in. */
export function trailSteps(t: Trail): string[] {
  return [
    t.explainer === 'agent' ? 'Explainer wrote this' : 'Template wrote this',
    t.lens === 'agent' ? 'Lens adapted it' : 'Template adapted it',
    t.director === 'agent' ? 'Director placed it' : 'Rules placed it',
  ]
}

/** Jump targets for the "source" links of an insight: events by index, everything else at the moment itself. */
export function refLinks(ins: Insight, eventTimes: number[]): { label: string; t: number }[] {
  const out: { label: string; t: number }[] = []
  for (const i of ins.refs.event_indices ?? []) out.push({ label: `event #${i}`, t: eventTimes[i] ?? ins.t_s })
  for (const s of ins.refs.sequence_ids ?? []) out.push({ label: `sequence ${s}`, t: ins.t_s })
  if (ins.refs.note_index != null) out.push({ label: `tactical note ${ins.refs.note_index}`, t: ins.t_s })
  return out
}
