// The 13 concept cards. The wording follows the prototype; every number is read from the match files or GET /models,
// and the rules were checked against src/tacticai/{interpret,explain,personalize}.
import type { Insight, MatchBundle, ModelCard } from '@/api/types'
import { PHASE_LABEL, mmss } from '@/lib/format'
import { fmtMetric, unitLabel } from '@/lib/overlays'
import type { RunInfo } from './data'
import { AUDIENCE_NAME, AUDIENCE_RULE, CLUB_BONUS, PLAYER_BONUS, kindLabel, windowAt, type ConceptKey, type Det, type Profile } from './model'
import { modelText, type ModelId } from './modelInfo'

/** What the card reads. `moment` is the open moment or the one on screen; null between moments. */
export interface Env {
  bundle: MatchBundle
  models: ModelCard[]
  run: RunInfo | null
  time: number
  moment: Insight | null
  det: Det | null
  profile: Profile
  /** Moments the current audience shows (from /overlays) and all the moments of the match. */
  shown: number | null
  moments: Insight[]
  /** library_id of the match; null for a generated one. */
  library: boolean | null
}

export interface Concept {
  term: string
  model?: ModelId
  what: (e: Env) => string
  how: (e: Env) => string[]
}

const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1)
const modelOf = (e: Env, id: ModelId) => modelText(e.models.find((m) => m.id === id), id)
const list = (xs: string[]) => xs.map(lower).join(', ')

export const CONCEPTS: Record<ConceptKey, Concept> = {
  xg: {
    term: 'xG', model: 'xg_v1',
    what: () => 'Chance that a shot is scored, from 0 to 1.',
    how: (e) => {
      const m = modelOf(e, 'xg_v1')
      return [`Logistic model on ${m.inputs.length} inputs at the moment of the shot: ${list(m.inputs)}.`, `${m.trained} ${m.score}`.trim()]
    },
  },
  xpass: {
    term: 'xPass', model: 'xpass_v1',
    what: () => 'Chance that a pass reaches a teammate, from 0 to 1. Pass difficulty is 1 − xPass.',
    how: (e) => {
      const m = modelOf(e, 'xpass_v1')
      return [`Logistic model on the pass when it is played: ${list(m.inputs)}.`, `${m.trained} ${m.score}`.trim()]
    },
  },
  vaep: {
    term: 'VAEP (goals added)', model: 'vaep_v1',
    what: () => "How much an action changed the team's chances.",
    how: (e) => [
      'For each pass, shot, tackle and interception: (chance of scoring in the next 10 actions − chance of conceding) after the action, minus the same before it.',
      "A player's VAEP is the sum, shown with its breakdown.",
      `${modelOf(e, 'vaep_v1').trained} ${modelOf(e, 'vaep_v1').score}`.trim(),
      'Carries and dribbles are not counted; goalkeepers have no rating.',
    ],
  },
  pressure: {
    term: 'Pressure index',
    what: () => 'How close opponents are to the player on the ball, from 0 to 1.',
    how: () => ['Every opponent within 5 m adds 1 − distance / 5, capped at 1.', "A team's pressure is the average while the other team has the ball; the match mean is that average over the whole clip."],
  },
  lines: {
    term: 'Lines broken',
    what: () => 'How many lines of the defending team a pass gets past.',
    how: () => ["At the moment of the pass, the defenders' positions along the pitch are grouped into up to three lines (lines that are too close are merged); we count the lines between passer and receiver."],
  },
  momentum: {
    term: 'Momentum',
    what: (e) => `Which team is on top, from −1 (${e.bundle.meta.teams.away.name}) to +1 (${e.bundle.meta.teams.home.name}).`,
    how: (e) => {
      const w = e.run?.interpretMeta?.weights?.momentum
      const x = (k: string) => (w?.[k] != null ? ` (×${w[k]})` : '')
      return [
        `${e.bundle.timeline.length} equal windows of open play.`,
        `Each window combines the home minus away difference in xG${x('xg')}, in final-third entries${x('final_third_entries')} and in possession${x('possession_share')}, squashed to −1…+1 and averaged with the windows on each side.`,
      ]
    },
  },
  importance: {
    term: 'Importance',
    what: () => 'How much a moment matters in this match, from 0 to 1.',
    how: () => [
      'The average of the factors that exist, each from 0 to 1.',
      "Rarity: share of this match's moments of the same kind that are as strong or weaker.",
      "Value: the team's VAEP during the moment, against the largest in the match.",
      'Score context: 1 if the margin before the moment is 0 or 1 goal, 0.5 if larger.',
      'Minute: match clock over 90 minutes.',
    ],
  },
  checked: {
    term: 'Checked',
    what: () => 'Every number on screen was written by code, not by the AI.',
    how: () => [
      "The check rejects a text with a digit or a number word outside a placeholder, a placeholder that is not one of the moment's metrics, or a claim such as “highest”, “first goal”, “equaliser” or “took the lead” that code did not compute.",
      'A rejected text falls back to a template.',
    ],
  },
  phase: {
    term: 'Phase',
    what: () => 'What a team was doing over a stretch of play.',
    how: () => [
      'Proposed by code with its rule.',
      'Counter: recovers the ball before the final third and gains 20 m or more within 5 s, reaching the final third or a shot.',
      'Build-up: keeps the ball in its own third until it leaves it, loses it or play stops.',
      "High press and low block: defending with the block higher or lower than the team's usual in this match.",
    ],
  },
  events: {
    term: 'Events',
    what: () => 'What happened, inferred from positions only.',
    how: () => [
      "The ball's owner is the nearest player within 1.25 m, with the ball below 1 m, for at least 3 frames.",
      'Passes, interceptions, tackles, shots, goals and set pieces follow from changes of owner, ball speed and the score.',
    ],
  },
  template: {
    term: 'Template',
    what: () => 'A situation searched and recorded in advance.',
    how: () => ['Same pipeline as a new match; it opens without waiting.'],
  },
  mode: {
    term: 'Agent / Template / Rules',
    what: () => 'Who produced this output.',
    how: () => ['Agent: a language model wrote it and the check passed.', 'Template or Rules: code produced it because no agent ran or its output was rejected.'],
  },
  audience: {
    term: 'Audience',
    what: () => 'Who the overlays and texts are made for.',
    how: () => [
      ...(['analyst', 'fan', 'first_match', 'broadcast', 'one_metric'] as const).map((l) => `${AUDIENCE_NAME[l]}: ${AUDIENCE_RULE[l].line}`),
      `Side adds ${CLUB_BONUS} to that team's moments and tells them from its side; Player focus adds ${PLAYER_BONUS} to moments with that player.`,
    ],
  },
}

