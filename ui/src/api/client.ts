// Typed client for every endpoint. With VITE_MOCK=1 the same functions
// are served by src/mocks/api.ts (dynamic import, so the mock layer is not part of a normal build).
import type {
  ModelCard,
  AgentsFile, AskResponse, Catalog, Club, CreateJobResult, EnrichedEvent, JobRequest, JobStatus, Lang, Lens, LibraryIndex, MatchBundle,
  Heatmaps, Insight, MatchMeta, MatchSummary, OverlayQuery, OverlaysResponse, PhaseCandidate, PlayerRow, QualityReport, Recap, Recipe, RecipeIssue, Roster, ScenarioResponse,
  TacticalNote, TeamRow, TimelineWindow, ValidateResponse,
} from './types'
import { TERMINAL_STATES } from './types'
import MOCK_PREVIEW from '@/mocks/preview.svg' // data URI: no request in mock mode

export const MOCK = import.meta.env.VITE_MOCK === '1'
const mock = () => import('@/mocks/api')

/** Error body of the API: {"error": "...", "detail": ...}. */
export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

// Shared access key: arrives once as ?key=..., is kept in localStorage and sent as X-Access-Key.
const KEY = 'tai_access_key'
try {
  const key = new URLSearchParams(location.search).get('key')
  if (key) {
    localStorage.setItem(KEY, key)
    const u = new URL(location.href)
    u.searchParams.delete('key')
    history.replaceState(null, '', u)
  }
} catch { /* storage blocked */ }
function storedKey(): string | null {
  try { return localStorage.getItem(KEY) } catch { return null }
}

async function request(method: string, url: string, body?: unknown): Promise<Response> {
  let res: Response
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const key = storedKey()
  if (key) headers['X-Access-Key'] = key
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the API. Is it running on localhost:8000?')
  }
  return res
}

async function errorFrom(res: Response): Promise<ApiError> {
  let body: { error?: string; detail?: unknown } = {}
  try {
    body = await res.json()
  } catch {
    /* non-JSON error body */
  }
  if (res.status === 401) return new ApiError(401, 'This action needs the access key from the submission.')
  return new ApiError(res.status, body.error ?? `${res.status} ${res.statusText}`, body.detail ?? body)
}

async function json<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await request(method, url, body)
  if (!res.ok) throw await errorFrom(res)
  return res.json() as Promise<T>
}

// ---- recipe ----
export const getCatalog = (): Promise<Catalog> =>
  MOCK ? mock().then((m) => m.getCatalog()) : json('GET', '/catalog')

export const validateRecipe = (recipe: Recipe): Promise<ValidateResponse> =>
  MOCK ? mock().then((m) => m.validateRecipe(recipe)) : json('POST', '/recipes/validate', { recipe })

/** 501 = agent not implemented, 503 = model failed or timed out, 502 = bad model output, 422 = bad input. */
export const draftScenario = (text: string, recipe: Recipe | null): Promise<ScenarioResponse> =>
  MOCK ? mock().then((m) => m.draftScenario(text, recipe)) : json('POST', '/scenario', { text, recipe })

// ---- jobs ----
/** 202 -> started, 200 -> the library entry already has a video, 409 -> ApiError(409) whose detail carries active_job_id. */
export async function createJob(req: JobRequest): Promise<CreateJobResult> {
  if (MOCK) return (await mock()).createJob(req)
  const res = await request('POST', '/jobs', req)
  if (res.status === 200) return { kind: 'existing', match_id: (await res.json()).match_id }
  if (res.status === 202) return { kind: 'started', job_id: (await res.json()).job_id }
  throw await errorFrom(res)
}

export const getJob = (jobId: string): Promise<JobStatus> =>
  MOCK ? mock().then((m) => m.getJob(jobId)) : json('GET', `/jobs/${jobId}`)

/** Last tracking frame of the running job; rejects with a 404 ApiError until there is one. */
export const getJobFrame = (jobId: string): Promise<Record<string, unknown>> =>
  MOCK ? mock().then((m) => m.getJobFrame(jobId)) : json('GET', `/jobs/${jobId}/frame`)

