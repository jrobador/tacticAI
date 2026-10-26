// Hand-built fixtures shaped like the contracts. Used only when VITE_MOCK=1.
import type {
  AgentsFile,
  Catalog,
  EnrichedEvent,
  LibraryIndex,
  MatchBundle,
  MatchMeta,
  MatchSummary,
  PhaseCandidate,
  PitchPlayer,
  PlayerRow,
  QualityReport,
  Recipe,
  Roster,
  RosterPlayer,
  Side,
  TacticalNote,
  TeamRow,
  TemplatePreview,
  TimelineWindow,
} from '@/api/types'

export const MOCK_MATCH_ID = '20261023-181502-a3f1'
export const MOCK_DURATION_S = 60

const TEAMS = {
  home: { name: 'Brackenford Athletic', short: 'BKA' },
  away: { name: 'Wexmoor City', short: 'WXC' },
}

// ---------- recipes ----------
const example = (over: Partial<Recipe>): Recipe => ({
  mode: 'situation',
  home: { formation: '4-3-3', style: 'counter', level: 1 },
  away: { formation: '4-4-2', style: 'balanced', level: 1 },
  situation: {
    start: '',
    positions: null,
    ball: null,
    ball_owner: 'home',
    ends_when: 'possession_change',
    wanted: ['ends_in_shot'],
    template: 'counter',
  },
  seeds: 50,
  steps: 300,
  seed: 0,
  ...over,
})

export const EXAMPLES: Recipe[] = [
  example({
    mode: 'full_match',
    home: { formation: '4-3-3', style: 'possession', level: 1 },
    away: { formation: '5-4-1', style: 'counter', level: 0.8 },
    situation: null,
    seeds: 20,
    steps: 3000,
  }),
  example({
    home: { formation: '4-2-3-1', style: 'counter', level: 1 },
    situation: {
      start: 'counter-attack down the left that ends in a shot',
      positions: null,
      ball: [-0.3, 0.2],
      ball_owner: 'home',
      ends_when: 'possession_change',
      wanted: ['ends_in_shot'],
      template: null,
    },
  }),
  example({}),
]

// ---------- catalog ----------
// Player layouts are in each team's own frame (as in situations.py, engine units: x in -1..1, y in -0.42..0.42).
const L = 54.4
const W = 83.6
const attackers = (pts: [string, number, number][]): PitchPlayer[] => pts.map(([role, x, y]) => ({ role, x: x * L, y: y * W }))
const mirror = (ps: PitchPlayer[]): PitchPlayer[] => ps.map((p) => ({ ...p, x: -p.x, y: -p.y }))

const COUNTER_ATTACK = attackers([
  ['GK', -1, 0], ['LB', -0.45, -0.25], ['CB', -0.55, -0.08], ['CB', -0.55, 0.08], ['RB', -0.45, 0.25],
  ['DM', -0.35, 0], ['CM', -0.15, 0.02], ['CM', -0.2, -0.12], ['LM', 0.05, -0.3], ['RM', 0.05, 0.3], ['CF', 0.12, 0],
])
const COUNTER_DEFEND = attackers([
  ['GK', -1, 0], ['LB', -0.18, -0.25], ['CB', -0.22, -0.08], ['CB', -0.22, 0.08], ['RB', -0.18, 0.25],
  ['LM', 0.25, -0.28], ['CM', 0.22, -0.08], ['CM', 0.22, 0.08], ['RM', 0.25, 0.28], ['CF', 0.45, -0.05], ['CF', 0.45, 0.08],
])
const WING_ATTACK = attackers([
  ['GK', -1, 0], ['LB', -0.2, -0.25], ['CB', -0.28, -0.08], ['CB', -0.28, 0.08], ['RB', 0.1, 0.3],
  ['DM', -0.1, 0], ['CM', 0.1, -0.08], ['CM', 0.12, 0.1], ['LM', 0.25, -0.28], ['RM', 0.4, 0.35], ['CF', 0.45, 0],
])
const WING_DEFEND = attackers([
  ['GK', -1, 0], ['LB', 0.0, -0.25], ['CB', -0.05, -0.08], ['CB', -0.05, 0.08], ['RB', 0.0, 0.25],
  ['LM', 0.3, -0.28], ['CM', 0.25, -0.08], ['CM', 0.25, 0.08], ['RM', 0.3, 0.28], ['CF', 0.5, -0.05], ['CF', 0.5, 0.08],
])
const BUILD_ATTACK = attackers([
  ['GK', -0.95, 0], ['LB', -0.6, -0.3], ['CB', -0.7, -0.08], ['CB', -0.7, 0.08], ['RB', -0.6, 0.3],
  ['DM', -0.45, 0], ['CM', -0.3, -0.1], ['CM', -0.3, 0.1], ['LM', -0.1, -0.3], ['RM', -0.1, 0.3], ['CF', 0.05, 0],
])
const BUILD_DEFEND = attackers([
  ['GK', -1, 0], ['LB', -0.2, -0.25], ['CB', -0.25, -0.08], ['CB', -0.25, 0.08], ['RB', -0.2, 0.25],
  ['LM', 0.1, -0.28], ['CM', 0.08, -0.08], ['CM', 0.08, 0.08], ['RM', 0.1, 0.28], ['CF', 0.2, -0.05], ['CF', 0.2, 0.08],
])
const mirrorY = (ps: PitchPlayer[]): PitchPlayer[] => ps.map((p) => ({ ...p, y: -p.y }))

