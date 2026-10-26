import { useCallback, useMemo, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { videoUrl } from '@/api/client'
import type { Lens, Overlay } from '@/api/types'
import { AskTab } from '@/components/match/AskTab'
import { AudienceBar } from '@/components/match/AudienceBar'
import { ConceptCard, placeConcept, type ConceptPos } from '@/components/match/ConceptCard'
import type { Env } from '@/components/match/concepts'
import { useBundle, useExplainFiles, useModels, useOverlays, useRecap, useRunInfo, useSummary, useTracking, useVariants } from '@/components/match/data'
import { HowDrawer } from '@/components/match/HowDrawer'
import { MomentsTab } from '@/components/match/MomentsTab'
import { DEFAULT_PROFILE, shownInsights, type ConceptKey, type Det, type Profile, type Tab } from '@/components/match/model'
import { OnAirTab } from '@/components/match/OnAirTab'
import { AnalystLayer, BroadcastLayer, FanLayer, NewcomerLayer, SpotlightLayer, buildViews, latest } from '@/components/match/Overlays'
import { Controls, SideBySide, VideoStage } from '@/components/match/Stage'
import { StatsTab } from '@/components/match/StatsTab'
import { ConceptContext, Term } from '@/components/match/Term'
import { usePlayback } from '@/components/match/usePlayback'
import { Alert } from '@/components/ui/alert'
import { mmss, type Names } from '@/lib/format'
import { cn } from '@/lib/utils'

const NONE: Overlay[] = []
const TABS: [Tab, string][] = [['moments', 'Moments'], ['stats', 'Stats'], ['onair', 'On-air'], ['ask', 'Ask']]

export function Match({ matchId }: { matchId: string }) {
  const { bundle, error } = useBundle(matchId)
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE)
  const [sbs, setSbs] = useState(false)
  const [tab, setTab] = useState<Tab>('moments')
  const [momOpen, setMomOpen] = useState<string | null>(null)
  const [approved, setApproved] = useState<Set<string>>(new Set())
  const [det, setDet] = useState<Det | null>(null)
  const [how, setHow] = useState(false)
  const [concept, setConcept] = useState<ConceptPos | null>(null)
  const onConcept = useCallback((key: ConceptKey, e: React.MouseEvent) => setConcept(placeConcept(key, e.currentTarget as HTMLElement)), [])
  const onOpenHow = useCallback(() => setHow(true), [])
  const closeHow = useCallback(() => setHow(false), [])
  const closeConcept = useCallback(() => setConcept(null), [])
  const models = useModels()
  const run = useRunInfo(matchId, how || concept !== null)

  const src = videoUrl(matchId)
  const duration = bundle ? bundle.meta.video.frames / bundle.meta.video.fps : 1
  const pb = usePlayback(src, duration)
  const { time, seek, play } = pb

  const ovs: Record<Lens, ReturnType<typeof useOverlays>> = {
    analyst: useOverlays(matchId, 'analyst', profile),
    fan: useOverlays(matchId, 'fan', profile),
    broadcast: useOverlays(matchId, 'broadcast', profile),
    first_match: useOverlays(matchId, 'first_match', profile),
    one_metric: useOverlays(matchId, 'one_metric', profile),
  }
  const available = ovs.analyst?.available === true
  const { insights: allInsights, manifest } = useExplainFiles(matchId, available)
  const texts = useVariants(matchId, profile.lens, profile, available)
  const { recap, loading: recapLoading } = useRecap(matchId, profile, available)
  const tracking = useTracking(matchId)
  const summary = useSummary(matchId)

  const names = useMemo<Names>(() => Object.fromEntries((bundle?.roster.players ?? []).map((p) => [p.player_id, p])), [bundle])
  const insights = useMemo(() => shownInsights(allInsights), [allInsights])
  const byId = useMemo(() => new Map(allInsights.map((i) => [i.insight_id, i])), [allInsights])
  const onSeek = useCallback((t: number) => seek(t), [seek])

  const openMoment = useCallback((id: string) => { setTab('moments'); setMomOpen(id); play(false) }, [play])
  const closeMoment = useCallback((id: string | null) => { setMomOpen(id); if (id === null) play(true) }, [play])
  const approve = useCallback((id: string) => setApproved((s) => new Set(s).add(id)), [])

  if (error) {
    return (
      <section className="w-full max-w-[1480px] px-[22px] py-5">
        <Alert><AlertTriangle className="mt-0.5 size-4 shrink-0" /><div><p className="font-medium">Could not load this match</p><p className="text-muted-foreground">{error}</p><a className="text-primary underline" href="#/matches">Back to Matches</a></div></Alert>
      </section>
    )
  }
  if (!bundle) return <p className="px-[22px] py-5 text-sm text-muted-foreground">Loading match...</p>

  const { meta, events } = bundle
  const short = { home: meta.teams.home.short, away: meta.teams.away.short }
  const goals = events.filter((e) => e.type === 'goal')
  const score = { home: goals.filter((e) => e.team === 'home' && e.t_s <= time).length, away: goals.filter((e) => e.team === 'away' && e.t_s <= time).length }
  const finalScore = { home: goals.filter((e) => e.team === 'home').length, away: goals.filter((e) => e.team === 'away').length }
  // Match clock: the tracking frame at the video time, or the last event's clock plus the time since it.
  const frame = tracking.filter((f) => f.t_s <= time).at(-1)
  const lastEv = events.filter((e) => e.t_s <= time).at(-1)
  const clockS = frame ? frame.clock_s : lastEv ? lastEv.clock_s + (time - lastEv.t_s) : 0

  const list = (l: Lens) => (available && ovs[l]?.overlays) || NONE
  const playerName = profile.player ? (names[profile.player]?.name ?? null) : null
  const views = Object.fromEntries((Object.keys(ovs) as Lens[]).map((l) => [l, buildViews(list(l), byId, time, profile, playerName)])) as Record<Lens, ReturnType<typeof buildViews>>
  // One graphic on air at a time: the latest approved one that is live.
  const onAir = latest(views.broadcast.filter((v) => approved.has(v.insightId)), 1)
  const on: Record<Lens, Set<string>> = {
    analyst: latest(views.analyst, 3), fan: latest(views.fan, 1), first_match: latest(views.first_match, 1), one_metric: latest(views.one_metric, 1), broadcast: onAir,
  }
  const windows = new Map<string, [number, number]>()
  for (const o of [...list('analyst'), ...list(profile.lens)]) windows.set(o.insight_id, [o.show_t_s, o.show_t_s + o.duration_s])
  const shown = ovs[profile.lens] ? new Set(list(profile.lens).map((o) => o.insight_id)) : null

  // The moment a concept card talks about: the open one, else the one whose overlay is on screen.
  const ctxMoment = momOpen ? (byId.get(momOpen) ?? null) : (insights.filter((i) => { const w = windows.get(i.insight_id); return !!w && time >= w[0] && time < w[1] }).at(-1) ?? null)
  const env: Env = { bundle, models, run, time, moment: ctxMoment, det, profile, shown: shown?.size ?? null, moments: insights, library: summary ? !!summary.library_id : null }

  const layerProps = (l: Lens) => ({ views: views[l], on: on[l], active: profile.lens === l, openId: tab === 'moments' ? momOpen : null, onOpen: openMoment })
  const origin = summary ? (summary.library_id ? 'Template' : 'Generated') : null
  const qaExamples = [`Every shot by ${meta.teams.home.name}`, `Every line-breaking pass by ${meta.teams.away.name}`, 'When did the pressure change?']

  return (
    <ConceptContext.Provider value={onConcept}>
      <section className="fade-in flex w-full max-w-[1480px] flex-col gap-2.5 px-[22px] pb-7 pt-3.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-baseline gap-3">
            <h1 className="text-lg font-semibold tracking-[-.01em]">{meta.teams.home.name} vs {meta.teams.away.name}</h1>
            <span className="font-heading text-sm font-semibold">{short.home} <span className="text-primary">{finalScore.home}–{finalScore.away}</span> {short.away}</span>
            {origin && <Term k="template" className="text-xs font-medium text-dim">{origin}</Term>}
          </div>
          <div className="flex items-center gap-2 rounded-full border border-foreground/20 px-2.5 py-1 text-[11.5px] font-medium">
            <span className="size-[7px] rounded-sm bg-foreground" />
            {meta.source.kind === 'synthetic' ? 'Synthetic feed · our 3D engine · 22 players + ball tracking' : `${meta.source.kind} feed`}
          </div>
        </div>

        <div className="flex flex-wrap items-start gap-[18px]">
          <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-2">
            <AudienceBar profile={profile} onChange={setProfile} sbs={sbs} onSbs={setSbs} short={short} roster={bundle.roster.players} />
            {ovs.analyst && !available && (
              <p className="rounded-[10px] border border-dashed border-foreground/25 px-3 py-2 text-[12.5px] text-muted-foreground">
                This match has no overlays or moments: the Explain and Render stages did not run on it. The video, the controls and the Ask tab still work.
              </p>
            )}
            <VideoStage src={src} pb={pb} short={short} score={score} clock={mmss(clockS)} hidden={sbs}>
              <AnalystLayer {...layerProps('analyst')} />
              <FanLayer {...layerProps('fan')} />
              <BroadcastLayer {...layerProps('broadcast')} />
              <SpotlightLayer {...layerProps('one_metric')} />
              <NewcomerLayer {...layerProps('first_match')} />
            </VideoStage>
            {sbs && (
              <SideBySide
                src={src} pb={pb} onOpen={openMoment}
                panes={{ analyst: { views: views.analyst, on: on.analyst }, fan: { views: views.fan, on: on.fan }, broadcast: { views: views.broadcast, on: on.broadcast } }}
              />
            )}
            <Controls pb={pb} duration={duration} events={events} names={names} focusId={profile.player} onSeek={onSeek} />
            <button type="button" onClick={onOpenHow} className="self-start py-1 text-[13px] font-semibold text-primary hover:text-foreground">How this match was made →</button>
          </div>

          <aside className="sticky top-3 flex min-w-0 max-w-full flex-[1_1_360px] flex-col overflow-hidden rounded-[14px] border border-foreground/10 bg-panel">
            <div role="tablist" className="flex gap-0.5 border-b border-foreground/10 p-1.5">
              {TABS.map(([k, l]) => (
                <button
                  key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                  className={cn('flex-1 rounded-lg px-1.5 py-[9px] text-[13px] font-semibold transition-colors duration-150', tab === k ? 'bg-[#1f2b40] text-foreground' : 'text-muted-foreground hover:text-foreground')}
                >
                  {l}
                </button>
              ))}
            </div>
            <div className="h-[calc(100vh-130px)] min-h-[420px] overflow-auto px-3.5 pb-[18px] pt-3">
              {tab === 'moments' && (
                <MomentsTab
                  insights={insights} bundle={bundle} profile={profile} texts={texts} shown={shown} windows={windows} time={time}
                  openId={momOpen} onOpen={closeMoment} onSeek={onSeek} onOpenHow={onOpenHow}
                />
              )}
              {tab === 'stats' && <StatsTab bundle={bundle} tracking={tracking} time={time} focusId={profile.player} names={names} models={models} det={det} onDet={setDet} onSeek={onSeek} />}
              {tab === 'onair' && (
                <OnAirTab
                  matchId={matchId} bundle={bundle} profile={profile} insights={insights} queue={list('broadcast')} time={time}
                  approved={approved} onApprove={approve} texts={texts} recap={recap} recapLoading={recapLoading} manifest={manifest} short={short} onSeek={onSeek}
                />
              )}
              {tab === 'ask' && (
                <AskTab
                  matchId={matchId} lang={profile.lang} examples={qaExamples} placeholder={qaExamples[0]} insights={insights} events={events}
                  names={names} texts={texts} onSeek={onSeek}
                />
              )}
            </div>
          </aside>
        </div>
      </section>
      {how && <HowDrawer title={`${meta.teams.home.name} vs ${meta.teams.away.name}`} bundle={bundle} run={run} insights={allInsights} library={env.library} suspendEsc={concept !== null} onClose={closeHow} />}
      {concept && <ConceptCard pos={concept} env={env} onClose={closeConcept} />}
    </ConceptContext.Provider>
  )
}
