import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowLeft, ArrowRight, Loader2, Play, Plus, X } from 'lucide-react'
import { activeJobId, ApiError, createJob, draftScenario, issuesOf, validateRecipe } from '@/api/client'
import type { Catalog, Recipe, RecipeIssue, Side, TeamPlan } from '@/api/types'
import { fromEngine, MiniPitch } from '@/components/MiniPitch'
import { TeamTag } from '@/components/TeamTag'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Textarea } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { DEFAULT_TEAMS, label } from '@/lib/format'
import { go, type Draft } from '@/lib/nav'
import { defaultSituation, predicateText } from '@/lib/recipe'

interface Props {
  catalog: Catalog
  draft: Draft
  setDraft: (d: Draft) => void
  text: string
  setText: (t: string) => void
}

const ENDS_LABEL: Record<string, string> = {
  goal: 'A goal is scored',
  possession_change: 'Possession changes',
  out_of_play: 'The ball goes out',
  steps: 'The clip time runs out',
}
const opt = (vals: string[]) => vals.map((v) => ({ value: v, label: label(v) }))

export function RecipeScreen({ catalog, draft, setDraft, text, setText }: Props) {
  const { recipe } = draft
  const [issues, setIssues] = useState<RecipeIssue[]>([])
  const [validating, setValidating] = useState(true)
  const [busy, setBusy] = useState<'generate' | 'adjust' | null>(null)
  const [alert, setAlert] = useState<{ text: string; jobId?: string } | null>(null)

  const change = (fn: (r: Recipe) => void) => {
    const next = structuredClone(recipe)
    fn(next)
    setDraft({ ...draft, recipe: next })
  }

  // Validate on every change (debounced); a stale answer is dropped.
  useEffect(() => {
    let live = true
    setValidating(true)
    const t = setTimeout(() => {
      validateRecipe(recipe)
        .then((v) => live && setIssues(v.errors))
        .catch((e: Error) => live && setIssues(issuesOf(e) ?? [{ path: 'recipe', message: `Validation unavailable: ${e.message}` }]))
        .finally(() => live && setValidating(false))
    }, 250)
    return () => { live = false; clearTimeout(t) }
  }, [recipe])

  async function generate() {
    setBusy('generate')
    setAlert(null)
    try {
      const r = await createJob({ recipe })
      go(r.kind === 'existing' ? `/matches/${r.match_id}` : `/jobs/${r.job_id}`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setAlert({ text: 'A match is already being generated', jobId: activeJobId(e) ?? undefined })
      else if (e instanceof ApiError && e.status === 422) setIssues(issuesOf(e) ?? [{ path: 'recipe', message: e.message }])
      else setAlert({ text: e instanceof Error ? e.message : String(e) })
    } finally {
      setBusy(null)
    }
  }

  async function adjust() {
    setBusy('adjust')
    setAlert(null)
    try {
      const r = await draftScenario(text, recipe)
      setDraft({ recipe: r.recipe, summary: r.summary })
    } catch (e) {
      setAlert({ text: `${e instanceof ApiError ? `Error ${e.status}: ` : ''}${e instanceof Error ? e.message : String(e)}. Your text and recipe are kept.` })
    } finally {
      setBusy(null)
    }
  }

  const sit = recipe.situation
  const preview = useMemo(() => {
    if (!sit) return null
    if (sit.template && sit.ball_owner) return catalog.template_previews[sit.template]?.[sit.ball_owner] ?? null
    if (sit.positions) return fromEngine(sit.positions, sit.ball, sit.ball_owner)
    return null
  }, [sit, catalog])

  const setMode = (mode: Recipe['mode']) => change((r) => {
    r.mode = mode
    if (mode === 'full_match') { r.situation = null; r.steps = 3000 } else { r.situation = r.situation ?? defaultSituation(catalog); r.steps = catalog.limits.steps_situation }
  })

  const sideName = (s: Side) => DEFAULT_TEAMS[s].name

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <Button variant="ghost" size="sm" onClick={() => go('/ask')} className="-ml-3"><ArrowLeft /> Back to library</Button>
          <h1 className="text-xl font-semibold">Adjust the recipe</h1>
        </div>
      </div>

      {draft.summary && (
        <Card><CardContent className="p-4 text-sm"><span className="text-primary">Agent summary - </span>{draft.summary}</CardContent></Card>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader><CardTitle>Mode</CardTitle></CardHeader>
            <CardContent className="flex flex-col gap-2">
              <div className="flex gap-2" role="group" aria-label="Mode">
                <Button variant={recipe.mode === 'situation' ? 'default' : 'outline'} aria-pressed={recipe.mode === 'situation'} onClick={() => setMode('situation')}>Situation</Button>
                <Button variant={recipe.mode === 'full_match' ? 'default' : 'outline'} aria-pressed={recipe.mode === 'full_match'} onClick={() => setMode('full_match')}>Full match</Button>
              </div>
              {recipe.mode === 'full_match' && <p className="text-sm text-muted-foreground">A full match takes about 11 minutes to generate.</p>}
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            {(['home', 'away'] as Side[]).map((side) => (
              <TeamEditor key={side} side={side} plan={recipe[side]} catalog={catalog}
                onChange={(p) => change((r) => { r[side] = p })} />
            ))}
          </div>

          {sit && (
            <Card>
              <CardHeader><CardTitle>Situation</CardTitle></CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                <Field name="Template">
                  <Select label="Template" value={sit.template ?? 'custom'}
                    onChange={(v) => change((r) => { const s = r.situation!; s.template = v; s.positions = null; s.ball = null; s.ball_owner = s.ball_owner ?? 'home' })}
                    options={[...(sit.template ? [] : [{ value: 'custom', label: 'Custom positions (from the agent)' }]), ...opt(catalog.templates)]} />
                </Field>
                <Field name="Who starts with the ball">
                  <Select label="Ball owner" value={sit.ball_owner ?? 'home'}
                    onChange={(v) => change((r) => { r.situation!.ball_owner = v as Side })}
                    options={(['home', 'away'] as Side[]).map((s) => ({ value: s, label: sideName(s) }))} />
                </Field>
                <Field name="Stop when">
                  <Select label="Stop when" value={sit.ends_when}
                    onChange={(v) => change((r) => { r.situation!.ends_when = v })}
                    options={catalog.ends_when.map((v) => ({ value: v, label: ENDS_LABEL[v] ?? label(v) }))} />
                </Field>
                <Field name={`Seeds to try (${catalog.limits.seeds.min}-${catalog.limits.seeds.max})`}>
                  <Input type="number" min={catalog.limits.seeds.min} max={catalog.limits.seeds.max} value={recipe.seeds}
                    onChange={(e) => change((r) => { r.seeds = e.target.value === '' ? 0 : Number(e.target.value) })} aria-label="Seeds" />
                </Field>
                <div className="md:col-span-2">
                  <WantedEditor wanted={sit.wanted} catalog={catalog} onChange={(w) => change((r) => { r.situation!.wanted = w })} />
                </div>
              </CardContent>
            </Card>
          )}

          {!sit && (
            <Card>
              <CardContent className="grid gap-4 p-4 md:grid-cols-2">
                <Field name={`Seeds to try (${catalog.limits.seeds.min}-${catalog.limits.seeds.max})`}>
                  <Input type="number" min={catalog.limits.seeds.min} max={catalog.limits.seeds.max} value={recipe.seeds}
                    onChange={(e) => change((r) => { r.seeds = e.target.value === '' ? 0 : Number(e.target.value) })} aria-label="Seeds" />
                </Field>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader><CardTitle>Ask for changes</CardTitle></CardHeader>
            <CardContent className="flex flex-col gap-2">
              <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder='For example: "more pressure"' aria-label="Ask for changes" className="min-h-16" />
              <Button variant="outline" className="self-start" onClick={adjust} disabled={busy !== null || !text.trim()}>
                {busy === 'adjust' ? <Loader2 className="animate-spin" /> : <ArrowRight />} Adjust recipe
              </Button>
            </CardContent>
          </Card>
        </div>

        <aside className="flex flex-col gap-4 lg:sticky lg:top-20 lg:self-start">
          <Card>
            <CardHeader><CardTitle>Starting positions</CardTitle></CardHeader>
            <CardContent className="flex flex-col gap-2">
              {sit ? (
                <>
                  <MiniPitch data={preview} owner={sit.ball_owner} />
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                    <TeamTag side="home" short /> <span>{sit.ball_owner === 'away' ? 'Wexmoor attacks toward the left' : 'Brackenford attacks toward the right'}</span> <TeamTag side="away" short />
                  </div>
                  {!preview && <p className="text-sm text-muted-foreground">No preview for this template.</p>}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">A full match starts from kick-off with both formations.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="flex flex-col gap-3 p-4">
              {issues.length > 0 && (
                <Alert aria-live="polite">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                  <div>
                    <p className="font-medium">Fix {issues.length === 1 ? 'this' : `these ${issues.length}`} before generating</p>
                    <ul className="mt-1 list-disc pl-4 text-muted-foreground">
                      {issues.map((i, k) => <li key={k}><code className="text-foreground">{i.path}</code>: {i.message}</li>)}
                    </ul>
                  </div>
                </Alert>
              )}
              {alert && (
                <Alert>
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                  <div>
                    <p className="font-medium">{alert.text}</p>
                    {alert.jobId && <a className="text-primary underline" href={`#/jobs/${alert.jobId}`}>See its progress</a>}
                  </div>
                </Alert>
              )}
              <Button size="lg" onClick={generate} disabled={issues.length > 0 || validating || busy !== null}>
                {busy === 'generate' ? <Loader2 className="animate-spin" /> : <Play />} Generate
              </Button>
              <p className="text-xs text-muted-foreground">
                {recipe.mode === 'full_match' ? 'About 11 minutes.' : `Searches up to ${recipe.seeds} seeds, then records the winner.`}
              </p>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  )
}

function Field({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="text-muted-foreground">{name}</span>
      {children}
    </label>
  )
}

function TeamEditor({ side, plan, catalog, onChange }: { side: Side; plan: TeamPlan; catalog: Catalog; onChange: (p: TeamPlan) => void }) {
  const { min, max } = catalog.limits.level
  return (
    <Card>
      <CardHeader><CardTitle className="text-base"><TeamTag side={side} /></CardTitle></CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Field name="Formation">
          <Select label={`${side} formation`} value={plan.formation} onChange={(v) => onChange({ ...plan, formation: v })} options={catalog.formations.map((f) => ({ value: f, label: f }))} />
        </Field>
        <Field name="Style">
          <Select label={`${side} style`} value={plan.style} onChange={(v) => onChange({ ...plan, style: v })} options={opt(catalog.styles)} />
        </Field>
        <div className="flex flex-col gap-1.5 text-sm">
          <div className="flex justify-between"><span className="text-muted-foreground">Level</span><span>{plan.level.toFixed(2)}</span></div>
          <Slider label={`${side} level`} value={plan.level} min={min} max={max} step={0.05} onChange={(v) => onChange({ ...plan, level: Math.round(v * 100) / 100 })} />
        </div>
      </CardContent>
    </Card>
  )
}

function WantedEditor({ wanted, catalog, onChange }: { wanted: string[]; catalog: Catalog; onChange: (w: string[]) => void }) {
  // One option per predicate; predicates that need a side or a player expand into one option each.
  const options = catalog.wanted.flatMap((w) => {
    if (w.takes === 'side') return (['home', 'away'] as Side[]).map((s) => ({ value: `${w.name}:${s}`, label: `${label(w.name)}: ${DEFAULT_TEAMS[s].name}`, hint: w.description }))
    if (w.takes === 'player') return catalog.players.map((p) => ({ value: `${w.name}:${p.name}`, label: `${label(w.name)}: ${p.name} (${DEFAULT_TEAMS[p.team].short} #${p.number})`, hint: w.description }))
    return [{ value: w.name, label: label(w.name), hint: w.description }]
  }).filter((o) => !wanted.includes(o.value))
  const [pick, setPick] = useState('')
  return (
    <div className="flex flex-col gap-2 text-sm">
      <span className="text-muted-foreground">What to look for</span>
      <div className="flex flex-wrap gap-2">
        {wanted.length === 0 && <span className="text-muted-foreground">Anything: no condition.</span>}
        {wanted.map((p) => (
          <Badge key={p} variant="muted" className="gap-1.5 py-1 pl-3 text-sm">
            {predicateText(p)}
            <button type="button" aria-label={`Remove ${predicateText(p)}`} onClick={() => onChange(wanted.filter((x) => x !== p))} className="rounded-full p-0.5 hover:bg-background"><X className="size-3.5" /></button>
          </Badge>
        ))}
      </div>
      <div className="flex gap-2">
        <Select label="Add a condition" placeholder="Add a condition" value={pick} onChange={setPick} options={options} />
        <Button variant="outline" disabled={!pick} onClick={() => { onChange([...wanted, pick]); setPick('') }}><Plus /> Add</Button>
      </div>
      {pick && <p className="text-xs text-muted-foreground">{options.find((o) => o.value === pick)?.hint}</p>}
    </div>
  )
}