function preview(att: PitchPlayer[], def: PitchPlayer[], ball: [number, number]): Partial<Record<Side, TemplatePreview>> {
  // ball_owner home: attackers are home as drawn. ball_owner away: the away team is reflected in both axes.
  const b = { x: ball[0] * L, y: ball[1] * W }
  return {
    home: { home: att, away: mirror(def), ball: b },
    away: { home: def, away: mirror(att), ball: { x: -b.x, y: -b.y } },
  }
}

export const CATALOG: Catalog = {
  formations: ['4-4-2', '4-3-3', '4-2-3-1', '3-5-2', '3-4-3', '5-3-2', '5-4-1', '4-1-4-1'],
  styles: ['balanced', 'high_press', 'counter', 'possession'],
  templates: ['counter', 'wing_attack_right', 'wing_attack_left', 'build_up'],
  modes: ['situation', 'full_match'],
  ends_when: ['goal', 'possession_change', 'out_of_play', 'steps'],
  wanted: [
    { name: 'ends_in_shot', takes: null, description: 'Either team ends the clip with a shot' },
    { name: 'ends_in_goal', takes: null, description: 'Either team scores' },
    { name: 'goal_by_team', takes: 'side', description: 'The chosen team scores' },
    { name: 'shot_by_team', takes: 'side', description: 'The chosen team takes a shot' },
    { name: 'goal_by', takes: 'player', description: 'A specific player scores' },
    { name: 'more_pressure', takes: 'side', description: 'The chosen team presses more' },
    { name: 'more_possession', takes: 'side', description: 'The chosen team keeps the ball more' },
  ],
  limits: { seeds: { min: 1, max: 200 }, level: { min: 0.7, max: 1 }, steps_situation: 300 },
  template_previews: {
    counter: preview(COUNTER_ATTACK, COUNTER_DEFEND, [-0.13, 0.02]),
    wing_attack_right: preview(WING_ATTACK, WING_DEFEND, [0.2, 0.3]),
    wing_attack_left: preview(mirrorY(WING_ATTACK), mirrorY(WING_DEFEND), [0.2, -0.3]),
    build_up: preview(BUILD_ATTACK, BUILD_DEFEND, [-0.85, 0]),
  },
  examples: EXAMPLES,
  players: [
    { name: 'Corvane', team: 'home', number: 6 },
    { name: 'Yarrowe', team: 'home', number: 9 },
    { name: 'Larkspur', team: 'home', number: 11 },
    { name: 'Dovedale', team: 'away', number: 9 },
    { name: 'Kestrel', team: 'away', number: 10 },
  ],
}

// ---------- library ----------
const lib = (
  entry_id: string, title: string, template: string, owner: Side, goal: boolean,
  hf: string, hs: string, af: string, as: string, seed: number, dur: number, xg: number | null, match_id: string | null,
) => ({
  entry_id, title, template, ball_owner: owner,
  wanted: [`${goal ? 'goal' : 'shot'}_by_team:${owner}`],
  home: { formation: hf, style: hs, level: 1 }, away: { formation: af, style: as, level: 1 },
  seed, tracking_sha256: entry_id.padEnd(16, '0'), duration_s: dur, goals: goal ? 1 : 0, shots: goal ? 1 : 2,
  attacker_xg: xg, match_id,
})

