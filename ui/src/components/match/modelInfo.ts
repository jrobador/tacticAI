// Plain-language text of the three models, built from the numbers of GET /models (nothing typed in by hand except the wording).
import type { ModelCard } from '@/api/types'

export type ModelId = 'xg_v1' | 'xpass_v1' | 'vaep_v1'

const INFO: Record<ModelId, { name: string; what: string; noun: string }> = {
  xg_v1: { name: 'xG', what: 'Chance that a shot is scored, from 0 to 1.', noun: 'shots' },
  xpass_v1: { name: 'xPass', what: 'Chance that a pass reaches a teammate, from 0 to 1. Pass difficulty is 1 − xPass.', noun: 'passes' },
  vaep_v1: { name: 'VAEP (goals added)', what: "How much an action changed the team's chances.", noun: 'actions' },
}

/** Label of a model input; an input without a label is derived from another one (log, square) and is left out. */
const FEATURE: Record<string, string> = {
  dist_goal_center_m: 'Distance to goal', visible_goal_angle_deg: 'Visible goal angle', defenders_in_cone: 'Defenders in the shooting cone',
  nearest_defender_m: 'Nearest defender', defenders_within_3m: 'Defenders within 3 m', gk_dist_to_shot_line_m: 'Keeper distance to the shot line',
  gk_off_line_m: 'Keeper off his line', header: 'Header',
  length_m: 'Length', progressive_m: 'Forward gain', start_x_att: 'Start position', passer_pressure: 'Pressure on the passer',
  opponents_near_line: 'Opponents near the passing line', nearest_opponent_to_receiver_m: 'Nearest opponent to the receiver', lines_broken: 'Lines broken',
}
/** The VAEP inputs are the last three actions plus the game state (src/tacticai/interpret/domain/vaep.py FEATURES). */
const VAEP_INPUTS = ['Type of the last 3 actions', 'Success', 'Start and end position', 'Distance and angle to goal', 'Same team', 'Seconds', 'Score difference', 'xG']

export const inputLabels = (c: ModelCard): string[] => (c.id === 'vaep_v1' ? VAEP_INPUTS : c.features.map((f) => FEATURE[f]).filter((l): l is string => !!l))
const num = (n: number | null | undefined) => (n == null ? '' : n.toLocaleString('en-US'))
const auc = (n: number) => n.toFixed(3)

export interface ModelText { name: string; id: string; what: string; trained: string; score: string; inputs: string[] }
export function modelText(c: ModelCard | undefined, id: ModelId): ModelText {
  const i = INFO[id]
  if (!c) return { name: i.name, id, what: i.what, trained: '', score: '', inputs: [] }
  const trained = c.n_train ? (id === 'vaep_v1' ? `Two models trained on ${num(c.n_train)} engine ${i.noun}` : `Trained on ${num(c.n_train)} ${i.noun} from our engine`) + (c.n_test ? `, tested on ${num(c.n_test)}.` : '.') : ''
  let score = ''
  if (id === 'vaep_v1') {
    if (c.test) score = `Test AUC ${auc(c.test.auc)} for scoring${c.concedes?.test ? ` and ${auc(c.concedes.test.auc)} for conceding` : ''}.`
  } else if (c.test) {
    const alone = (c.baseline?.features ?? []).map((f) => (FEATURE[f] ?? f).toLowerCase())
    score = `Test AUC ${auc(c.test.auc)}${c.baseline ? `, against ${auc(c.baseline.auc)} for ${alone.join(' and ')} alone` : ''}.`
  }
  return { name: i.name, id, what: i.what, trained, score, inputs: inputLabels(c) }
}

export const MODEL_NOTE = 'Trained on our engine, so these numbers are not calibrated to real football.'
