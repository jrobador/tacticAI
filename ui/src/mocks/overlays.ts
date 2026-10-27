// Fixtures for /overlays and explain/insights.jsonl, built from the spec example (match 20261023-235553-f205).
// The other mock match (a3f1) has no Explain stage: it answers available: false.
import type { Brand, BrandTokens, Club, Heatmaps, Insight, Lang, Lens, Metric, MetricSeries, MetricValue, Overlay, OverlayQuery, OverlaysResponse, Recap } from '@/api/types'
import { resolve } from '@/lib/overlays'
import { PLAYERS, ROSTER, TIMELINE } from './fixtures'

export const FEATURED_MOCK_ID = '20261023-235553-f205'

const m = (value: number, unit: string): MetricValue => ({ value, unit })
type Seed = Pick<Insight, 'insight_id' | 'kind' | 'subtype' | 'team' | 'show_t_s' | 'metrics' | 'importance' | 'text'> & Partial<Insight>
const ins = (p: Seed): Insight => ({
  players: [], t_s: p.show_t_s, until_t_s: p.show_t_s, clock_s: Math.round(p.show_t_s * 18 * 100) / 100, period: 1,
  refs: {}, claims: [], ...p,
})

export const INSIGHTS: Insight[] = [
  ins({
    insight_id: 'i000', kind: 'pressure_spell', subtype: 'shift_up', team: 'away', show_t_s: 10.3,
    metrics: { before: m(0.31, '0-1'), after: m(0.52, '0-1') },
    refs: { note_index: 0 },
    importance: { value: 0.41, factors: { rarity: 0.5, value: 0.2, score_context: 1, minute: 0.02 } },
    text: { fact: 'Wexmoor raised their pressure from {before} to {after}', why: 'They started winning the ball higher up the pitch', source: 'template' },
  }),
  ins({
    insight_id: 'i001', kind: 'lines_broken', subtype: 'goal', team: 'home', players: ['home-10', 'home-06', 'home-09'],
    t_s: 13.5, until_t_s: 24.3, show_t_s: 24.3, clock_s: 137.18,
    metrics: { lines_broken: m(2, 'lines'), passes: m(2, 'passes'), duration_s: m(9.7, 's'), xg: m(0.34, 'engine xG') },
    refs: { note_index: 1, sequence_ids: [3], event_indices: [7], candidate_id: 0 },
    importance: { value: 0.656, factors: { rarity: 1, value: 0.6, score_context: 1, minute: 0.025 } },
    text: { fact: 'Brackenford broke {lines_broken} lines in {passes} passes', why: 'The move ended in a goal', source: 'template' },
    agent_context: [{ ref: 'key_note', note_index: 1, rank: 1, text: 'Brackenford play through the middle after winning the ball.' }],
  }),
  ins({
    insight_id: 'i002', kind: 'goal_or_chance', subtype: 'goal', team: 'home', players: ['home-09'],
    t_s: 21, until_t_s: 24.3, show_t_s: 24.3, clock_s: 137.18,
    metrics: { xg: m(0.34, 'engine xG') },
    refs: { note_index: 1, event_indices: [6, 7] },
    claims: ['first_goal'],
    importance: { value: 0.93, factors: { rarity: 1, value: 0.84, score_context: 1, minute: 0.025 } },
    text: { fact: 'Larkspur scores from {xg} engine xG', why: 'The opening goal of the match', source: 'template' },
  }),
  ins({
    insight_id: 'i003', kind: 'pressure_spell', subtype: 'peak', team: 'away', show_t_s: 41,
    metrics: { value: m(0.6, '0-1'), match_mean: m(0.42, '0-1') },
    refs: { note_index: 2 },
    claims: ['match_max'],
    importance: { value: 0.52, factors: { rarity: 0.5, value: 0.3, score_context: 0.5, minute: 0.03 } },
    text: { fact: 'Wexmoor reached {value} pressure, their highest of the match', why: 'Their match average is {match_mean}', source: 'template' },
  }),
]

