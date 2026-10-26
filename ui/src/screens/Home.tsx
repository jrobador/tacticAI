import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowRight, Film, Loader2, Play, Sparkles, Video } from 'lucide-react'
import { activeJobId, ApiError, createJob, draftScenario, getLibrary, listMatches } from '@/api/client'
import type { Catalog, LibraryEntry, MatchSummary, Side } from '@/api/types'
import { MiniPitch } from '@/components/MiniPitch'
import { TeamTag } from '@/components/TeamTag'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/input'
import { label } from '@/lib/format'
import { go, type Draft } from '@/lib/nav'
import { oneLine } from '@/lib/recipe'

const EXAMPLE_PROMPTS = ['Wexmoor counter-attack that ends in a goal', 'Brackenford attack down the right']
const PAGE = 12

interface Props {
  catalog: Catalog | null
  text: string
  setText: (t: string) => void
  setDraft: (d: Draft) => void
}

export function Home({ catalog, text, setText, setDraft }: Props) {
  return (
    <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
      <div className="flex flex-col gap-6">
        <RequestCard catalog={catalog} text={text} setText={setText} setDraft={setDraft} />
        <RecordedMatches />
      </div>
      <Library catalog={catalog} />
    </div>
  )
}

function RequestCard({ catalog, text, setText, setDraft }: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [showExamples, setShowExamples] = useState(false)

  async function draft() {
    setBusy(true)
    setError(null)
    try {
      const r = await draftScenario(text, null)
      setDraft({ recipe: r.recipe, summary: r.summary })
      go('/recipe')
    } catch (e) {
      // 501/503 etc: show the error, keep the text, and offer the example path.
      setError(e instanceof ApiError ? e : new ApiError(0, String(e)))
      setShowExamples(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base"><Sparkles className="size-4 text-primary" /> Ask for a new play</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Describe the play you want to see"
          aria-label="Describe the play you want to see"
        />
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_PROMPTS.map((p) => (
            <button key={p} type="button" onClick={() => setText(p)} className="rounded-full border px-3 py-1 text-xs text-muted-foreground hover:border-primary hover:text-foreground">
              {p}
            </button>
          ))}
        </div>
        <Button onClick={draft} disabled={busy || !text.trim()}>
          {busy ? <Loader2 className="animate-spin" /> : <ArrowRight />} Draft recipe
        </Button>

        {error && (
          <Alert>
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <div>
              <p className="font-medium">The recipe agent is not available ({error.status || 'network'})</p>
              <p className="text-muted-foreground">{error.message}. Your text is kept; you can start from an example instead.</p>
            </div>
          </Alert>
        )}

        <div className="border-t pt-3">
          <Button variant={error ? 'default' : 'outline'} className="w-full" onClick={() => setShowExamples((v) => !v)} aria-expanded={showExamples}>
            Start from an example
          </Button>
          {showExamples && (
            <ul className="mt-3 flex flex-col gap-2">
              {(catalog?.examples ?? []).map((ex, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => { setDraft({ recipe: ex, summary: null }); go('/recipe') }}
                    className="w-full rounded-lg border p-3 text-left text-sm hover:border-primary"
                  >
                    {oneLine(ex)}
                    <span className="mt-1 block text-xs text-muted-foreground">
                      {ex.mode === 'full_match' ? 'Takes about 11 minutes' : `${ex.seeds} seeds`}
                    </span>
                  </button>
                </li>
              ))}
              {!catalog && <li className="text-sm text-muted-foreground">The catalog is not loaded yet.</li>}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function RecordedMatches() {
  const [matches, setMatches] = useState<MatchSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    listMatches().then(setMatches).catch((e: Error) => setError(e.message))
  }, [])
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Film className="size-4 text-primary" /> Recorded matches</CardTitle></CardHeader>
      <CardContent className="flex flex-col gap-2">
        {error && <p className="text-sm text-muted-foreground">{error}</p>}
        {matches?.length === 0 && <p className="text-sm text-muted-foreground">Nothing recorded yet.</p>}
        {!matches && !error && <p className="text-sm text-muted-foreground">Loading...</p>}
        {matches?.map((m) => (
          <div key={m.match_id} className="flex items-center justify-between gap-2 rounded-lg border p-3 text-sm">
            <div className="flex min-w-0 flex-col gap-1">
              <span className="flex flex-wrap items-center gap-2">
                <TeamTag side="home" name={m.teams.home.short} /> <span className="text-muted-foreground">vs</span> <TeamTag side="away" name={m.teams.away.short} />
              </span>
              <span className="text-xs text-muted-foreground">{m.formations.home} v {m.formations.away} - {Math.round(m.duration_s)} s{m.library_id ? ` - ${m.library_id}` : ''}</span>
            </div>
            <Button size="sm" onClick={() => go(`/matches/${m.match_id}`)}><Play /> View</Button>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

const ALL = 'all'
const outcomeOf = (e: LibraryEntry) => (e.wanted[0]?.startsWith('goal') ? 'goal' : 'shot')

function Library({ catalog }: { catalog: Catalog | null }) {
  const [entries, setEntries] = useState<LibraryEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [template, setTemplate] = useState(ALL)
  const [team, setTeam] = useState(ALL)
  const [outcome, setOutcome] = useState(ALL)
  const [shown, setShown] = useState(PAGE)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ text: string; jobId?: string } | null>(null)

  useEffect(() => {
    getLibrary().then((l) => setEntries(l.entries)).catch((e: Error) => setError(e.message))
  }, [])

  const templates = useMemo(() => [...new Set((entries ?? []).map((e) => e.template))], [entries])
  const filtered = useMemo(
    () => (entries ?? []).filter((e) => (template === ALL || e.template === template) && (team === ALL || e.ball_owner === team) && (outcome === ALL || outcomeOf(e) === outcome)),
    [entries, template, team, outcome],
  )

  async function record(e: LibraryEntry) {
    setBusy(e.entry_id)
    setNotice(null)
    try {
      const r = await createJob({ library_id: e.entry_id })
      go(r.kind === 'existing' ? `/matches/${r.match_id}` : `/jobs/${r.job_id}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setNotice({ text: 'A match is already being generated', jobId: activeJobId(err) ?? undefined })
      else setNotice({ text: err instanceof Error ? err.message : String(err) })
    } finally {
      setBusy(null)
    }
  }

  const opts = (vals: string[], all: string) => [{ value: ALL, label: all }, ...vals.map((v) => ({ value: v, label: label(v) }))]

  return (
    <section aria-label="Library" className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Library</h1>
          <p className="text-sm text-muted-foreground">Ready-made situations. Recording a video takes about 80 s.</p>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Select label="Filter by template" value={template} onChange={(v) => { setTemplate(v); setShown(PAGE) }} options={opts(templates, 'All templates')} className="w-44" />
          <Select label="Filter by attacking team" value={team} onChange={(v) => { setTeam(v); setShown(PAGE) }} options={[{ value: ALL, label: 'Either team' }, { value: 'home', label: 'Brackenford attacks' }, { value: 'away', label: 'Wexmoor attacks' }]} className="w-44" />
          <Select label="Filter by result" value={outcome} onChange={(v) => { setOutcome(v); setShown(PAGE) }} options={[{ value: ALL, label: 'Shot or goal' }, { value: 'goal', label: 'Goal' }, { value: 'shot', label: 'Shot' }]} className="w-36" />
        </div>
      </div>

      {notice && (
        <Alert>
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium">{notice.text}</p>
            {notice.jobId && <a className="text-primary underline" href={`#/jobs/${notice.jobId}`}>See its progress</a>}
          </div>
        </Alert>
      )}
      {error && <Alert><AlertTriangle className="mt-0.5 size-4 shrink-0" /><p>{error}</p></Alert>}
      {!entries && !error && <p className="text-sm text-muted-foreground">Loading library...</p>}
      {entries && filtered.length === 0 && <p className="text-sm text-muted-foreground">No situations match these filters.</p>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {filtered.slice(0, shown).map((e) => {
          const preview = catalog?.template_previews[e.template]?.[e.ball_owner as Side] ?? null
          return (
            <Card key={e.entry_id} className="flex flex-col">
              <CardContent className="flex flex-1 flex-col gap-3 p-3">
                <MiniPitch data={preview} owner={e.ball_owner} />
                <h2 className="text-sm font-medium leading-snug">{e.title}</h2>
                <div className="flex flex-wrap gap-1.5">
                  <Badge>{label(e.template)}</Badge>
                  <Badge variant={outcomeOf(e) === 'goal' ? 'default' : 'outline'}>{label(outcomeOf(e))}</Badge>
                  <Badge>{e.home.formation} v {e.away.formation}</Badge>
                </div>
                <div className="mt-auto flex items-center justify-between pt-1">
                  <span className="text-xs text-muted-foreground">{e.duration_s.toFixed(1)} s clip</span>
                  {e.match_id ? (
                    <Button size="sm" onClick={() => go(`/matches/${e.match_id}`)}><Play /> View</Button>
                  ) : (
                    <Button size="sm" variant="outline" disabled={busy !== null} onClick={() => record(e)}>
                      {busy === e.entry_id ? <Loader2 className="animate-spin" /> : <Video />} Record video
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
      {filtered.length > shown && <Button variant="outline" className="self-center" onClick={() => setShown((n) => n + PAGE)}>Show more</Button>}
    </section>
  )
}
