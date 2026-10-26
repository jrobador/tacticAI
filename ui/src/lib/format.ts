import type { EnrichedEvent, PlayerRow, Rating, RosterPlayer, Side, TacticalNote } from '@/api/types'

export const DEFAULT_TEAMS: Record<Side, { name: string; short: string }> = {
  home: { name: 'Brackenford Athletic', short: 'BKA' },
  away: { name: 'Wexmoor City', short: 'WXC' },
}
/** Club crests appear only where a team is named. */
export const CREST: Record<Side, string> = { home: '/crest-bka.png', away: '/crest-wxc.png' }

export const label = (s: string) => s.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())

/** Match minute from the clock the source shows (clock_s), e.g. "45'". */
export const minute = (clock_s: number) => `${Math.floor(clock_s / 60) + 1}'`

export const mmss = (t: number) => {
  const s = Math.max(0, Math.floor(t))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export type Names = Record<string, RosterPlayer>
export const nameOf = (names: Names, id: string | null | undefined) => (id ? (names[id]?.name ?? id) : 'Unknown')

export const DASH = '—'
/** null/undefined is never shown as 0: it is an em dash. */
export const fix = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? DASH : v.toFixed(d))
export const pctText = (v: number | null | undefined, d = 1) => (v === null || v === undefined ? DASH : `${v.toFixed(d)}%`)

/** Events the timeline marks: line-breaking passes, shots with xG, goals and ball wins (spec: Linea de tiempo). */
export function isTimelineEvent(e: EnrichedEvent) {
  if (e.type === 'shot' || e.type === 'goal' || e.type === 'tackle') return true
  return e.type === 'pass' && ((e.lines_broken ?? 0) > 0 || e.outcome === 'intercepted')
}

export function eventTitle(e: EnrichedEvent, names: Names): string {
  const who = nameOf(names, e.player_id)
  switch (e.type) {
    case 'goal':
      return `Goal: ${nameOf(names, e.scorer_id ?? e.player_id)}`
    case 'shot':
      return `Shot by ${who}${e.xg != null ? ` (engine xG ${e.xg.toFixed(2)})` : ''}`
    case 'tackle':
      return `${who} wins the ball from ${nameOf(names, e.from_player_id)}`
    case 'pass':
      if (e.outcome === 'intercepted') return `${who}'s pass intercepted by ${nameOf(names, e.intercepted_by)}`
      if ((e.lines_broken ?? 0) > 0) return `${who} breaks ${e.lines_broken} line${e.lines_broken === 1 ? '' : 's'} with a pass`
      return `${who} passes${e.to_player_id ? ` to ${nameOf(names, e.to_player_id)}` : ''}`
    case 'set_piece':
      return label(e.kind ?? 'Set piece')
  }
}

export type EventKind = 'goal' | 'shot' | 'tackle' | 'pass'
export const eventKind = (e: EnrichedEvent): EventKind => (e.type === 'set_piece' ? 'pass' : e.type)

/** Tactical-note kinds that stay hidden until the momentum curve is reviewed against a video. */
const HIDDEN_NOTES = new Set(['momentum_swing', 'dominance_spell'])
export const visibleNote = (n: TacticalNote) => !HIDDEN_NOTES.has(n.kind)

export function noteText(n: TacticalNote, names: Names, teamName: string): string {
  const ev = n.evidence as Record<string, number | string | number[] | undefined>
  switch (n.kind) {
    case 'pressure_shift':
      return `${teamName} ${n.text_key === 'pressure_up' ? 'raised' : 'dropped'} its pressure from ${fix(ev.before as number)} to ${fix(ev.after as number)}`
    case 'pressure_peak':
      return `${teamName}'s highest pressure of the match (${fix(ev.value as number)} vs ${fix(ev.match_mean as number)} average)`
    case 'line_breaking_sequence':
      return `${teamName} sequence breaking ${ev.lines_broken} lines in ${ev.passes} passes`
    case 'big_chance':
      return `${teamName} ${n.text_key === 'big_chance_scored' ? 'scored' : 'missed'} a big chance (${nameOf(names, ev.player_id as string)}, engine xG ${fix(ev.xg as number)})`
    default:
      return label(n.kind)
  }
}

export const PHASE_LABEL: Record<string, string> = {
  high_press: 'High press',
  low_block: 'Low block',
  build_up: 'Build-up',
  counter: 'Counter-attack',
}

export const RATING_NOTE = 'goals added (engine)'
export function ratingView(r: Rating): { text: string; rated: boolean } {
  if (r.value !== null) return { text: `${r.value >= 0 ? '+' : ''}${r.value.toFixed(2)} ${RATING_NOTE}`, rated: true }
  // Keepers are "Not rated" (saves_not_validated); no model yet is "Not rated yet". null is never shown as 0.
  return { text: r.reason === 'vaep_model_missing' ? 'Not rated yet' : 'Not rated', rated: false }
}

/** Rated players first by value (desc); unrated ones stay out of the ranking, at the end. */
export const byRating = (a: PlayerRow, b: PlayerRow) =>
  (b.rating.value ?? Number.NEGATIVE_INFINITY) - (a.rating.value ?? Number.NEGATIVE_INFINITY)