type Text = { title: string; text: string }
type TextLens = 'analyst' | 'fan'
const TEXTS: Record<Lang, Record<string, Record<TextLens, Text>>> = {
  en: {
    i000: {
      analyst: { title: 'Pressure up: {before} to {after}', text: 'Wexmoor pressing intensity rises from {before} to {after} (0-1).' },
      fan: { title: 'Wexmoor squeeze higher', text: 'They are pressing much harder now.' },
    },
    i001: {
      analyst: { title: 'Sequence breaks {lines_broken} lines', text: '{passes} passes in {duration_s} s through two defensive lines, ending in a goal. Engine xG {xg}.' },
      fan: { title: 'They cut through {lines_broken} lines!', text: 'Brackenford carve open the defence and finish it off.' },
    },
    i002: {
      analyst: { title: 'Goal, engine xG {xg}', text: 'Larkspur finishes the move. First goal of the match.' },
      fan: { title: 'GOAL for Brackenford!', text: 'Larkspur puts them ahead. Big moment.' },
    },
    i003: {
      analyst: { title: 'Pressure peak {value}', text: 'Wexmoor reach {value}, the match high (average {match_mean}).' },
      fan: { title: 'Wexmoor at full tilt', text: 'Their strongest pressing spell so far.' },
    },
  },
  es: {
    i000: {
      analyst: { title: 'Sube la presión: {before} a {after}', text: 'La intensidad de presión de Wexmoor pasa de {before} a {after} (0-1).' },
      fan: { title: 'Wexmoor aprieta más arriba', text: 'Ahora presionan mucho más fuerte.' },
    },
    i001: {
      analyst: { title: 'Secuencia rompe {lines_broken} líneas', text: '{passes} pases en {duration_s} s a través de dos líneas, y termina en gol. xG del motor {xg}.' },
      fan: { title: '¡Rompieron {lines_broken} líneas!', text: 'Brackenford abre la defensa y la termina.' },
    },
    i002: {
      analyst: { title: 'Gol, xG del motor {xg}', text: 'Larkspur termina la jugada. Primer gol del partido.' },
      fan: { title: '¡GOL de Brackenford!', text: 'Larkspur los pone arriba. Momento clave.' },
    },
    i003: {
      analyst: { title: 'Pico de presión {value}', text: 'Wexmoor llega a {value}, lo más alto del partido (promedio {match_mean}).' },
      fan: { title: 'Wexmoor a todo vapor', text: 'Su mejor tramo de presión hasta ahora.' },
    },
  },
}

/** Principal metric per kind (fan shows only this one). */
const MAIN = (i: Insight) => ({ lines_broken: 'lines_broken', goal_or_chance: 'xg', momentum_shift: 'after', pressure_spell: i.subtype === 'peak' ? 'value' : 'after' })[i.kind]
const THRESHOLD: Record<Lens, number> = { analyst: 0.3, fan: 0.6, first_match: 0.5, broadcast: 0.3, one_metric: 0.2 }
const PREFERRED = { lines_broken: 'bottom_left', goal_or_chance: 'bottom_left', pressure_spell: 'top_right', momentum_shift: 'top_right' } as const
const METRIC_KINDS: Record<string, Insight['kind'][]> = {
  pressure: ['pressure_spell'], xg: ['goal_or_chance'], possession: [], goals_added: ['lines_broken', 'goal_or_chance'],
}
const METRIC_UNIT: Record<string, string> = { pressure: '0-1', xg: 'engine xG', possession: '%', goals_added: 'goals_added' }

/** A tiny stand-in for the rules Director: threshold, then slots, never overlapping in time. broadcast has no slots (a queue). */
function plan(q: OverlayQuery): Overlay[] {
  const { lens, club, lang } = q
  const textLens: TextLens = lens === 'fan' || lens === 'first_match' ? 'fan' : 'analyst'
  const slots: NonNullable<Overlay['slot']>[] = lens === 'analyst' ? ['bottom_left', 'top_right', 'bottom_right'] : ['bottom_left']
  const bonus = (i: Insight) => (club !== 'neutral' && i.team === club ? 0.15 : 0) + (q.player && i.players.includes(q.player) ? 0.25 : 0)
  const kinds = lens === 'one_metric' ? METRIC_KINDS[q.metric ?? 'pressure'] : null
  const ranked = INSIGHTS.filter((i) => !kinds || kinds.includes(i.kind))
    .map((i) => ({ i, p: Math.min(1, i.importance.value + bonus(i)) }))
    .filter((x) => x.p >= THRESHOLD[lens])
    .sort((a, b) => b.p - a.p || a.i.show_t_s - b.i.show_t_s || a.i.insight_id.localeCompare(b.i.insight_id))
  const busy: Record<string, [number, number][]> = {}
  const out: Overlay[] = []
  for (const { i, p } of ranked) {
    const dur = i.kind === 'goal_or_chance' ? 8 : 6
    let slot: Overlay['slot'] = null
    if (lens !== 'broadcast') {
      const order = [PREFERRED[i.kind], ...slots].filter((s, k, a) => slots.includes(s) && a.indexOf(s) === k)
      slot = order.find((s) => !(busy[s] ?? []).some(([a, b]) => i.show_t_s < b && a < i.show_t_s + dur)) ?? null
      if (!slot) continue
      ;(busy[slot] ??= []).push([i.show_t_s, i.show_t_s + dur])
    }
    const t = TEXTS[lang][i.insight_id][textLens]
    const main = MAIN(i)
    const one = lens === 'fan' || lens === 'first_match' || lens === 'one_metric'
    out.push({
      overlay_id: '', insight_id: i.insight_id, show_t_s: i.show_t_s, duration_s: dur, slot, priority: Math.round(p * 1000) / 1000,
      title: resolve(t.title, i.metrics), text: resolve(t.text, i.metrics),
      metrics: one ? { [main]: i.metrics[main] } : i.metrics,
      trail: { explainer: 'agent', lens: 'agent', director: lens === 'one_metric' || i.insight_id === 'i003' ? 'rules' : 'agent' },
    })
  }
  return out.sort((a, b) => a.show_t_s - b.show_t_s).map((o, k) => ({ ...o, overlay_id: `o${k}` }))
}

