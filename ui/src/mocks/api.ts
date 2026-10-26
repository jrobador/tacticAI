// Mock backend for VITE_MOCK=1. Same signatures as src/api/client.ts.
// Fake job: 12 seeds at 250 ms, then rendering, analyzing, agents, done (about 8 s).
// Rules for trying the edge cases: seeds < 5 -> no_winner; a recipe whose home style is "possession"
// with level 0.7 -> failed; text containing "503" -> /scenario 503; text containing "501" -> 501.
import { ApiError } from '@/api/client'
import type {
  AskResponse, Catalog, ClipManifest, Club, CreateJobResult, Heatmaps, Insight, Lang, Lens, Recap, JobRequest, JobStatus, LibraryIndex, MatchBundle, MatchSummary, Recipe,
  OverlayQuery, OverlaysResponse, RecipeIssue, ScenarioResponse, ValidateResponse,
} from '@/api/types'
import { TERMINAL_STATES } from '@/api/types'
import { CLIPS, heatmaps, INSIGHTS, overlaysFor, recap } from './overlays'
import { CATALOG, EXAMPLES, LIBRARY, MATCHES, MOCK_BUNDLE, MOCK_MATCH_ID } from './fixtures'

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))
const clone = <T>(v: T): T => structuredClone(v)

export async function getCatalog(): Promise<Catalog> {
  await delay(120)
  return clone(CATALOG)
}

function issues(r: Recipe): RecipeIssue[] {
  const e: RecipeIssue[] = []
  const { limits } = CATALOG
  if (!Number.isInteger(r.seeds) || r.seeds < limits.seeds.min || r.seeds > limits.seeds.max) e.push({ path: 'seeds', message: 'seeds must be an int in 1..200' })
  for (const side of ['home', 'away'] as const) {
    const t = r[side]
    if (!CATALOG.formations.includes(t.formation)) e.push({ path: `${side}.formation`, message: `unknown formation '${t.formation}'` })
    if (!CATALOG.styles.includes(t.style)) e.push({ path: `${side}.style`, message: `unknown style '${t.style}'` })
    if (!(t.level >= limits.level.min && t.level <= limits.level.max)) e.push({ path: `${side}.level`, message: 'level must be between 0.7 and 1' })
  }
  if (r.mode === 'situation') {
    const s = r.situation
    if (!s) e.push({ path: 'situation', message: 'situation is required iff mode is situation' })
    else if (s.template && !s.ball_owner) e.push({ path: 'situation.ball_owner', message: 'template needs ball_owner' })
  }
  return e
}

export async function validateRecipe(r: Recipe): Promise<ValidateResponse> {
  await delay(150)
  const errors = issues(r)
  return { ok: errors.length === 0, errors }
}

export async function draftScenario(text: string, recipe: Recipe | null): Promise<ScenarioResponse> {
  await delay(900)
  if (!text.trim()) throw new ApiError(422, 'text is empty', [{ path: 'text', message: 'text is empty' }])
  if (text.includes('501')) throw new ApiError(501, 'The scenario agent is not implemented yet')
  if (text.includes('503')) throw new ApiError(503, 'The model took longer than 20 s to answer')
  const base = clone(recipe ?? EXAMPLES[2])
  const lower = text.toLowerCase()
  if (lower.includes('pressure')) base.home.style = 'high_press'
  if (lower.includes('wexmoor') && base.situation) {
    base.situation.ball_owner = 'away'
    base.situation.wanted = ['goal_by_team:away']
  }
  if (lower.includes('goal') && base.situation) base.situation.wanted = [`goal_by_team:${base.situation.ball_owner ?? 'home'}`]
  return { recipe: base, summary: `Drafted from "${text.trim()}": ${base.home.formation} ${base.home.style} vs ${base.away.formation} ${base.away.style}.`, errors: issues(base) }
}

// ---- jobs ----
const jobs = new Map<string, { status: JobStatus; recipe: Recipe | null }>()
let counter = 0
const isTerminal = (s: JobStatus) => TERMINAL_STATES.includes(s.state)
const active = () => [...jobs.values()].find((j) => !isTerminal(j.status))

function patch(id: string, p: Partial<JobStatus>) {
  const j = jobs.get(id)!
  j.status = { ...j.status, ...p, rev: j.status.rev + 1, updated_at: new Date().toISOString() }
}