export const LIBRARY: LibraryIndex = {
  library_version: 1,
  code_version: 'mock',
  engine_image: 'mock',
  entries: [
    lib('counter-away-goal-01', 'Wexmoor counter-attack ends in a Wexmoor goal', 'counter', 'away', true, '4-4-2', 'balanced', '4-3-3', 'counter', 1187, 9.4, 0.41, MOCK_MATCH_ID),
    lib('counter-home-goal-02', 'Brackenford counter-attack ends in a Brackenford goal', 'counter', 'home', true, '4-3-3', 'high_press', '4-2-3-1', 'balanced', 342, 8.1, 0.35, null),
    lib('wing_attack_right-home-goal-01', 'Brackenford attack down the right ends in a goal', 'wing_attack_right', 'home', true, '4-3-3', 'counter', '4-4-2', 'balanced', 77, 11.2, 0.28, null),
    lib('wing_attack_left-away-shot-03', 'Wexmoor attack down the left ends in a shot', 'wing_attack_left', 'away', false, '4-2-3-1', 'balanced', '4-2-3-1', 'counter', 910, 10.5, 0.12, null),
    lib('build_up-home-goal-07', 'Brackenford patient build-up ends in a goal', 'build_up', 'home', true, '4-4-2', 'possession', '3-5-2', 'high_press', 1203, 14.8, 0.19, null),
    lib('build_up-away-shot-04', 'Wexmoor build-up ends in a shot', 'build_up', 'away', false, '4-4-2', 'balanced', '3-4-3', 'high_press', 55, 13.0, null, null),
  ],
}

export const MATCHES: MatchSummary[] = [
  {
    match_id: MOCK_MATCH_ID,
    teams: TEAMS,
    formations: { home: '4-4-2', away: '4-3-3' },
    duration_s: MOCK_DURATION_S,
    library_id: 'counter-away-goal-01',
  },
  // The match of the spec example, with the Explain stage (see mocks/overlays.ts). The a3f1 match above has none.
  {
    match_id: '20261023-235553-f205',
    teams: TEAMS,
    formations: { home: '4-4-2', away: '4-3-3' },
    duration_s: MOCK_DURATION_S,
    library_id: null,
    featured: true,
  },
]

// ---------- the finished match ----------
export const META: MatchMeta = {
  contract_version: 1,
  match_id: MOCK_MATCH_ID,
  source: { kind: 'synthetic', camera_setup: 'synthetic', detail: 'tacticAI engine, seed 1187' },
  teams: TEAMS,
  pitch: { length_m: 108.8, width_m: 70.2 },
  video: { fps: 10, frames: MOCK_DURATION_S * 10, width: 1280, height: 720 },
  formations: { home: '4-4-2', away: '4-3-3' },
  projection: { applies: true, effective_play_s: 3300 },
  calibration: { physical_absolute: false },
}

const NAMES: Record<Side, [string, string][]> = {
  home: [['Venmere', 'GK'], ['Thornquill', 'LB'], ['Ashgrove', 'CB'], ['Pellwood', 'CB'], ['Dunmarrow', 'RB'], ['Corvane', 'LM'], ['Halbrook', 'CM'], ['Fenwick', 'CM'], ['Yarrowe', 'RM'], ['Ostley', 'CF'], ['Larkspur', 'CF']],
  away: [['Quillon', 'GK'], ['Brindle', 'LB'], ['Hartigan', 'CB'], ['Sedgemoor', 'CB'], ['Trevane', 'RB'], ['Eldermere', 'DM'], ['Wrenfield', 'CM'], ['Calloway', 'CM'], ['Dovedale', 'LM'], ['Kestrel', 'CF'], ['Ironsby', 'RM']],
}
const NUMBERS = [1, 3, 5, 4, 2, 6, 8, 10, 7, 9, 11]

const rosterPlayers: RosterPlayer[] = (['home', 'away'] as Side[]).flatMap((team) =>
  NAMES[team].map(([name, role], i) => ({
    player_id: `${team}-${String(i).padStart(2, '0')}`, team, name, number: NUMBERS[i], role,
  })),
)
export const ROSTER: Roster = { players: rosterPlayers }

