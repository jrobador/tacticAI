import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { videoUrl } from '@/api/client'
import type { Lens, Overlay } from '@/api/types'
import { AskTab } from '@/components/match/AskTab'
import { AudienceBar, type Feed } from '@/components/match/AudienceBar'
import { ConceptCard, placeConcept, type ConceptPos } from '@/components/match/ConceptCard'
import type { Env } from '@/components/match/concepts'
import { FeedLayer, FullTimeOverlay, GoalTakeover, OnAirBar, ReelsTab, ReplayTag, StudioScriptView, airAt, airNext, schedule } from '@/components/match/Broadcast'
import { useBundle, useExplainFiles, useFanFacts, useFanView, useModels, useOverlays, useReels, useRundown, useRunInfo, useStudio, useSummary, useTracking, useVariants } from '@/components/match/data'
import { HowDrawer } from '@/components/match/HowDrawer'
import { EventTicker } from '@/components/match/EventTicker'
import { FanOverlay, FanStory } from '@/components/match/FanStory'
import { MomentsTab } from '@/components/match/MomentsTab'
import { DEFAULT_PROFILE, modeOf, shownInsights, type Mode, type ConceptKey, type Det, type Profile, type Tab } from '@/components/match/model'
import { PlayerFocus } from '@/components/match/PlayerFocus'
import { AnalystLayer, FanLayer, NewcomerLayer, SpotlightLayer, buildViews, latest } from '@/components/match/Overlays'
import { Controls, Countdown, VideoStage } from '@/components/match/Stage'
import { StatsTab } from '@/components/match/StatsTab'
import { ConceptContext } from '@/components/match/Term'
import { usePlayback } from '@/components/match/usePlayback'
import { Alert } from '@/components/ui/alert'
import { mmss, type Names } from '@/lib/format'
import { cn } from '@/lib/utils'

const NONE: Overlay[] = []
/** Seconds the video holds: a moment's graphic has text to read, a shot or goal only its card. */
const STOP_S = { moment: 8, event: 4, fullTime: 12, takeover: 3 }
const FULL_TIME = 'full-time'

/** The side panel of each mode. Broadcast has its own: the studio teleprompter and the 9:16 reels. */
const TABS: Record<Mode, [Tab, string][]> = {
  analyst: [['moments', 'Moments'], ['stats', 'Stats'], ['ask', 'Ask']],
  fan: [['moments', 'Moments'], ['ask', 'Ask']],
  broadcast: [['studio', 'Studio'], ['reels', 'Reels']],
}

