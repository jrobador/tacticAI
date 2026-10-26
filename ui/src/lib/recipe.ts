import type { Catalog, Recipe, Side, Situation } from '@/api/types'
import { DEFAULT_TEAMS, label } from './format'

export const defaultSituation = (catalog: Catalog): Situation => ({
  start: '',
  positions: null,
  ball: null,
  ball_owner: 'home',
  ends_when: 'possession_change',
  wanted: ['ends_in_shot'],
  template: catalog.templates[0] ?? null,
})

export function oneLine(r: Recipe): string {
  const t = (s: Side) => `${DEFAULT_TEAMS[s].short} ${r[s].formation} ${label(r[s].style).toLowerCase()}`
  const mode = r.mode === 'full_match' ? 'Full match' : r.situation?.template ? label(r.situation.template) : 'Custom situation'
  return `${mode} - ${t('home')} vs ${t('away')}`
}

/** Human text for a wanted predicate like "goal_by_team:away" or "goal_by:Corvane". */
export function predicateText(p: string): string {
  const [name, arg] = p.split(':')
  const what = label(name)
  if (!arg) return what
  if (arg === 'home' || arg === 'away') return `${what}: ${DEFAULT_TEAMS[arg].short}`
  return `${what}: ${arg}`
}