const ev = (
  type: EnrichedEvent['type'], t_s: number, team: Side, player_id: string | null, extra: Partial<EnrichedEvent> = {},
): EnrichedEvent => ({
  type, frame_index: Math.round(t_s * 10), t_s, clock_s: Math.round(t_s * 18 * 10) / 10, period: 1, team, player_id,
  x: 0, y: 0, sequence_id: null, pressure: 0.2, score_before: { home: 0, away: 0 }, ...extra,
})
const after = { home: 0, away: 1 }

export const EVENTS: EnrichedEvent[] = [
  ev('set_piece', 0.4, 'away', null, { kind: 'kick_off' }),
  ev('pass', 7.5, 'away', 'away-06', { to_player_id: 'away-07', outcome: 'complete', length_m: 14, progressive_m: 9, lines_broken: 1, xpass: 0.86, difficulty: 0.14 }),
  ev('pass', 10.8, 'away', 'away-07', { to_player_id: 'away-09', outcome: 'complete', length_m: 22, progressive_m: 18, lines_broken: 2, xpass: 0.58, difficulty: 0.42 }),
  ev('tackle', 13.1, 'home', 'home-06', { from_player_id: 'away-09', zone: 'mid_third', pressure: 0.5 }),
  ev('pass', 16.4, 'home', 'home-06', { to_player_id: 'home-07', outcome: 'complete', length_m: 8, progressive_m: 3, lines_broken: 0, xpass: 0.93, difficulty: 0.07 }),
  ev('pass', 19.0, 'home', 'home-07', { to_player_id: 'home-10', outcome: 'intercepted', intercepted_by: 'away-05', length_m: 31, progressive_m: 24, lines_broken: 2, xpass: 0.31, difficulty: 0.69, pressure: 0.6 }),
  ev('shot', 21.7, 'away', 'away-09', { end_x: 54.4, end_y: 5.1, speed_m_s: 24, outcome: 'no_goal', xg: 0.08, dist_goal_center_m: 27, on_target: false }),
  ev('pass', 24.5, 'home', 'home-04', { to_player_id: 'home-08', outcome: 'complete', length_m: 18, progressive_m: 12, lines_broken: 1, xpass: 0.74, difficulty: 0.26 }),
  ev('pass', 28.2, 'away', 'away-06', { to_player_id: 'away-09', outcome: 'complete', length_m: 29, progressive_m: 27, lines_broken: 3, xpass: 0.41, difficulty: 0.59, pressure: 0.35 }),
  ev('shot', 31.0, 'away', 'away-09', { end_x: 54.4, end_y: 1.8, speed_m_s: 28, outcome: 'goal', xg: 0.41, dist_goal_center_m: 14, on_target: true }),
  ev('goal', 31.0, 'away', 'away-09', { scorer_id: 'away-09' }),
  ev('set_piece', 33.0, 'home', null, { kind: 'kick_off', score_before: after }),
  ev('pass', 38.6, 'home', 'home-07', { to_player_id: 'home-10', outcome: 'complete', length_m: 16, progressive_m: 11, lines_broken: 1, xpass: 0.8, difficulty: 0.2, score_before: after }),
  ev('shot', 42.3, 'home', 'home-10', { end_x: 54.4, end_y: -6.9, speed_m_s: 22, outcome: 'no_goal', xg: 0.22, dist_goal_center_m: 19, on_target: false, score_before: after }),
  ev('tackle', 46.0, 'home', 'home-04', { from_player_id: 'away-09', zone: 'def_third', pressure: 0.4, score_before: after }),
  ev('pass', 50.1, 'home', 'home-04', { to_player_id: 'home-08', outcome: 'complete', length_m: 26, progressive_m: 21, lines_broken: 2, xpass: 0.55, difficulty: 0.45, score_before: after }),
  ev('shot', 54.8, 'home', 'home-09', { end_x: 54.4, end_y: -2.2, speed_m_s: 30, outcome: 'goal', xg: 0.35, dist_goal_center_m: 15, on_target: true, score_before: after }),
  ev('goal', 54.8, 'home', 'home-09', { scorer_id: 'home-09', score_before: after }),
]

