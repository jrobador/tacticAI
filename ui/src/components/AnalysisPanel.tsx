import { useState } from 'react'
import type { AgentEvidence, MatchBundle, PlayerRow, Side } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { TeamTag } from '@/components/TeamTag'
import { byRating, fix, label, minute, mmss, noteText, pctText, PHASE_LABEL, ratingView, visibleNote, type Names } from '@/lib/format'
import { cn } from '@/lib/utils'

/**
 * "Full-match analysis": totals of the whole match, so nothing here follows the video clock.
 * Physical values are relative only (rank, percentile) while meta.calibration.physical_absolute is false.
 */
export function AnalysisPanel({ bundle, names }: { bundle: MatchBundle; names: Names }) {
  const { meta, agents } = bundle
  const hasAgents = !!agents?.tactical
  return (
    <section aria-labelledby="analysis-title">
      <Card>
        <CardHeader>
          <CardTitle id="analysis-title" className="text-lg">Full-match analysis</CardTitle>
          <p className="text-sm text-muted-foreground">
            Totals for the whole match; they do not change with the video. xG is the engine xG, and physical values are relative only (rank and percentile), never kilometres.
          </p>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="teams">
            <TabsList>
              <TabsTrigger value="teams">Teams</TabsTrigger>
              <TabsTrigger value="players">Players</TabsTrigger>
              {hasAgents && <TabsTrigger value="agents">Tactical reading</TabsTrigger>}
              <TabsTrigger value="quality">Tracking quality</TabsTrigger>
            </TabsList>
            <TabsContent value="teams"><TeamsTab bundle={bundle} /></TabsContent>
            <TabsContent value="players"><PlayersTab bundle={bundle} names={names} /></TabsContent>
            {hasAgents && <TabsContent value="agents"><AgentsTab bundle={bundle} names={names} /></TabsContent>}
            <TabsContent value="quality"><QualityTab bundle={bundle} /></TabsContent>
          </Tabs>
          <p className="mt-4 text-xs text-muted-foreground">Source: {meta.source.detail}. Camera setup: {meta.source.camera_setup}.</p>
        </CardContent>
      </Card>
    </section>
  )
}

