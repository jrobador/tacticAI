// Types for the HTTP API, both match packages, the library, ratings, phases.jsonl and agents.json.

export type Side = 'home' | 'away'
export type Mode = 'full_match' | 'situation'

// ---- Recipe (src/tacticai/ingest/domain/recipe.py) ----
export interface TeamPlan {
  formation: string
  style: string
  level: number
}
export interface Situation {
  start: string
  positions: Record<Side, [number, number, string][]> | null
  ball: [number, number] | null
  ball_owner: Side | null
  ends_when: string
  wanted: string[]
  template: string | null
}
export interface Recipe {
  mode: Mode
  home: TeamPlan
  away: TeamPlan
  situation: Situation | null
  seeds: number
  steps: number
  seed: number | null
}

// ---- Catalog (GET /catalog) ----
// The shape the UI expects.
export interface PitchPlayer {
  x: number // metres, absolute coordinates (home attacks +x)
  y: number
  role: string
}
export interface TemplatePreview {
  home: PitchPlayer[]
  away: PitchPlayer[]
  ball: { x: number; y: number }
}
export interface WantedPredicate {
  name: string // e.g. goal_by_team, ends_in_shot, goal_by
  takes: 'side' | 'player' | null
  description: string
}
export interface CatalogPlayer {
  name: string
  team: Side
  number: number
}
export interface Catalog {
  formations: string[]
  styles: string[]
  templates: string[]
  modes: Mode[]
  ends_when: string[]
  wanted: WantedPredicate[]
  limits: {
    seeds: { min: number; max: number }
    level: { min: number; max: number }
    steps_situation: number
  }
  template_previews: Record<string, Partial<Record<Side, TemplatePreview>>>
  examples: Recipe[]
  players: CatalogPlayer[]
}

// ---- Validation / scenario ----
export interface RecipeIssue {
  path: string
  message: string
}
export interface ValidateResponse {
  ok: boolean
  errors: RecipeIssue[]
}
export interface ScenarioResponse {
  recipe: Recipe
  summary: string
  errors: RecipeIssue[]
}

// ---- Jobs (status.json) ----
export type JobState =
  | 'queued'
  | 'searching'
  | 'rendering'
  | 'analyzing'
  | 'agents'
  | 'explaining'
  | 'personalizing'
  | 'directing'
  | 'rendering_assets'
  | 'done'
  | 'no_winner'
  | 'failed'
export interface JobStatus {
  job_id: string
  kind: 'recipe' | 'library'
  state: JobState
  progress: { done: number; total: number } | null
  match_id: string | null
  message: string | null
  failed_seeds: number
  rev: number
  updated_at: string
  stages?: Record<string, string>
  search?: { seeds: number; met: number; seed: number }
}
export interface ModelCard {
  id: string
  features: string[]
  trained_on: string | null
  n_train: number | null
  n_test: number | null
  note: string | null
  test: { n: number; goals: number; brier: number; log_loss: number; auc: number } | null
  baseline: { n: number; goals: number; brier: number; log_loss: number; auc: number; features: string[]; l2: number } | null
  /** vaep_v1 only: `test` and `baseline` above are the scoring sub-model, these are the conceding one. */
  concedes?: { test: { n: number; goals: number; brier: number; log_loss: number; auc: number } | null; baseline: { n: number; goals: number; brier: number; log_loss: number; auc: number; features: string[]; l2: number } | null }
}
export const TERMINAL_STATES: JobState[] = ['done', 'no_winner', 'failed']
export type JobRequest = { recipe: Recipe } | { library_id: string }
export type CreateJobResult =
  | { kind: 'started'; job_id: string }
  | { kind: 'existing'; match_id: string }

// ---- Library (library/index.json) ----
export interface LibraryEntry {
  entry_id: string
  title: string
  template: string
  ball_owner: Side
  wanted: string[]
  home: TeamPlan
  away: TeamPlan
  seed: number
  tracking_sha256: string
  duration_s: number
  goals: number
  shots: number
  attacker_xg: number | null
  match_id: string | null
}
export interface LibraryIndex {
  library_version: number
  code_version: string
  engine_image: string
  entries: LibraryEntry[]
}

// ---- GET /matches ----
export interface MatchSummary {
  match_id: string
  teams: Record<Side, { name: string; short: string }>
  formations: Record<Side, string>
  duration_s: number
  library_id: string | null
  /** The match the app opens on (TAI_FEATURED_MATCH or the most recent one with video). */
  featured?: boolean
}