function runJob(id: string, recipe: Recipe | null) {
  const total = recipe ? recipe.seeds : 0
  const steps: (() => void)[] = []
  if (recipe) {
    const shown = Math.min(total, 12)
    for (let i = 1; i <= shown; i++) steps.push(() => patch(id, { state: 'searching', progress: { done: Math.round((i / shown) * total), total } }))
    if (total < 5) { steps.push(() => patch(id, { state: 'no_winner', message: `None of the ${total} seeds ended in a goal` })); play(steps, 250); return }
    if (recipe.home.style === 'possession' && recipe.home.level <= 0.7) { steps.push(() => patch(id, { state: 'failed', message: 'Mock failure: the engine container exited with code 3' })); play(steps, 250); return }
  }
  steps.push(() => patch(id, { state: 'rendering', progress: null }))
  steps.push(() => {}, () => {}, () => {}, () => {}, () => {}, () => {}, () => {}, () => {}) // keep "Recording" for ~2 s
  steps.push(() => patch(id, { state: 'analyzing' }), () => {}, () => {}, () => {})
  steps.push(() => patch(id, { state: 'agents' }), () => {}, () => {}, () => {})
  steps.push(() => {
    patch(id, { state: 'done', match_id: MOCK_MATCH_ID, message: null })
  })
  play(steps, 250)
}
function play(steps: (() => void)[], ms: number) {
  let i = 0
  const t = setInterval(() => {
    steps[i++]?.()
    if (i >= steps.length) clearInterval(t)
  }, ms)
}

export async function createJob(req: JobRequest): Promise<CreateJobResult> {
  await delay(200)
  if ('library_id' in req) {
    const entry = LIBRARY.entries.find((e) => e.entry_id === req.library_id)
    if (!entry) throw new ApiError(422, 'unknown library_id', [{ path: 'library_id', message: 'not in the library' }])
    if (entry.match_id) return { kind: 'existing', match_id: entry.match_id }
  } else {
    const errs = issues(req.recipe)
    if (errs.length) throw new ApiError(422, 'invalid recipe', errs)
  }
  const a = active()
  if (a) throw new ApiError(409, 'A match is already being generated', { active_job_id: a.status.job_id })
  const id = `20261023-18${String(++counter).padStart(4, '0')}-a3f1`
  const recipe = 'recipe' in req ? req.recipe : null
  jobs.set(id, {
    recipe,
    status: { job_id: id, kind: recipe ? 'recipe' : 'library', state: 'queued', progress: null, match_id: null, message: null, failed_seeds: 0, rev: 0, updated_at: new Date().toISOString() },
  })
  setTimeout(() => runJob(id, recipe), 400)
  return { kind: 'started', job_id: id }
}

export async function getJob(id: string): Promise<JobStatus> {
  const j = jobs.get(id)
  if (!j) throw new ApiError(404, 'Unknown job')
  return clone(j.status)
}

export function watchJob(id: string, onStatus: (s: JobStatus) => void, onError: (e: Error) => void): () => void {
  let last = -1
  let stopped = false
  const t = setInterval(() => {
    if (stopped) return
    const j = jobs.get(id)
    if (!j) { onError(new ApiError(404, 'Unknown job')); clearInterval(t); return }
    if (j.status.rev !== last) {
      last = j.status.rev
      onStatus(clone(j.status))
    }
    if (isTerminal(j.status)) clearInterval(t)
  }, 200)
  return () => { stopped = true; clearInterval(t) }
}

// ---- files ----
export async function listMatches(): Promise<MatchSummary[]> {
  await delay(100)
  return clone(MATCHES)
}
export async function getLibrary(): Promise<LibraryIndex> {
  await delay(100)
  return clone(LIBRARY)
}
export async function loadMatch(_id: string): Promise<MatchBundle> {
  await delay(300)
  return clone({ ...MOCK_BUNDLE, meta: { ...MOCK_BUNDLE.meta, match_id: _id } })
}

// ---- overlays / insights ----
export async function getOverlays(matchId: string, q: OverlayQuery): Promise<OverlaysResponse> {
  await delay(150)
  return clone(overlaysFor(matchId, q))
}
export async function getInsights(): Promise<Insight[]> {
  await delay(100)
  return clone(INSIGHTS)
}
export async function getHeatmaps(): Promise<Heatmaps> {
  await delay(100)
  return heatmaps()
}
export async function getClipManifest(): Promise<ClipManifest> {
  await delay(60)
  return clone(CLIPS)
}
export async function getRecap(lens: Lens, lang: Lang, club: Club): Promise<Recap> {
  await delay(100)
  return recap(lens, lang, club)
}

/** Mock Q&A: "501", "429", "503" and "502" in the question give those errors; anything else lists the first insights. */
export async function askMatch(question: string, lang: Lang): Promise<AskResponse> {
  await delay(700)
  if (question.includes('501')) throw new ApiError(501, 'the Q&A agent is not implemented')
  if (question.includes('429')) throw new ApiError(429, 'too many questions this hour', { retry_after_s: 754 })
  if (question.includes('503')) throw new ApiError(503, 'the model did not answer in 20 s')
  if (question.includes('502')) throw new ApiError(502, 'the agent returned an answer that does not validate')
  const picks = INSIGHTS.slice(0, 3)
  return {
    answer: lang === 'es' ? `Hay ${picks.length} momentos que responden a la pregunta.` : `${picks.length} moments answer that question.`,
    values: { n: picks.length },
    moments: picks.map((i) => ({ kind: 'insight' as const, insight_id: i.insight_id, t_s: i.t_s, clock_s: i.clock_s, period: i.period })),
  }
}
