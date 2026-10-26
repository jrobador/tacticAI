import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowLeft, ListChecks, Loader2 } from 'lucide-react'
import { getClipManifest, getHeatmaps, getInsights, getOverlays, getRecap, loadMatch, videoUrl } from '@/api/client'
import type { ClipManifest, Heatmaps, Insight, MatchBundle, Overlay, OverlaysResponse, Recap } from '@/api/types'
import { AskBox } from '@/components/AskBox'
import { AnalysisPanel } from '@/components/AnalysisPanel'
import { BroadcastConsole } from '@/components/BroadcastConsole'
import { CardActions } from '@/components/CardActions'
import { EventTimeline } from '@/components/EventTimeline'
import { EvidencePanel } from '@/components/EvidencePanel'
import { GuideHint, guideStep } from '@/components/GuideHint'
import { LivePanel } from '@/components/LivePanel'
import { MetricStrip } from '@/components/MetricStrip'
import { OverlayLayer } from '@/components/OverlayLayer'
import { Player, type SeekRequest } from '@/components/Player'
import { PlayerCard } from '@/components/PlayerCard'
import { DEFAULT_PROFILE, ProfileBar, queryOf, type Profile } from '@/components/ProfileBar'
import { RecapPanel } from '@/components/RecapPanel'
import { TeamTag } from '@/components/TeamTag'
import { TrailStrip } from '@/components/TrailStrip'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { Names } from '@/lib/format'
import { go } from '@/lib/nav'
import { currentOverlay } from '@/lib/overlays'

const NO_OVERLAYS: Overlay[] = []