// 18 windows over 60 s (~3.33 s each); momentum is present in the file but the UI never reads it.
const poss = [0.4, 0.38, 0.45, 0.52, 0.6, 0.55, 0.48, 0.42, 0.36, 0.34, 0.4, 0.5, 0.58, 0.62, 0.57, 0.52, 0.66, 0.6]
const pHome = [0.31, 0.28, 0.35, 0.44, 0.52, 0.5, 0.46, 0.4, 0.33, 0.3, 0.34, 0.45, 0.55, 0.6, 0.54, 0.5, 0.62, 0.58]
const pAway = [0.48, 0.52, 0.45, 0.4, 0.36, 0.38, 0.44, 0.5, 0.57, 0.6, 0.52, 0.42, 0.36, 0.34, 0.38, 0.4, 0.3, 0.33]
const xgHome = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.22, 0, 0, 0, 0.35, 0]
const xgAway = [0, 0, 0, 0, 0, 0.08, 0, 0, 0.41, 0, 0, 0, 0, 0, 0, 0, 0, 0]
export const TIMELINE: TimelineWindow[] = poss.map((share, i) => ({
  window: i,
  start_t_s: Math.round((i * MOCK_DURATION_S) / 18 * 10) / 10,
  end_t_s: Math.round(((i + 1) * MOCK_DURATION_S) / 18 * 10) / 10,
  start_clock_s: Math.round(((i * MOCK_DURATION_S) / 18) * 18),
  end_clock_s: Math.round((((i + 1) * MOCK_DURATION_S) / 18) * 18),
  period: 1,
  home: { possession_share: share, pressure: pHome[i], xg: xgHome[i], final_third_entries: i % 4 === 0 ? 2 : 1 },
  away: { possession_share: Math.round((1 - share) * 100) / 100, pressure: pAway[i], xg: xgAway[i], final_third_entries: i % 5 === 0 ? 2 : 1 },
  momentum: Math.round((share - 0.5) * 140) / 100,
}))

export const NOTES: TacticalNote[] = [
  { t_s: 6, until_t_s: 20, start_clock_s: 108, period: 1, team: 'away', kind: 'pressure_shift', text_key: 'pressure_up', strength: 0.42,
    evidence: { timeline_windows: [0, 1, 2, 3, 4, 5], metric: 'pressure', before: 0.38, after: 0.59 } },
  { t_s: 11, until_t_s: 30, start_clock_s: 198, period: 1, team: 'away', kind: 'dominance_spell', text_key: 'dominance_spell', strength: 0.5,
    evidence: { timeline_windows: [3, 4, 5], mean_momentum: -0.5 } },
  { t_s: 27, until_t_s: 31, start_clock_s: 486, period: 1, team: 'away', kind: 'line_breaking_sequence', text_key: 'line_breaking_move', strength: 0.6,
    evidence: { sequence_ids: [4], lines_broken: 3, passes: 4, duration_s: 6.2, end_cause: 'goal', xg: 0.41 } },
  { t_s: 28, until_t_s: 31, start_clock_s: 504, period: 1, team: 'away', kind: 'big_chance', text_key: 'big_chance_scored', strength: 0.41,
    evidence: { event_indices: [9], frame_index: 310, xg: 0.41, player_id: 'away-09' } },
  { t_s: 35, until_t_s: 40, start_clock_s: 630, period: 1, team: 'home', kind: 'momentum_swing', text_key: 'momentum_to_home', strength: 0.45,
    evidence: { timeline_windows: [10, 11], metric: 'momentum', values: [-0.1, 0.35] } },
  { t_s: 40, until_t_s: 54, start_clock_s: 720, period: 1, team: 'home', kind: 'pressure_shift', text_key: 'pressure_up', strength: 0.36,
    evidence: { timeline_windows: [12, 13, 14, 15, 16, 17], metric: 'pressure', before: 0.36, after: 0.57 } },
  { t_s: 50, until_t_s: 55, start_clock_s: 900, period: 1, team: 'home', kind: 'big_chance', text_key: 'big_chance_scored', strength: 0.35,
    evidence: { event_indices: [16], frame_index: 548, xg: 0.35, player_id: 'home-09' } },
  { t_s: 52, until_t_s: 58, start_clock_s: 936, period: 1, team: 'home', kind: 'pressure_peak', text_key: 'highest_pressure_of_match', strength: 0.3,
    evidence: { timeline_windows: [16], metric: 'pressure', value: 0.62, match_mean: 0.44 } },
]