// ---- Contract 1: match package ----
export interface MatchMeta {
  contract_version: number
  match_id: string
  source: { kind: string; camera_setup: string; detail: string }
  teams: Record<Side, { name: string; short: string }>
  pitch: { length_m: number; width_m: number }
  video: { fps: number; frames: number; width: number; height: number }
  formations: Record<Side, string>
  projection: { applies: boolean; effective_play_s: number }
  calibration: { physical_absolute: boolean }
}
export interface RosterPlayer {
  player_id: string
  team: Side
  name: string
  number: number
  role: string
}
export interface Roster {
  players: RosterPlayer[]
}
export type EventType = 'pass' | 'tackle' | 'shot' | 'goal' | 'set_piece' | 'carry'
export interface MatchEvent {
  type: EventType
  frame_index: number
  t_s: number
  clock_s: number
  period: number
  team: Side
  player_id: string | null
  x: number
  y: number
  to_player_id?: string | null
  end_x?: number
  end_y?: number
  outcome?: 'complete' | 'intercepted' | 'goal' | 'no_goal'
  intercepted_by?: string | null
  from_player_id?: string
  speed_m_s?: number
  scorer_id?: string | null
  kind?: string
  /** carry: metres and seconds the player ran with the ball. */
  distance_m?: number
  duration_s?: number
}

// ---- Contract 2: analysis package ----
export interface EnrichedEvent extends MatchEvent {
  sequence_id: number | null
  pressure: number | null
  score_before: Record<Side, number>
  length_m?: number
  progressive_m?: number
  lines_broken?: number
  xpass?: number | null
  difficulty?: number | null
  xg?: number | null
  dist_goal_center_m?: number
  visible_goal_angle_deg?: number
  defenders_in_cone?: number
  on_target?: boolean
  zone?: string
  /** vaep_v1: how much the action changed the chances of the acting team (passes, shots, tackles, interceptions). */
  vaep?: { offensive: number; defensive: number; total: number } | null
}
export interface TimelineSide {
  possession_share: number | null
  pressure: number | null
  xg: number | null
  final_third_entries: number
}
export interface TimelineWindow {
  window: number
  start_t_s: number
  end_t_s: number
  start_clock_s: number
  end_clock_s: number
  period: number
  home: TimelineSide
  away: TimelineSide
  momentum: number // never shown until reviewed against a video
}
export interface RatingBreakdown {
  item: string
  count: number
  offensive: number
  defensive: number
  points: number
}
export interface Rating {
  value: number | null
  unit?: 'goals_added'
  scope?: 'full_match'
  breakdown: RatingBreakdown[]
  reason: string | null // saves_not_validated | vaep_model_missing
}
export interface PlayerRow {
  player_id: string
  team: Side
  minutes_open_play: number
  physical: {
    distance_rank: number
    distance_percentile: number
    top_speed_rank: number
    top_speed_percentile: number
    sprints: number
  } & Record<string, number | null>
  passing: { passes: number; completed: number; completion_pct: number | null; progressive_passes: number; lines_broken: number } & Record<string, number | null>
  shooting: { shots: number; xg: number | null; goals: number } & Record<string, number | null>
  defending: { tackles: number; interceptions: number; pressures: number }
  rating: Rating
}
export interface TeamRow {
  team: Side
  possession_pct: number
  pressure: number | null
  xg: number | null
  goals: number
  sequences: number
  sequences_ending_in_shot: number
  passing: { passes: number; passes_per_min: number; passes_projected: number | null; completion_pct: number | null; progressive_passes: number; lines_broken: number }
  shooting: { shots: number; xg: number | null; goals: number }
  defending: { tackles: number; interceptions: number; pressures: number }
}
export interface QualityReport {
  camera_setup: string
  tracking_lines: number
  video_frames: number
  main_camera_share: number
  ball_observed_share: number
  players_observed_share: number
  mean_confidence: number
  gaps: number
  identity_swaps_suspected: number
  level: 'high' | 'medium' | 'low'
  notes: string[]
}
export interface TacticalNote {
  t_s: number
  until_t_s: number
  start_clock_s: number
  period: number
  team: Side
  kind: string
  text_key: string
  strength: number
  evidence: Record<string, unknown>
}
export interface PhaseCandidate {
  candidate_id: number
  phase: 'high_press' | 'low_block' | 'build_up' | 'counter'
  team: Side
  from_t_s: number
  until_t_s: number
  rule: string
  evidence: Record<string, unknown>
  values: Record<string, number>
}
export interface AgentEvidence {
  call_id: string
  path: string
  value: unknown
}
export interface AgentsFile {
  agents_version: number
  model: string
  quality: {
    level: string
    summary: string
    caveats: { text: string; evidence: AgentEvidence[] }[]
  } | null
  tactical: {
    phases: { candidate_id: number; rank: number; text: string; evidence: AgentEvidence[] }[]
    key_notes: { note_index: number; rank: number; text: string; evidence: AgentEvidence[] }[]
    summary: { text: string; evidence: AgentEvidence[] }
  } | null
}

export interface MatchBundle {
  meta: MatchMeta
  roster: Roster
  events: EnrichedEvent[]
  timeline: TimelineWindow[]
  notes: TacticalNote[]
  phases: PhaseCandidate[]
  players: PlayerRow[]
  teams: TeamRow[]
  quality: QualityReport
  agents: AgentsFile | null
}