/** Latest recording frame of a running job; n busts the cache. */
export const previewUrl = (jobId: string, n: number): string =>
  MOCK ? MOCK_PREVIEW : `/jobs/${jobId}/preview.jpg?t=${n}`

export const getModels = (): Promise<{ models: ModelCard[] }> =>
  MOCK ? mock().then((m) => m.getModels()) : json('GET', '/models')

/** The 422 body carries the list of {path, message} directly in detail. null when the error has no such list. */
export function issuesOf(e: unknown): RecipeIssue[] | null {
  if (!(e instanceof ApiError) || e.status !== 422 || !Array.isArray(e.detail)) return null
  return e.detail as RecipeIssue[]
}

/** Active job id out of a 409 error (the body is {"active_job_id": ...}). */
export function activeJobId(e: ApiError): string | null {
  const d = e.detail as { active_job_id?: string } | undefined
  return d?.active_job_id ?? null
}

/**
 * Progress stream: WS /ws/jobs/{id} sends the current state, then each change, and closes on a terminal state.
 * If the socket cannot be used it falls back to polling GET /jobs/{id}. Returns the unsubscribe function.
 */
export function watchJob(jobId: string, onStatus: (s: JobStatus) => void, onError: (e: Error) => void): () => void {
  if (MOCK) {
    let stop = () => {}
    mock().then((m) => { stop = m.watchJob(jobId, onStatus, onError) })
    return () => stop()
  }
  let closed = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let ws: WebSocket | undefined
  let polling = false
  let terminal = false
  let lastRev = -1
  // Only a higher rev gets through and a terminal state is final, whichever of the socket or a slow poll answers late.
  const handle = (s: JobStatus) => {
    if (closed || terminal || s.rev <= lastRev) return
    lastRev = s.rev
    terminal = TERMINAL_STATES.includes(s.state)
    onStatus(s)
  }
  // Polling is the fallback when the socket fails: one request at a time, the next one scheduled when it answers.
  const poll = () => {
    if (polling || closed || terminal) return
    polling = true
    ws?.close()
    const tick = () => getJob(jobId)
      .then(handle)
      .catch((e) => { if (!closed) onError(e) })
      .finally(() => { if (!closed && !terminal) timer = setTimeout(tick, 1000) })
    tick()
  }
  try {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${proto}//${location.host}/ws/jobs/${jobId}`)
    ws.onmessage = (m) => handle(JSON.parse(m.data) as JobStatus)
    ws.onerror = () => poll()
    ws.onclose = () => { if (!closed && !terminal) poll() }
  } catch {
    poll()
  }
  return () => {
    closed = true
    ws?.close()
    clearTimeout(timer)
  }
}

// ---- files ----
export const listMatches = (): Promise<MatchSummary[]> =>
  MOCK ? mock().then((m) => m.listMatches()) : json<{ matches: MatchSummary[] } | MatchSummary[]>('GET', '/matches').then((r) => (Array.isArray(r) ? r : r.matches))

export const getLibrary = (): Promise<LibraryIndex> =>
  MOCK ? mock().then((m) => m.getLibrary()) : json('GET', '/library')

export const matchFileUrl = (matchId: string, name: string) => `/matches/${matchId}/files/${name}`
export const libraryFileUrl = (entryId: string, name: string) => `/library/${entryId}/files/${name}`
/** null in mock mode: there is no mp4 to play. */
export const videoUrl = (matchId: string): string | null => (MOCK ? null : matchFileUrl(matchId, 'video.mp4'))

async function fileText(matchId: string, name: string): Promise<string | null> {
  const res = await request('GET', matchFileUrl(matchId, name))
  if (res.status === 404) return null
  if (!res.ok) throw await errorFrom(res)
  return res.text()
}
const parseJsonl = <T>(text: string | null): T[] =>
  (text ?? '').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l) as T)