export const PHASES: PhaseCandidate[] = [
  { candidate_id: 0, phase: 'counter', team: 'away', from_t_s: 24.5, until_t_s: 31.0,
    rule: 'recovery at start_xa < L/6, +20 m in <= 5 s, reached final third',
    evidence: { event_indices: [8, 9], sequence_ids: [4], frame_ranges: [[245, 310]] }, values: { gain_m: 31.4, duration_s: 4.7 } },
  { candidate_id: 1, phase: 'build_up', team: 'home', from_t_s: 34, until_t_s: 42.3,
    rule: 'own-third possession with at least 4 passes before crossing the halfway line',
    evidence: { event_indices: [12, 13], sequence_ids: [6], frame_ranges: [[340, 423]] }, values: { passes: 4, duration_s: 8.3 } },
  { candidate_id: 2, phase: 'counter', team: 'home', from_t_s: 46, until_t_s: 54.8,
    rule: 'recovery at start_xa < L/6, +20 m in <= 5 s, reached final third',
    evidence: { event_indices: [14, 16], sequence_ids: [8], frame_ranges: [[460, 548]] }, values: { gain_m: 38.2, duration_s: 4.9 } },
]

// (rating value, passes, completed, shots, xg, goals, tackles, interceptions, rank, percentile) per outfield player; GK rows are null-rated
const STATS: Record<string, [number | null, number, number, number, number, number, number, number]> = {
  'home-01': [0.02, 9, 7, 0, 0, 0, 1, 0], 'home-02': [0.03, 8, 7, 0, 0, 0, 2, 1], 'home-03': [0.01, 7, 6, 0, 0, 0, 1, 1],
  'home-04': [0.09, 11, 10, 0, 0, 0, 2, 1], 'home-05': [0.05, 14, 12, 0, 0, 0, 1, 0], 'home-06': [0.07, 12, 11, 0, 0, 0, 2, 0],
  'home-07': [0.11, 13, 11, 0, 0, 0, 0, 0], 'home-08': [0.06, 10, 9, 0, 0, 0, 0, 0], 'home-09': [0.21, 6, 5, 1, 0.35, 1, 0, 0],
  'home-10': [-0.02, 7, 5, 1, 0.22, 0, 0, 0],
  'away-01': [0.01, 8, 7, 0, 0, 0, 1, 0], 'away-02': [0.02, 7, 6, 0, 0, 0, 1, 1], 'away-03': [0.0, 6, 5, 0, 0, 0, 1, 0],
  'away-04': [0.04, 7, 6, 0, 0, 0, 1, 1], 'away-05': [0.06, 9, 8, 0, 0, 0, 0, 1], 'away-06': [0.12, 10, 9, 0, 0, 0, 0, 0],
  'away-07': [0.08, 9, 8, 0, 0, 0, 0, 0], 'away-08': [0.05, 8, 7, 0, 0, 0, 0, 0], 'away-09': [0.34, 6, 5, 2, 0.49, 1, 0, 0],
  'away-10': [0.04, 7, 6, 0, 0, 0, 1, 0],
}

function playerRow(p: RosterPlayer, i: number): PlayerRow {
  const s = STATS[p.player_id]
  const gk = p.role === 'GK'
  const [v, passes, done, shots, xg, goals, tk, ic] = s ?? [null, 5, 4, 0, 0, 0, 0, 0]
  const rated = !gk && v !== null
  const offensive = rated ? Math.round(v * 0.85 * 1000) / 1000 : 0
  const breakdown = rated
    ? [
        { item: 'pass', count: passes, offensive: Math.round(v * 0.45 * 1000) / 1000, defensive: 0.005, points: Math.round(v * 0.45 * 1000) / 1000 + 0.005 },
        ...(shots ? [{ item: 'shot', count: shots, offensive: Math.round(v * 0.4 * 1000) / 1000, defensive: 0, points: Math.round(v * 0.4 * 1000) / 1000 }] : []),
        ...(tk ? [{ item: 'tackle', count: tk, offensive: 0.004, defensive: Math.round((v - offensive / 2) * 100) / 100 / 10, points: 0.02 }] : []),
      ]
    : []
  return {
    player_id: p.player_id, team: p.team, minutes_open_play: 4.9,
    physical: { distance_m: 1100 + i * 20, distance_rank: 1 + ((i * 7) % 22), distance_percentile: 100 - ((i * 13) % 100), top_speed_m_s: 7.2, top_speed_rank: 1 + ((i * 5) % 22), top_speed_percentile: 100 - ((i * 9) % 100), sprints: i % 6 },
    passing: { passes, completed: done, completion_pct: passes ? Math.round((done / passes) * 1000) / 10 : 0, progressive_passes: Math.round(passes / 4), lines_broken: Math.round(passes / 5) },
    shooting: { shots, xg: shots ? xg : 0, goals },
    defending: { tackles: tk, interceptions: ic, pressures: 6 + (i % 9) },
    rating: gk
      ? { value: null, breakdown: [], reason: 'saves_not_validated' }
      : { value: rated ? v : null, unit: 'goals_added', scope: 'full_match', breakdown, reason: null },
  }
}
export const PLAYERS: PlayerRow[] = rosterPlayers.map(playerRow)