export function Match({ matchId }: { matchId: string }) {
  const { bundle, error } = useBundle(matchId)
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE)
  const [tab, setTab] = useState<Tab>('moments')
  const [momOpen, setMomOpen] = useState<string | null>(null)
  const [det, setDet] = useState<Det | null>(null)
  const [feed, setFeed] = useState<Feed>('plus')
  const [cue, setCue] = useState<number | null>(null)
  const [how, setHow] = useState(false)
  const [concept, setConcept] = useState<ConceptPos | null>(null)
  const onConcept = useCallback((key: ConceptKey, e: React.MouseEvent) => setConcept(placeConcept(key, e.currentTarget as HTMLElement)), [])
  const onOpenHow = useCallback(() => setHow(true), [])
  const closeHow = useCallback(() => setHow(false), [])
  const closeConcept = useCallback(() => setConcept(null), [])
  const models = useModels()
  const run = useRunInfo(matchId, how || concept !== null || tab === 'stats' || profile.player !== null)

  const src = videoUrl(matchId)
  const duration = bundle ? bundle.meta.video.frames / bundle.meta.video.fps : 1
  // Broadcast plays at 0.9x so a graphic can be read while it is on air; every other mode at 1x.
  const pb = usePlayback(src, duration, modeOf(profile.lens) === 'broadcast' ? 0.9 : 1)
  const { time, seek, play } = pb

  const ovs: Record<Lens, ReturnType<typeof useOverlays>> = {
    analyst: useOverlays(matchId, 'analyst', profile),
    fan: useOverlays(matchId, 'fan', profile),
    broadcast: useOverlays(matchId, 'broadcast', profile),
    first_match: useOverlays(matchId, 'first_match', profile),
    one_metric: useOverlays(matchId, 'one_metric', profile),
  }
  const available = ovs.analyst?.available === true
  const { insights: allInsights } = useExplainFiles(matchId, available)
  const texts = useVariants(matchId, profile.lens, profile, available)
  const tracking = useTracking(matchId)
  const summary = useSummary(matchId)

  const names = useMemo<Names>(() => Object.fromEntries((bundle?.roster.players ?? []).map((p) => [p.player_id, p])), [bundle])
  const insights = useMemo(() => shownInsights(allInsights), [allInsights])
  const byId = useMemo(() => new Map(allInsights.map((i) => [i.insight_id, i])), [allInsights])
  const onSeek = useCallback((t: number) => seek(t), [seek])

  // Moment stops: when the video reaches a moment of the selected audience (once its graphic has slid in), it holds
  // a few seconds (STOP_S) and goes on by itself. Broadcast only stops at full time: graphics go on air by themselves.
  const [stop, setStop] = useState<{ id: string; s: number } | null>(null)
  const passed = useRef(new Set<string>())
  const prevT = useRef(0)
  const lensList = ovs[profile.lens]?.available ? (ovs[profile.lens]?.overlays ?? NONE) : NONE
  // Where the video holds: every shot and goal, and every moment graphic of the audience once it has slid in.
  // Fan mode tells the match as a supporter lives it: its own moments, cards and stops replace the analytic ones.
  const fan = modeOf(profile.lens) === 'fan'
  const es = profile.lang === 'es'
  const broadcast = modeOf(profile.lens) === 'broadcast'
  const rundown = useRundown(matchId, broadcast)
  // Faces load ahead: a graphic that airs while the video downloads (the goal takeover) otherwise waits behind it and shows an empty frame.
  useEffect(() => {
    for (const id of new Set(rundown?.graphics.map((g) => g.player_id).filter(Boolean))) new Image().src = `/players/${id}.png`
  }, [rundown])
  const studio = useStudio(matchId, profile.lang, broadcast)
  const reels = useReels(matchId, broadcast)
  const facts = useFanFacts(matchId, broadcast)
  const neutralFan = useFanView(matchId, profile.lang, 'neutral', broadcast)
  const sched = useMemo(() => schedule(rundown), [rundown])
  const fanView = useFanView(matchId, profile.lang, profile.club, fan)
  const stops = useMemo(() => fan
    // Fan mode never holds on a play (that is the analyst's way to watch): only at full time, on the verdict and the awards.
    ? [{ id: FULL_TIME, at: duration - 0.4, s: STOP_S.fullTime }]
    // Broadcast is a live feed: it never holds either, except at full time.
    : broadcast ? [{ id: FULL_TIME, at: duration - 0.4, s: STOP_S.fullTime },
      // Plus feed: the video pauses for the goal takeover when playback reaches the ball in the net (a seek past it does not count).
      ...(feed === 'plus' ? (rundown?.graphics ?? []).filter((g) => g.type === 'goal' && typeof g.data.net_t === 'number').map((g) => ({ id: `goal@${g.id}`, at: g.data.net_t as number, s: STOP_S.takeover, smooth: true })) : [])]
    : [
      ...(bundle?.events ?? []).filter((e) => e.type === 'shot' || e.type === 'goal').map((e) => ({ id: `${e.type}@${e.t_s}`, at: e.t_s + 0.3, s: STOP_S.event })),
      ...(profile.lens === 'broadcast' ? [] : lensList.map((o) => ({ id: o.insight_id, at: o.show_t_s + 0.6, s: STOP_S.moment }))),
    ], [fan, broadcast, bundle, lensList, profile.lens, duration, rundown, feed])
  useEffect(() => {
    const prev = prevT.current
    prevT.current = time
    if (time < prev - 0.5) passed.current.clear() // looped or sought back: the moments stop again
    if (!pb.playing) return
    const hit = stops.find((s) => !passed.current.has(s.id) && prev < s.at && time >= s.at && (!('smooth' in s) || time - prev < 1))
    if (!hit) return
    passed.current.add(hit.id)
    play(false)
    setStop({ id: hit.id, s: hit.s })
  }, [time, pb.playing, stops, play])
  useEffect(() => {
    if (!stop) return
    const id = setTimeout(() => {
      setStop(null)
      if (stop.id === FULL_TIME) seek(0)
      play(true)
    }, stop.s * 1000)
    return () => clearTimeout(id)
  }, [stop, play, seek])
  // Playing again by hand (click, space, a seek that resumes) ends the hold.
  useEffect(() => { if (pb.playing && stop) setStop(null) }, [pb.playing, stop])

  const onCue = useCallback((i: number, t: number | null) => { setCue(i); if (t !== null) seek(Math.max(0, t - 1.5)) }, [seek])
  const openMoment = useCallback((id: string) => { setTab('moments'); setMomOpen(id); play(false) }, [play])
  const closeMoment = useCallback((id: string | null) => { setMomOpen(id); if (id === null) play(true) }, [play])

  if (error) {
    return (
      <section className="w-full px-[22px] py-5">
        <Alert><AlertTriangle className="mt-0.5 size-4 shrink-0" /><div><p className="font-medium">Could not load this match</p><p className="text-muted-foreground">{error}</p><a className="text-primary underline" href="#/matches">Back to Matches</a></div></Alert>
      </section>
    )
  }
  if (!bundle) return <p className="px-[22px] py-5 text-sm text-muted-foreground">Loading match...</p>

  const { meta, events } = bundle
  const short = { home: meta.teams.home.short, away: meta.teams.away.short }
  const goals = events.filter((e) => e.type === 'goal')
  const score = { home: goals.filter((e) => e.team === 'home' && e.t_s <= time).length, away: goals.filter((e) => e.team === 'away' && e.t_s <= time).length }
  // Match clock: the tracking frame at the video time, or the last event's clock plus the time since it.
  const frame = tracking.filter((f) => f.t_s <= time).at(-1)
  const lastEv = events.filter((e) => e.t_s <= time).at(-1)
  const air = broadcast ? airAt(sched, time) : null
  const ft = broadcast && stop?.id === FULL_TIME
  const takeover = broadcast && stop?.id.startsWith('goal@') ? rundown?.graphics.find((g) => `goal@${g.id}` === stop.id) : undefined
  const cueSeg = cue != null && cue >= 1 ? studio?.segments[cue - 1] : undefined
  const final = { home: goals.filter((e) => e.team === 'home').length, away: goals.filter((e) => e.team === 'away').length }
  const clockS = frame ? frame.clock_s : lastEv ? lastEv.clock_s + (time - lastEv.t_s) : 0

  const list = (l: Lens) => (available && ovs[l]?.overlays) || NONE
  const playerName = profile.player ? (names[profile.player]?.name ?? null) : null
  const views = Object.fromEntries((Object.keys(ovs) as Lens[]).map((l) => [l, buildViews(list(l), byId, time, profile, playerName)])) as Record<Lens, ReturnType<typeof buildViews>>
  const on: Record<Lens, Set<string>> = {
    analyst: latest(views.analyst, 2), fan: latest(views.fan, 1), first_match: latest(views.first_match, 1), one_metric: latest(views.one_metric, 1), broadcast: new Set(),
  }
  const windows = new Map<string, [number, number]>()
  for (const o of [...list('analyst'), ...list(profile.lens)]) windows.set(o.insight_id, [o.show_t_s, o.show_t_s + o.duration_s])
  const shown = ovs[profile.lens] ? new Set(list(profile.lens).map((o) => o.insight_id)) : null

  // The moment a concept card talks about: the open one, else the one whose overlay is on screen.
  const ctxMoment = momOpen ? (byId.get(momOpen) ?? null) : (insights.filter((i) => { const w = windows.get(i.insight_id); return !!w && time >= w[0] && time < w[1] }).at(-1) ?? null)
  const env: Env = { bundle, models, run, time, moment: ctxMoment, det, profile, shown: shown?.size ?? null, moments: insights, library: summary ? !!summary.library_id : null }

  const th = run?.interpretMeta?.thresholds
  const sprint = th?.sprint_speed_m_s != null ? { speed: th.sprint_speed_m_s, minS: th.sprint_min_s ?? 1 } : null
  const tabs = TABS[modeOf(profile.lens)]
  const shownTab: Tab = tabs.some(([k]) => k === tab) ? tab : tabs[0][0]
  const layerProps = (l: Lens) => ({ views: views[l], on: on[l], active: profile.lens === l, openId: shownTab === 'moments' ? momOpen : null, onOpen: openMoment })
  // Fan mode asks what that reader's own view suggests (written by the Supporter agent for their club and language).
  const qaExamples = fan && fanView ? fanView.ask_examples : [`Every shot by ${meta.teams.home.name}`, `Every line-breaking pass by ${meta.teams.away.name}`, 'When did the pressure change?']

  return (
    <ConceptContext.Provider value={onConcept}>
      <section className="fade-in flex w-full flex-col gap-2.5 px-[22px] pb-7 pt-3.5">
        <h1 className="sr-only">{meta.teams.home.name} vs {meta.teams.away.name}</h1>
        <div className="flex flex-wrap items-start gap-[18px]">
          <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-2">
            <AudienceBar profile={profile} onChange={setProfile} short={short} roster={bundle.roster.players} feed={broadcast ? feed : undefined} onFeed={setFeed} />
            {ovs.analyst && !available && (
              <p className="rounded-[10px] border border-dashed border-foreground/25 px-3 py-2 text-[12.5px] text-muted-foreground">
                This match has no overlays or moments: the Explain and Render stages did not run on it. The video, the controls and the Ask tab still work.
              </p>
            )}
            <VideoStage src={src} pb={pb} short={short} score={score} clock={mmss(clockS)}>
              <AnalystLayer {...layerProps('analyst')} />
              {fan ? (stop?.id !== FULL_TIME && <FanOverlay view={fanView} time={time} player={profile.player} />) : <FanLayer {...layerProps('fan')} />}
              {broadcast && <FeedLayer air={feed === 'plus' && !ft ? air : null} time={time} lang={profile.lang} names={names} teams={meta.teams} />}
              {broadcast && shownTab === 'studio' && !ft && cueSeg && time >= cueSeg.t_s - 3 && time < cueSeg.t_s + 12 && <ReplayTag text={`REPLAY · VT ${cue}`} />}
              <SpotlightLayer {...layerProps('one_metric')} />
              <NewcomerLayer {...layerProps('first_match')} />
              {!fan && !broadcast && <EventTicker events={events} time={time} names={names} teams={meta.teams} models={models} />}
              {profile.player && <PlayerFocus playerId={profile.player} roster={bundle.roster.players} tracking={tracking} events={events} time={time} names={names} sprint={sprint} es={es} />}
              {ft && <FullTimeOverlay s={stop.s} lang={profile.lang} teams={meta.teams} score={final} names={names} star={facts?.verdict.figure ?? null} view={neutralFan} opening={studio?.opening ?? null} />}
              {takeover && <GoalTakeover key={stop?.id} g={takeover} lang={profile.lang} names={names} teams={meta.teams} />}
              {stop && !ft && !takeover && (
                <div className="absolute left-1/2 top-3 z-[5] flex -translate-x-1/2 items-center gap-3 overflow-hidden rounded-full border border-primary/50 bg-[rgba(12,23,42,.92)] py-1.5 pl-3.5 pr-1.5 text-[13px] font-semibold">
                  {stop.id === FULL_TIME
                    ? <span className="text-primary">{es ? 'Final del partido · se repite en ' : 'Full time · replaying in '}<Countdown key={stop.id} s={stop.s} /> s</span>
                    : <span className="text-primary">Key moment</span>}
                  <button type="button" onClick={(e) => { e.stopPropagation(); if (stop.id === FULL_TIME) seek(0); play(true) }} className="rounded-full bg-primary px-3 py-1 text-xs font-bold text-primary-foreground">
                    {stop.id === FULL_TIME ? (es ? 'Repetir ▶' : 'Replay ▶') : 'Continue ▶'}
                  </button>
                  <span key={stop.id} className="stop-bar absolute inset-x-0 bottom-0 h-[3px] origin-left bg-primary" style={{ animationDuration: `${stop.s}s` }} />
                </div>
              )}
            </VideoStage>
            <Controls pb={pb} duration={duration} events={events} names={names} focusId={profile.player} onSeek={onSeek} />
            {broadcast && <OnAirBar air={air} next={airNext(sched, time)} clean={feed === 'clean'} ft={ft} time={time} names={names} />}
            <button type="button" onClick={onOpenHow} className="self-start py-1 text-[13px] font-semibold text-primary hover:text-foreground">How this match was made →</button>
          </div>

          <aside className="sticky top-3 flex min-w-0 max-w-full flex-[1_1_360px] flex-col overflow-hidden rounded-[14px] border border-foreground/10 bg-panel">
            <div role="tablist" className="flex gap-0.5 border-b border-foreground/10 p-1.5">
              {tabs.map(([k, l]) => (
                <button
                  key={k} type="button" role="tab" aria-selected={shownTab === k} onClick={() => setTab(k)}
                  className={cn('flex-1 rounded-lg px-1.5 py-[9px] text-[13px] font-semibold transition-colors duration-150', shownTab === k ? 'bg-[#1f2b40] text-foreground' : 'text-muted-foreground hover:text-foreground')}
                >
                  {l}
                </button>
              ))}
            </div>
            <div className="h-[calc(100vh-130px)] min-h-[420px] overflow-auto px-3.5 pb-[18px] pt-3">
              {shownTab === 'moments' && fan && (
                <FanStory view={fanView} events={events} teams={meta.teams} time={time} final={time >= duration - 0.5} player={profile.player} playerName={playerName} />
              )}
              {shownTab === 'moments' && !fan && (
                <MomentsTab
                  insights={insights} bundle={bundle} profile={profile} texts={texts} shown={shown} windows={windows} time={time}
                  openId={momOpen} onOpen={closeMoment} onSeek={onSeek}
                />
              )}
              {shownTab === 'stats' && <StatsTab sprint={sprint} bundle={bundle} tracking={tracking} time={time} focusId={profile.player} names={names} models={models} det={det} onDet={setDet} onSeek={onSeek} />}
              {shownTab === 'studio' && <StudioScriptView script={studio} cue={cue} onCue={onCue} />}
              {shownTab === 'reels' && <ReelsTab matchId={matchId} reels={reels} rundown={rundown} names={names} lang={profile.lang} time={time} />}
              {shownTab === 'ask' && (
                <AskTab
                  matchId={matchId} lang={profile.lang} examples={qaExamples} placeholder={qaExamples[0]} insights={insights} events={events}
                  names={names} texts={texts} onSeek={onSeek} fan={fan ? { club: profile.club, view: fanView } : undefined}
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