function TeamsTab({ bundle }: { bundle: MatchBundle }) {
  const { meta, teams } = bundle
  const t = (s: Side) => teams.find((x) => x.team === s)
  const projected = meta.projection.applies
  const rows: [string, (s: Side) => string][] = [
    ['Goals', (s) => String(t(s)?.goals ?? '-')],
    ['Engine xG', (s) => fix(t(s)?.xg)],
    ['Shots', (s) => String(t(s)?.shooting.shots ?? '-')],
    ['Possession', (s) => pctText(t(s)?.possession_pct)],
    ['Pressure (match mean)', (s) => fix(t(s)?.pressure)],
    ['Passes', (s) => String(t(s)?.passing.passes ?? '-')],
    ['Passes per minute', (s) => fix(t(s)?.passing.passes_per_min, 1)],
    ...(projected ? [["Passes projected to 90'", (s: Side) => fix(t(s)?.passing.passes_projected, 0)] as [string, (s: Side) => string]] : []),
    ['Pass completion', (s) => pctText(t(s)?.passing.completion_pct)],
    ['Progressive passes', (s) => String(t(s)?.passing.progressive_passes ?? '-')],
    ['Lines broken', (s) => String(t(s)?.passing.lines_broken ?? '-')],
    ['Tackles', (s) => String(t(s)?.defending.tackles ?? '-')],
    ['Interceptions', (s) => String(t(s)?.defending.interceptions ?? '-')],
    ['Sequences ending in a shot', (s) => `${t(s)?.sequences_ending_in_shot ?? '-'} of ${t(s)?.sequences ?? '-'}`],
  ]
  return (
    <table className="w-full max-w-2xl text-sm">
      <thead>
        <tr>
          <th className="py-2 text-left font-normal text-muted-foreground">Metric</th>
          {(['home', 'away'] as Side[]).map((s) => <th key={s} className="py-2 text-right font-medium"><TeamTag side={s} name={meta.teams[s].name} className="justify-end" /></th>)}
        </tr>
      </thead>
      <tbody className="tabular-nums">
        {rows.map(([name, f]) => (
          <tr key={name} className="border-t">
            <td className="py-1.5 text-muted-foreground">{name}</td>
            <td className="py-1.5 text-right">{f('home')}</td>
            <td className="py-1.5 text-right">{f('away')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function PlayersTab({ bundle, names }: { bundle: MatchBundle; names: Names }) {
  const [side, setSide] = useState<Side | 'all'>('all')
  const { meta } = bundle
  const rows = bundle.players.filter((p) => side === 'all' || p.team === side).sort(byRating)
  let rank = 0
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter players">
        <Button size="sm" variant={side === 'all' ? 'default' : 'outline'} onClick={() => setSide('all')}>Both teams</Button>
        {(['home', 'away'] as Side[]).map((s) => (
          <Button key={s} size="sm" variant={side === s ? 'default' : 'outline'} onClick={() => setSide(s)}>{meta.teams[s].short}</Button>
        ))}
        <span className="ml-auto text-xs text-muted-foreground">Rating = goals added by the player's actions, from the engine model. Goalkeepers are not rated.</span>
      </div>
      <ul className="grid gap-2 xl:grid-cols-2">
        {rows.map((p) => {
          const v = ratingView(p.rating)
          if (v.rated) rank++
          return <PlayerItem key={p.player_id} p={p} names={names} bundle={bundle} view={v} rank={v.rated ? rank : null} />
        })}
      </ul>
    </div>
  )
}

function PlayerItem({ p, names, bundle, view, rank }: { p: PlayerRow; names: Names; bundle: MatchBundle; view: ReturnType<typeof ratingView>; rank: number | null }) {
  const r = names[p.player_id]
  return (
    <li>
      <details className="group rounded-lg border bg-background open:border-primary/60">
        <summary className="flex cursor-pointer list-none items-center gap-3 p-3">
          <span className="w-6 text-center text-xs text-muted-foreground tabular-nums">{rank ?? '-'}</span>
          <img src={p.team === 'home' ? '/crest-bka.png' : '/crest-wxc.png'} alt={bundle.meta.teams[p.team].name} className="size-5 object-contain" />
          <span className="flex-1 truncate font-medium">{r?.name ?? p.player_id} <span className="font-normal text-muted-foreground">#{r?.number} {r?.role}</span></span>
          <span className={cn('text-sm tabular-nums', view.rated ? 'font-semibold text-primary' : 'text-muted-foreground')}>{view.text}</span>
        </summary>
        <div className="flex flex-col gap-3 border-t p-3 text-sm">
          {p.rating.breakdown.length > 0 ? (
            <table className="w-full tabular-nums">
              <thead>
                <tr className="text-xs text-muted-foreground"><th className="text-left font-normal">Action</th><th className="text-right font-normal">Count</th><th className="text-right font-normal">Offensive</th><th className="text-right font-normal">Defensive</th><th className="text-right font-normal">Goals added</th></tr>
              </thead>
              <tbody>
                {p.rating.breakdown.map((b) => (
                  <tr key={b.item} className="border-t">
                    <td className="py-1">{label(b.item)}</td><td className="text-right">{b.count}</td>
                    <td className="text-right">{b.offensive.toFixed(3)}</td><td className="text-right">{b.defensive.toFixed(3)}</td><td className="text-right font-medium">{b.points.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="text-muted-foreground">{view.rated ? 'No rated actions.' : p.rating.reason === 'vaep_model_missing' ? 'The rating model is not available for this match yet.' : 'Saves are not detected yet, so goalkeepers are not rated.'}</p>}
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-muted-foreground sm:grid-cols-3">
            <dt>Passes</dt><dd className="text-right text-foreground">{p.passing.completed}/{p.passing.passes} ({pctText(p.passing.completion_pct, 0)})</dd>
            <dt>Shots / engine xG</dt><dd className="text-right text-foreground">{p.shooting.shots} / {fix(p.shooting.xg)}</dd>
            <dt>Tackles / interceptions</dt><dd className="text-right text-foreground">{p.defending.tackles} / {p.defending.interceptions}</dd>
            <dt>Distance (relative)</dt><dd className="text-right text-foreground">#{p.physical.distance_rank}, {p.physical.distance_percentile}th pct</dd>
            <dt>Top speed (relative)</dt><dd className="text-right text-foreground">#{p.physical.top_speed_rank}, {p.physical.top_speed_percentile}th pct</dd>
          </dl>
        </div>
      </details>
    </li>
  )
}

function Evidence({ items }: { items: AgentEvidence[] }) {
  if (!items.length) return null
  return (
    <details className="mt-1 text-xs text-muted-foreground">
      <summary className="cursor-pointer">Evidence ({items.length})</summary>
      <ul className="mt-1 list-disc pl-4">
        {items.map((e, i) => <li key={i}><code>{e.call_id}</code> {e.path} = {String(e.value)}</li>)}
      </ul>
    </details>
  )
}

function AgentsTab({ bundle, names }: { bundle: MatchBundle; names: Names }) {
  const { agents, phases, notes, meta } = bundle
  const t = agents!.tactical!
  return (
    <div className="flex max-w-3xl flex-col gap-5">
      <div>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Summary</h4>
        <p>{t.summary.text}</p>
        <Evidence items={t.summary.evidence} />
      </div>
      {t.phases.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Phases</h4>
          <ol className="flex flex-col gap-3">
            {[...t.phases].sort((a, b) => a.rank - b.rank).map((p) => {
              const c = phases.find((x) => x.candidate_id === p.candidate_id)
              return (
                <li key={p.candidate_id} className="rounded-lg border p-3 text-sm">
                  {c && (
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <Badge variant="default">{PHASE_LABEL[c.phase] ?? label(c.phase)}</Badge>
                      <TeamTag side={c.team} name={meta.teams[c.team].short} className="text-xs" />
                      <span className="text-xs text-muted-foreground">{mmss(c.from_t_s)} to {mmss(c.until_t_s)}</span>
                    </div>
                  )}
                  <p>{p.text}</p>
                  <Evidence items={p.evidence} />
                </li>
              )
            })}
          </ol>
        </div>
      )}
      {t.key_notes.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Key notes</h4>
          <ol className="flex flex-col gap-3">
            {[...t.key_notes].sort((a, b) => a.rank - b.rank).filter((k) => { const n = notes[k.note_index]; return !n || visibleNote(n) }).map((k) => {
              const n = notes[k.note_index]
              return (
                <li key={k.note_index} className="rounded-lg border p-3 text-sm">
                  {n && (
                    <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <TeamTag side={n.team} name={meta.teams[n.team].short} /> <span>{minute(n.start_clock_s)}</span>
                      <span className="sr-only">{noteText(n, names, meta.teams[n.team].name)}</span>
                    </div>
                  )}
                  <p>{k.text}</p>
                  <Evidence items={k.evidence} />
                </li>
              )
            })}
          </ol>
        </div>
      )}
      <p className="text-xs text-muted-foreground">Written by {agents!.model}. Every number comes from the Stats Tools; the model does not compute any.</p>
    </div>
  )
}

function QualityTab({ bundle }: { bundle: MatchBundle }) {
  const q = bundle.quality
  const share = (v: number) => `${Math.round(v * 100)}%`
  return (
    <div className="flex max-w-2xl flex-col gap-4 text-sm">
      <div className="flex items-center gap-3">
        <span className="text-muted-foreground">Confidence level</span>
        <Badge variant={q.level === 'high' ? 'default' : 'muted'} className="text-sm uppercase">{q.level}</Badge>
      </div>
      {q.notes.length > 0 ? (
        <ul className="list-disc pl-5">{q.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
      ) : <p className="text-muted-foreground">No quality notes.</p>}
      <dl className="grid grid-cols-2 gap-x-6 gap-y-1 tabular-nums text-muted-foreground sm:grid-cols-4">
        <dt>Main camera</dt><dd className="text-right text-foreground">{share(q.main_camera_share)}</dd>
        <dt>Ball observed</dt><dd className="text-right text-foreground">{share(q.ball_observed_share)}</dd>
        <dt>Players observed</dt><dd className="text-right text-foreground">{share(q.players_observed_share)}</dd>
        <dt>Mean confidence</dt><dd className="text-right text-foreground">{q.mean_confidence.toFixed(2)}</dd>
        <dt>Gaps</dt><dd className="text-right text-foreground">{q.gaps}</dd>
        <dt>Suspected identity swaps</dt><dd className="text-right text-foreground">{q.identity_swaps_suspected}</dd>
      </dl>
    </div>
  )
}