export function Watch({ matchId }: { matchId: string }) {
  const [bundle, setBundle] = useState<MatchBundle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [time, setTime] = useState(0)
  const [seek, setSeek] = useState<SeekRequest | null>(null)
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE)
  const [overlays, setOverlays] = useState<OverlaysResponse | null>(null)
  const [insights, setInsights] = useState<Insight[]>([])
  const [heatmaps, setHeatmaps] = useState<Heatmaps | null>(null)
  const [manifest, setManifest] = useState<ClipManifest | null>(null)
  const [open, setOpen] = useState<Overlay | null>(null)
  const [openedEvidence, setOpenedEvidence] = useState(false)
  const [switchedLens, setSwitchedLens] = useState(false)
  const [recapOpen, setRecapOpen] = useState(false)
  const [recap, setRecap] = useState<{ key: string; data: Recap | null } | null>(null)

  // The route mounts Watch with key={matchId}, so state never carries over; `live` drops a load that outlives its mount.
  useEffect(() => {
    let live = true
    loadMatch(matchId).then((b) => live && setBundle(b)).catch((e: Error) => live && setError(e.message))
    return () => { live = false }
  }, [matchId])

  // Every profile change asks /overlays again. A failure just means no overlays: the player and the analysis stay.
  useEffect(() => {
    let live = true
    getOverlays(matchId, queryOf(profile)).then((r) => live && setOverlays(r)).catch(() => live && setOverlays({ available: false }))
    return () => { live = false }
  }, [matchId, profile])

  // These files only exist for matches the Explain and Render stages ran on; they load once /overlays said available.
  const available = overlays?.available === true
  useEffect(() => {
    if (!available) return
    let live = true
    getInsights(matchId).then((r) => live && setInsights(r)).catch(() => {})
    getHeatmaps(matchId).then((r) => live && setHeatmaps(r)).catch(() => {})
    getClipManifest(matchId).then((r) => live && setManifest(r)).catch(() => {})
    return () => { live = false }
  }, [matchId, available])

  // The recap loads when it is opened (button or end of the video) for the active lens, language and club.
  const recapKey = `${profile.lens}|${profile.lang}|${profile.club}`
  useEffect(() => {
    if (!recapOpen || !available) return
    let live = true
    getRecap(matchId, profile.lens, profile.lang, profile.club)
      .then((d) => live && setRecap({ key: recapKey, data: d }))
      .catch(() => live && setRecap({ key: recapKey, data: null }))
    return () => { live = false }
  }, [matchId, recapOpen, available, recapKey, profile.lens, profile.lang, profile.club])

  const names = useMemo<Names>(() => Object.fromEntries((bundle?.roster.players ?? []).map((p) => [p.player_id, p])), [bundle])
  const doSeek = useCallback((t: number) => setSeek((s) => ({ t, n: (s?.n ?? 0) + 1 })), [])
  const list = (available && overlays?.overlays) || NO_OVERLAYS
  const onVideo = profile.lens === 'broadcast' ? NO_OVERLAYS : list
  const eventTimes = useMemo(() => (bundle?.events ?? []).map((e) => e.t_s), [bundle])
  const closeEvidence = useCallback(() => setOpen(null), [])
  const openEvidence = useCallback((o: Overlay) => { setOpen(o); setOpenedEvidence(true) }, [])
  const changeProfile = useCallback((p: Profile) => {
    if (p.lens !== profile.lens) setSwitchedLens(true)
    setProfile(p)
  }, [profile.lens])

  if (error) {
    return (
      <div className="flex flex-col gap-3">
        <Button variant="ghost" size="sm" className="self-start" onClick={() => go('/ask')}><ArrowLeft /> Library</Button>
        <Alert><AlertTriangle className="mt-0.5 size-4 shrink-0" /><div><p className="font-medium">Could not load this match</p><p className="text-muted-foreground">{error}</p></div></Alert>
      </div>
    )
  }
  if (!bundle) return <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Loading match...</p>

  const { meta } = bundle
  const duration = meta.video.frames / meta.video.fps
  const onScreen = open ?? currentOverlay(list, time)
  const step = guideStep(openedEvidence, switchedLens)
  const clubName = profile.club === 'neutral' ? 'both clubs' : meta.teams[profile.club].name
  const metricSeries = overlays?.metric_series
  const card = overlays?.player_card
  const insightOf = (o: Overlay) => insights.find((i) => i.insight_id === o.insight_id)
  const actions = (o: Overlay) => <CardActions matchId={matchId} overlay={o} insight={insightOf(o)} bundle={bundle} manifest={manifest} />
  const console_ = profile.lens === 'broadcast' && available && (
    <BroadcastConsole overlays={list} time={time} brand={overlays?.brand_tokens ?? null} actions={actions} />
  )

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex flex-wrap items-center gap-3 text-xl font-semibold">
          <TeamTag side="home" name={meta.teams.home.name} /> <span className="text-muted-foreground">vs</span> <TeamTag side="away" name={meta.teams.away.name} />
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{meta.formations.home} v {meta.formations.away}</Badge>
          <Badge>{Math.round(duration)} s of video</Badge>
          <Badge>{meta.source.kind}</Badge>
          {available && <Button variant="outline" size="sm" onClick={() => setRecapOpen(true)}><ListChecks /> Recap</Button>}
          <Button variant="ghost" size="sm" onClick={() => go('/ask')}>Library</Button>
        </div>
      </div>

      {available && (
        <>
          <ProfileBar
            profile={profile} onChange={changeProfile} spotlightLens={step === 2}
            clubs={{ home: meta.teams.home.short, away: meta.teams.away.short }}
            teamNames={{ home: meta.teams.home.name, away: meta.teams.away.name }} roster={bundle.roster.players}
          />
          <GuideHint step={step} onShowOverlay={() => doSeek((list.find((o) => o.slot) ?? list[0])?.show_t_s ?? 0)} />
        </>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex min-w-0 flex-col gap-4">
          <Player
            key={matchId} src={videoUrl(matchId)} duration={duration} seek={seek} onTime={setTime}
            onLoop={() => available && setRecapOpen(true)}
          >
            {available && <OverlayLayer overlays={onVideo} time={time} lens={overlays?.lens ?? profile.lens} onOpen={openEvidence} />}
            {open && <EvidencePanel overlay={open} insight={insightOf(open)} eventTimes={eventTimes} onSeek={doSeek} onClose={closeEvidence} actions={actions(open)} />}
            {recapOpen && (
              <RecapPanel
                recap={recap?.key === recapKey ? recap.data : null} loading={recap?.key !== recapKey} lens={profile.lens} clubName={clubName}
                insights={insights} onSeek={doSeek} onClose={() => setRecapOpen(false)}
              />
            )}
          </Player>
          <AskBox matchId={matchId} lang={profile.lang} onSeek={doSeek} />
          <TrailStrip available={available} trail={onScreen?.trail ?? null} />
          {profile.lens === 'one_metric' && metricSeries && (
            <MetricStrip series={metricSeries} duration={duration} time={time} names={{ home: meta.teams.home.short, away: meta.teams.away.short }} onSeek={doSeek} />
          )}
          {card && <PlayerCard card={card} player={names[card.player_id]} crestName={card.player_id.startsWith('away') ? meta.teams.away.name : meta.teams.home.name} heatmaps={heatmaps} insights={insights} onSeek={doSeek} />}
          <Card>
            <CardContent className="p-4">
              <h2 className="mb-3 text-sm font-semibold">Event timeline</h2>
              <EventTimeline events={bundle.events} names={names} duration={duration} time={time} onSeek={doSeek} />
            </CardContent>
          </Card>
        </div>
        <div className="flex min-h-0 flex-col gap-4 lg:max-h-[calc(100vh-7rem)] lg:sticky lg:top-20 lg:self-start lg:w-full lg:overflow-y-auto">
          {console_}
          <LivePanel bundle={bundle} names={names} time={time} />
        </div>
      </div>

      <AnalysisPanel bundle={bundle} names={names} />
    </div>
  )
}