// ---- Explain / Personalize / Render ----
export type Lens = 'analyst' | 'fan' | 'first_match' | 'broadcast' | 'one_metric'
export type Lang = 'en' | 'es'
export type Club = 'neutral' | 'home' | 'away'
export type Slot = 'bottom_left' | 'top_right' | 'bottom_right'
export type InsightKind = 'lines_broken' | 'pressure_spell' | 'goal_or_chance' | 'momentum_shift'

export interface MetricValue {
  value: number
  unit: string
}
/** Who wrote and placed an overlay: "agent" or the fallback ("template" for texts, "rules" for the Director). */
export interface Trail {
  explainer: 'agent' | 'template'
  lens: 'agent' | 'template'
  director: 'agent' | 'rules'
}
export interface Overlay {
  overlay_id: string
  insight_id: string
  show_t_s: number
  duration_s: number
  slot: Slot | null // null in the broadcast queue: it is not drawn over the video
  priority: number
  title: string
  text: string
  metrics: Record<string, MetricValue>
  trail: Trail
}
export type Metric = 'pressure' | 'xg' | 'possession' | 'goals_added'
export type Brand = 'tacticai' | 'bka-tv'
export interface MetricSeries {
  metric: Metric
  unit: string
  mode: 'windows' | 'steps'
  available: boolean
  reason: string | null
  /** windows: from_t_s..until_t_s; steps: t_s. A null value is a gap, never 0. */
  points: { from_t_s?: number; until_t_s?: number; t_s?: number; home: number | null; away: number | null }[]
}
export interface PlayerCard {
  player_id: string
  rating: Rating | null
  insight_ids: string[]
}
export interface BrandTokens {
  brand_version: number
  name: string
  colors: { background: string; foreground: string; accent: string }
  font_family: string
  logo: string
}
/** GET /matches/{id}/overlays. With available: false the other fields are absent. */
export interface OverlaysResponse {
  overlays_version?: number
  available: boolean
  reason?: string
  lens?: Lens
  lang?: Lang
  club?: Club
  player?: string | null
  metric?: Metric | null
  brand?: Brand
  director?: 'agent' | 'rules'
  overlays?: Overlay[]
  metric_series?: MetricSeries | null
  player_card?: PlayerCard | null
  brand_tokens?: BrandTokens | null
}
/** Query of /overlays. metric only travels with one_metric and brand only with broadcast. */
export interface OverlayQuery {
  lens: Lens
  lang: Lang
  club: Club
  player?: string | null
  metric?: Metric | null
  brand?: Brand | null
}

/** render/heatmaps.json: grid[i][j], i along x (-L/2 to +L/2), j along y; home attacks +x. grid null = no sample. */
export interface Heatmaps {
  heatmap_version: number
  x_bins: number
  y_bins: number
  bounds: { x: [number, number]; y: [number, number] }
  unit: string
  players: Record<string, { eligible_s: number; grid: number[][] | null }>
}
/** render/reels/manifest.json. A reel is the 9:16 video of a broadcast goal or shot, one file per language; it is ready once the video reaches `t_in`. */
export interface ReelManifest {
  reels: { graphic_id: string; type: 'goal' | 'shot'; t_in: number; player_id: string | null; files: Partial<Record<Lang, string>> }[]
  errors: { graphic_id: string | null; message: string }[]
}
/** personalize/recaps/<lens>_<lang>_<club>.json (text already resolved). */
export interface Recap {
  recap_version: number
  lens: Lens
  lang: Lang
  club: Club
  insight_ids: string[]
  text: string
  source: 'agent' | 'template'
}

/** One line of explain/insights.jsonl. text.fact and text.why keep their {markers} unresolved. */
export interface Insight {
  insight_id: string
  kind: InsightKind
  subtype: string
  team: Side
  players: string[]
  t_s: number
  until_t_s: number
  show_t_s: number
  clock_s: number
  period: number
  metrics: Record<string, MetricValue>
  refs: { note_index?: number | null; sequence_ids?: number[]; event_indices?: number[]; candidate_id?: number | null }
  claims: string[]
  importance: { value: number; factors: { rarity: number; value: number | null; score_context: number; minute: number } }
  text: { fact: string; why: string; source: 'agent' | 'template' }
  agent_context?: { ref: string; rank: number; text: string; note_index?: number; candidate_id?: number }[]
}

/** POST /matches/{id}/ask. A moment is an insight or an event; t_s, clock_s and period are resolved by the backend. */
export interface AskMoment { kind: 'insight' | 'event'; insight_id?: string; event_index?: number; t_s: number; clock_s: number; period: number }
export interface AskResponse { answer: string; values: Record<string, number>; moments: AskMoment[] }