export interface Here { rows: { l: string; v: string }[]; note: string }

const sgn = (v: number, d: number) => `${v < 0 ? '−' : '+'}${Math.abs(v).toFixed(d)}`
const counts = (a: number, b: number, x: string, y: string) => `${a} ${x} · ${b} ${y}`

/** The "Here" rows: real values of the moment on screen or the match. Empty rows give a hint to open a moment. */
export function conceptHere(key: ConceptKey, e: Env): Here {
  const { bundle: b, moment: mo, det, time, profile } = e
  const rows: Here['rows'] = []
  const add = (l: string, v: string) => rows.push({ l, v })
  const lab = (m: Insight) => `${kindLabel(m.kind)} · ${mmss(m.clock_s)}`
  const metric = (m: Insight | null, k: string) => (m ? m.metrics[k] : undefined)
  const so_far = b.events.map((ev, i) => ({ ev, i })).filter((x) => x.ev.t_s <= time)
  const last = (type: string) => so_far.filter((x) => x.ev.type === type).at(-1)
  const name = (id: string | null | undefined) => b.roster.players.find((p) => p.player_id === id)?.name ?? id ?? 'Unknown'
  const short = (s: 'home' | 'away') => b.meta.teams[s].short
  const sources = (xs: Insight[]) => ({ agent: xs.filter((i) => i.text.source === 'agent').length, tpl: xs.filter((i) => i.text.source !== 'agent').length })
  let note = ''

  if (key === 'xg') {
    const v = metric(mo, 'xg')
    if (mo && v) add(lab(mo), fmtMetric(v))
    const s = det?.kind === 'shot' ? { ev: b.events[det.i] } : last('shot')
    if (s?.ev && s.ev.xg != null) add(`Shot · ${name(s.ev.player_id)} · ${mmss(s.ev.clock_s)}`, s.ev.xg.toFixed(3))
  } else if (key === 'xpass') {
    const p = det?.kind === 'pass' ? { ev: b.events[det.i] } : last('pass')
    if (p?.ev && p.ev.xpass != null) {
      add(`Pass · ${name(p.ev.player_id)} → ${name(p.ev.to_player_id)}`, p.ev.xpass.toFixed(2))
      add('Pass difficulty', (p.ev.difficulty ?? 1 - p.ev.xpass).toFixed(2))
    }
  } else if (key === 'vaep') {
    const ids = det?.kind === 'player' ? [det.id] : profile.player ? [profile.player] : mo?.players.length ? mo.players : []
    const pool = ids.length ? ids : b.players.filter((p) => p.rating.value !== null).sort((x, y) => (y.rating.value ?? 0) - (x.rating.value ?? 0)).slice(0, 1).map((p) => p.player_id)
    for (const id of pool) {
      const r = b.players.find((p) => p.player_id === id)?.rating
      add(name(id), r?.value == null ? 'Not rated' : sgn(r.value, 3))
    }
  } else if (key === 'pressure') {
    if (mo) for (const [k, m] of Object.entries(mo.metrics)) if (['value', 'before', 'after'].includes(k)) add(`${lab(mo)} · ${k}`, `${fmtMetric(m)} ${unitLabel(m.unit)}`.trim())
    for (const s of ['home', 'away'] as const) {
      const v = b.teams.find((t) => t.team === s)?.pressure
      add(`Match mean · ${short(s)}`, v == null ? '—' : v.toFixed(2))
    }
  } else if (key === 'lines') {
    const v = metric(mo, 'lines_broken')
    if (mo && v) add(lab(mo), fmtMetric(v))
    const p = last('pass')
    if (p) add(`Pass · ${name(p.ev.player_id)} → ${name(p.ev.to_player_id)}`, String(p.ev.lines_broken ?? 0))
  } else if (key === 'momentum') {
    const w = b.timeline
    const i = windowAt(w, time)
    if (w[i]) add(`Window ${i + 1} of ${w.length} · now`, sgn(w[i].momentum, 2))
    add('Used for moments', 'Off until checked against video')
  } else if (key === 'importance') {
    if (mo) {
      add(lab(mo), mo.importance.value.toFixed(2))
      const f = mo.importance.factors
      add('Rarity', f.rarity.toFixed(2)); add('Value', f.value == null ? 'n/a' : f.value.toFixed(2)); add('Score context', f.score_context.toFixed(2)); add('Minute', f.minute.toFixed(2))
    }
  } else if (key === 'checked') {
    if (mo) {
      add(lab(mo), `${(`${mo.text.fact} ${mo.text.why}`.match(/\{\w+/g) ?? []).length} placeholders filled by code`)
      add('Text from', mo.text.source === 'agent' ? 'Agent' : 'Template')
    }
    const s = sources(e.moments)
    add('This match', `${s.agent} agent ${s.agent === 1 ? 'text' : 'texts'} passed · ${s.tpl} template`)
  } else if (key === 'phase') {
    const id = mo?.refs.candidate_id
    const p = (id == null ? undefined : b.phases.find((x) => x.candidate_id === id)) ?? b.phases.find((x) => x.from_t_s <= time && time <= x.until_t_s) ?? b.phases[0]
    if (p) {
      add(`${PHASE_LABEL[p.phase] ?? p.phase} · ${short(p.team)} · ${mmss(p.from_t_s)}–${mmss(p.until_t_s)}`, p.values.gain_m != null ? `${p.values.gain_m.toFixed(1)} m in ${p.values.duration_s.toFixed(1)} s` : `${p.values.duration_s.toFixed(1)} s`)
      note = `Rule: ${p.rule}.`
    }
  } else if (key === 'events') {
    add('In this clip', String(b.events.length))
    add('So far', String(so_far.length))
  } else if (key === 'template') {
    add('This match', e.library === null ? '—' : e.library ? 'Template' : 'Generated from your request')
  } else if (key === 'mode') {
    if (mo) add(`${lab(mo)} · text`, mo.text.source === 'agent' ? 'Agent' : 'Template')
    const s = sources(e.moments)
    add('Explainer texts', counts(s.agent, s.tpl, 'Agent', 'Template'))
    if (e.run?.plans) add('Overlay plans', counts(e.run.plans.agent, e.run.plans.fallback, 'Agent', 'Rules'))
  } else if (key === 'audience') {
    add(AUDIENCE_NAME[profile.lens], AUDIENCE_RULE[profile.lens].line)
    if (profile.club !== 'neutral') add('Side', `${short(profile.club)} moments +${CLUB_BONUS}`)
    if (profile.player) add('Player focus', `${name(profile.player)} moments +${PLAYER_BONUS}`)
    if (e.shown !== null) add('Shown now', `${e.shown} of ${e.moments.length} moments`)
    note = 'Switching audiences never calls a model: the agents run once per match, when it is analysed.'
  }
  if (!note && !rows.length) note = 'Open a moment to see its value here.'
  return { rows, note }
}