/** Downloads the analysis files once; agents.json and phases.jsonl are optional (404 -> empty/null). */
export async function loadMatch(matchId: string): Promise<MatchBundle> {
  if (MOCK) return (await mock()).loadMatch(matchId)
  const need = async (name: string) => {
    const t = await fileText(matchId, name)
    if (t === null) throw new ApiError(404, `Missing ${name}`)
    return t
  }
  const [meta, roster, events, timeline, notes, phases, players, teams, quality, agents] = await Promise.all([
    need('meta.json'), need('roster.json'), need('interpret/events_enriched.jsonl'), need('interpret/timeline.jsonl'),
    fileText(matchId, 'interpret/tactical_notes.jsonl'), fileText(matchId, 'interpret/phases.jsonl'),
    need('interpret/players.json'), need('interpret/teams.json'), need('interpret/quality.json'),
    fileText(matchId, 'interpret/agents.json'),
  ])
  return {
    meta: JSON.parse(meta) as MatchMeta,
    roster: JSON.parse(roster) as Roster,
    events: parseJsonl<EnrichedEvent>(events),
    timeline: parseJsonl<TimelineWindow>(timeline),
    notes: parseJsonl<TacticalNote>(notes),
    phases: parseJsonl<PhaseCandidate>(phases),
    players: (JSON.parse(players) as { players: PlayerRow[] }).players,
    teams: (JSON.parse(teams) as { teams: TeamRow[] }).teams,
    quality: JSON.parse(quality) as QualityReport,
    agents: agents ? (JSON.parse(agents) as AgentsFile) : null,
  }
}

// ---- overlays (Render) and insights (Explain) ----
export function overlaysUrl(matchId: string, q: OverlayQuery): string {
  const p = new URLSearchParams({ lens: q.lens, lang: q.lang, club: q.club })
  if (q.player) p.set('player', q.player)
  if (q.lens === 'one_metric' && q.metric) p.set('metric', q.metric)
  if (q.lens === 'broadcast' && q.brand) p.set('brand', q.brand)
  return `/matches/${encodeURIComponent(matchId)}/overlays?${p}`
}
export const getOverlays = (matchId: string, q: OverlayQuery): Promise<OverlaysResponse> =>
  MOCK ? mock().then((m) => m.getOverlays(matchId, q)) : json('GET', overlaysUrl(matchId, q))

/** Only call these when /overlays said available: true. A missing file gives an empty list / null. */
export async function getInsights(matchId: string): Promise<Insight[]> {
  if (MOCK) return (await mock()).getInsights()
  return parseJsonl<Insight>(await fileText(matchId, 'explain/insights.jsonl'))
}
export async function getHeatmaps(matchId: string): Promise<Heatmaps | null> {
  if (MOCK) return (await mock()).getHeatmaps()
  const t = await fileText(matchId, 'render/heatmaps.json')
  return t ? (JSON.parse(t) as Heatmaps) : null
}
/** The recap of the text lens (analyst for broadcast and one_metric), language and club. */
export async function getRecap(matchId: string, lens: Lens, lang: Lang, club: Club): Promise<Recap | null> {
  const textLens = lens === 'broadcast' || lens === 'one_metric' ? 'analyst' : lens
  if (MOCK) return (await mock()).getRecap(textLens, lang, club)
  const t = await fileText(matchId, `personalize/recaps/${textLens}_${lang}_${club}.json`)
  return t ? (JSON.parse(t) as Recap) : null
}

/** Match Q&A. Errors: 429 (detail has retry_after_s in the body), 501 not available, 503 timeout, 502 invalid answer. */
/** `fanClub` (Fan mode) asks for the answer in a supporter's voice for that club. */
export async function askMatch(matchId: string, question: string, lang: Lang, fanClub?: string): Promise<AskResponse> {
  if (MOCK) return (await mock()).askMatch(question, lang)
  const res = await request('POST', `/matches/${encodeURIComponent(matchId)}/ask`, { question, lang, ...(fanClub ? { fan_club: fanClub } : {}) })
  if (res.ok) return res.json() as Promise<AskResponse>
  let body: { error?: string; retry_after_s?: number } = {}
  try { body = await res.clone().json() } catch { /* non-JSON */ }
  const err = await errorFrom(res)
  if (typeof body.retry_after_s === 'number') err.detail = { retry_after_s: body.retry_after_s }
  throw err
}