/** Windows keep their null (a gap); goals_added steps accumulate the value of each team. */
function series(metric: Metric): MetricSeries {
  const base = { metric, unit: METRIC_UNIT[metric], reason: null, available: true }
  if (metric === 'goals_added') {
    let h = 0
    let a = 0
    const points = [{ t_s: 0, home: 0, away: 0 }]
    for (const [t, th, ta] of [[21, 0.21, 0], [24.3, 0.13, 0], [33, 0, 0.09], [47, 0.05, 0.12]] as const) {
      h += th
      a += ta
      points.push({ t_s: t, home: Math.round(h * 100) / 100, away: Math.round(a * 100) / 100 })
    }
    return { ...base, mode: 'steps', points }
  }
  const key = metric === 'possession' ? 'possession_share' : metric
  const v = (x: number | null) => (x === null ? null : metric === 'possession' ? Math.round(x * 1000) / 10 : x)
  return {
    ...base, mode: 'windows',
    points: TIMELINE.map((w) => ({ from_t_s: w.start_t_s, until_t_s: w.end_t_s, home: v(w.home[key]), away: v(w.away[key]) })),
  }
}

export const BRANDS: Record<Brand, BrandTokens> = {
  tacticai: { brand_version: 1, name: 'tacticAI', colors: { background: '#0B1020', foreground: '#F4F6FB', accent: '#2DD4BF' }, font_family: 'Inter, system-ui, sans-serif', logo: '/tacticai-logo-dark-bg.png' },
  'bka-tv': { brand_version: 1, name: 'BKA TV', colors: { background: '#1B1B3A', foreground: '#FFFFFF', accent: '#F5B700' }, font_family: 'Oswald, Impact, sans-serif', logo: '/crest-bka.png' },
}

export function overlaysFor(matchId: string, q: OverlayQuery): OverlaysResponse {
  if (matchId !== FEATURED_MOCK_ID) return { available: false, reason: 'not_enriched' }
  const metric = q.lens === 'one_metric' ? (q.metric ?? 'pressure') : null
  const player = q.player ?? null
  const rating = player ? (PLAYERS.find((p) => p.player_id === player)?.rating ?? null) : null
  return {
    overlays_version: 1, available: true, lens: q.lens, lang: q.lang, club: q.club, player, metric, brand: q.brand ?? 'tacticai',
    director: 'agent', overlays: plan(q), metric_series: metric ? series(metric) : null,
    player_card: player ? { player_id: player, rating, insight_ids: INSIGHTS.filter((i) => i.players.includes(player)).map((i) => i.insight_id) } : null,
    brand_tokens: q.lens === 'broadcast' ? BRANDS[q.brand ?? 'tacticai'] : null,
  }
}

/** 16 x 12 grid: a soft blob around a spot per role; away-10 has no sample (grid null). */
export function heatmaps(): Heatmaps {
  const spot: Record<string, [number, number]> = { GK: [-48, 0], LB: [-28, -22], RB: [-28, 22], CB: [-32, 0], DM: [-12, 0], CM: [-2, 0], LM: [8, -22], RM: [8, 22], CF: [30, 0] }
  const players: Heatmaps['players'] = {}
  for (const p of ROSTER.players) {
    if (p.player_id === 'away-10') { players[p.player_id] = { eligible_s: 0, grid: null }; continue }
    const [bx, by] = spot[p.role] ?? [0, 0]
    const sign = p.team === 'home' ? 1 : -1
    let total = 0
    const grid = Array.from({ length: 16 }, (_, i) => Array.from({ length: 12 }, (_, j) => {
      const x = -54.4 + (i + 0.5) * (108.8 / 16)
      const y = -35.1 + (j + 0.5) * (70.2 / 12)
      const v = Math.round(0.6 * Math.exp(-(((x - sign * bx) / 14) ** 2 + ((y - sign * by) / 11) ** 2)) * 1000) / 1000
      total += v
      return v
    }))
    players[p.player_id] = { eligible_s: Math.round(total * 1000) / 1000, grid }
  }
  return { heatmap_version: 1, x_bins: 16, y_bins: 12, bounds: { x: [-54.4, 54.4], y: [-35.1, 35.1] }, unit: 's', players }
}

export function recap(lens: Lens, lang: Lang, club: Club): Recap {
  const ids = INSIGHTS.filter((i) => i.importance.value >= 0.5).sort((a, b) => b.importance.value - a.importance.value).slice(0, 5).map((i) => i.insight_id)
  const text = lang === 'es'
    ? 'Brackenford abrió el marcador tras romper dos líneas, y Wexmoor respondió con su mejor tramo de presión.'
    : 'Brackenford opened the scoring after breaking two lines, and Wexmoor answered with their best pressing spell.'
  return { recap_version: 1, lens, lang, club, insight_ids: ids, text, source: 'template' }
}