export const TEAMS_STATS: TeamRow[] = [
  { team: 'home', possession_pct: 51.4, pressure: 0.44, xg: 0.57, goals: 1, sequences: 9, sequences_ending_in_shot: 2,
    passing: { passes: 97, passes_per_min: 19.8, passes_projected: 1090, completion_pct: 85.6, progressive_passes: 23, lines_broken: 17 },
    shooting: { shots: 2, xg: 0.57, goals: 1 }, defending: { tackles: 8, interceptions: 4, pressures: 71 } },
  { team: 'away', possession_pct: 48.6, pressure: 0.46, xg: 0.49, goals: 1, sequences: 8, sequences_ending_in_shot: 2,
    passing: { passes: 90, passes_per_min: 18.4, passes_projected: 1012, completion_pct: 83.3, progressive_passes: 21, lines_broken: 16 },
    shooting: { shots: 2, xg: 0.49, goals: 1 }, defending: { tackles: 6, interceptions: 5, pressures: 66 } },
]

export const QUALITY: QualityReport = {
  camera_setup: 'synthetic', tracking_lines: 600, video_frames: 600, main_camera_share: 1, ball_observed_share: 1,
  players_observed_share: 1, mean_confidence: 1, gaps: 0, identity_swaps_suspected: 0, level: 'high',
  notes: ['Synthetic tracking is exact ground truth; every value was observed.'],
}

export const AGENTS: AgentsFile = {
  agents_version: 1,
  model: 'gpt-4.1-mini',
  quality: null,
  tactical: {
    phases: [
      { candidate_id: 0, rank: 1, text: 'Wexmoor won the ball in midfield and covered 31.4 m in 4.7 s, reaching the final third before Brackenford could recover its shape.',
        evidence: [{ call_id: 'c5', path: 'results.candidates[0].values.gain_m', value: 31.4 }, { call_id: 'c5', path: 'results.candidates[0].values.duration_s', value: 4.7 }] },
      { candidate_id: 2, rank: 2, text: 'Brackenford answered with its own counter: 38.2 m in 4.9 s after a tackle in its defensive third.',
        evidence: [{ call_id: 'c5', path: 'results.candidates[2].values.gain_m', value: 38.2 }] },
    ],
    key_notes: [
      { note_index: 3, rank: 1, text: 'Wexmoor scored from a 0.41 engine xG chance, the biggest of the clip.', evidence: [{ call_id: 'c7', path: 'results.notes[3].evidence.xg', value: 0.41 }] },
      { note_index: 5, rank: 2, text: 'Brackenford raised its pressure from 0.36 to 0.57 after conceding.', evidence: [{ call_id: 'c7', path: 'results.notes[5].evidence.after', value: 0.57 }] },
    ],
    summary: {
      text: 'An even clip decided by transitions: Wexmoor broke three lines on the move that led to its goal, and Brackenford equalised from a counter after raising its pressure.',
      evidence: [{ call_id: 'c7', path: 'results.notes[2].evidence.lines_broken', value: 3 }],
    },
  },
}

export const MOCK_BUNDLE: MatchBundle = {
  meta: META, roster: ROSTER, events: EVENTS, timeline: TIMELINE, notes: NOTES, phases: PHASES,
  players: PLAYERS, teams: TEAMS_STATS, quality: QUALITY, agents: AGENTS,
}
