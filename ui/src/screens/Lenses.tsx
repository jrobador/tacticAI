import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, ArrowLeft, Loader2 } from 'lucide-react'
import { getClipManifest, getInsights, getOverlays, loadMatch, videoUrl } from '@/api/client'
import type { ClipManifest, Insight, Lang, Lens, MatchBundle, Overlay, OverlaysResponse, Club } from '@/api/types'
import { BroadcastConsole } from '@/components/BroadcastConsole'
import { CardActions } from '@/components/CardActions'
import { OverlayLayer } from '@/components/OverlayLayer'
import { Player } from '@/components/Player'
import { ClubSegmented, LENS_LABEL, Segmented } from '@/components/ProfileBar'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { go } from '@/lib/nav'

const PANES: Lens[] = ['analyst', 'fan', 'broadcast']
const NO_OVERLAYS: Overlay[] = []
const DRIFT_S = 0.2

/** Makes `mirror` follow `master`: pause, play, seek, playback rate and end, and a correction when it drifts more than 0.2 s. */
function useMirror(master: HTMLVideoElement | null, mirror: React.RefObject<HTMLVideoElement | null>) {
  useEffect(() => {
    const v = mirror.current
    if (!master || !v) return
    const sync = () => {
      if (v.playbackRate !== master.playbackRate) v.playbackRate = master.playbackRate
      if (Math.abs(v.currentTime - master.currentTime) > DRIFT_S || master.paused) {
        if (Math.abs(v.currentTime - master.currentTime) > 0.02) v.currentTime = master.currentTime
      }
      if (master.paused || master.ended) { if (!v.paused) v.pause() } else if (v.paused) v.play().catch(() => {})
    }
    const events = ['play', 'pause', 'seeking', 'seeked', 'ratechange', 'ended', 'timeupdate'] as const
    events.forEach((e) => master.addEventListener(e, sync))
    v.addEventListener('loadedmetadata', sync)
    const id = setInterval(sync, 250)
    sync()
    return () => {
      events.forEach((e) => master.removeEventListener(e, sync))
      v.removeEventListener('loadedmetadata', sync)
      clearInterval(id)
    }
  }, [master, mirror])
}

function Mirror({ src, master, children }: { src: string | null; master: HTMLVideoElement | null; children: React.ReactNode }) {
  const ref = useRef<HTMLVideoElement>(null)
  useMirror(master, ref)
  return (
    <div className="relative">
      {src ? <video ref={ref} src={src} muted playsInline loop aria-label="Mirror of the master video" className="aspect-video w-full rounded-lg bg-black" /> : <div className="aspect-video w-full rounded-lg border bg-muted" />}
      {children}
    </div>
  )
}

function usePaneOverlays(matchId: string, lens: Lens, lang: Lang, club: Club) {
  const [res, setRes] = useState<OverlaysResponse | null>(null)
  useEffect(() => {
    let live = true
    getOverlays(matchId, { lens, lang, club, brand: lens === 'broadcast' ? 'tacticai' : null }).then((r) => live && setRes(r)).catch(() => live && setRes({ available: false }))
    return () => { live = false }
  }, [matchId, lens, lang, club])
  return res
}

function Pane({ matchId, lens, lang, club, time, master, bundle, insights, manifest, duration, onTime, onVideo }: {
  matchId: string; lens: Lens; lang: Lang; club: Club; time: number; master: HTMLVideoElement | null; bundle: MatchBundle
  insights: Insight[]; manifest: ClipManifest | null; duration: number; onTime?: (t: number) => void; onVideo?: (v: HTMLVideoElement | null) => void
}) {
  const res = usePaneOverlays(matchId, lens, lang, club)
  const list = res?.overlays ?? NO_OVERLAYS
  const layer = res?.available && lens !== 'broadcast' ? <OverlayLayer overlays={list} time={time} lens={lens} onOpen={() => {}} compact /> : null
  const isMaster = !!onTime
  return (
    <section aria-label={`${LENS_LABEL[lens]} lens`} className="flex min-w-0 flex-col gap-3">
      <h2 className="flex items-center justify-between text-sm font-semibold">
        <span>{LENS_LABEL[lens]}</span>
        <span className="text-xs font-normal text-muted-foreground">{isMaster ? 'master video' : 'mirror, muted'} · {res ? (res.available ? `${list.length} graphics` : 'no overlays') : 'loading'}</span>
      </h2>
      {isMaster ? (
        <Player src={videoUrl(matchId)} duration={duration} seek={null} onTime={onTime} onVideo={onVideo}>{layer}</Player>
      ) : (
        <Mirror src={videoUrl(matchId)} master={master}>{layer}</Mirror>
      )}
      {lens === 'broadcast' && res?.available && (
        <BroadcastConsole
          overlays={list} time={time} brand={res.brand_tokens ?? null}
          actions={(o) => <CardActions matchId={matchId} overlay={o} insight={insights.find((i) => i.insight_id === o.insight_id)} bundle={bundle} manifest={manifest} />}
        />
      )}
    </section>
  )
}

/** Three lenses on the same match: one master video and two muted mirrors; each pane asks for its own /overlays. */
export function Lenses({ matchId }: { matchId: string }) {
  const [bundle, setBundle] = useState<MatchBundle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [time, setTime] = useState(0)
  const [master, setMaster] = useState<HTMLVideoElement | null>(null)
  const [lang, setLang] = useState<Lang>('en')
  const [club, setClub] = useState<Club>('neutral')
  const [insights, setInsights] = useState<Insight[]>([])
  const [manifest, setManifest] = useState<ClipManifest | null>(null)

  useEffect(() => {
    let live = true
    loadMatch(matchId).then((b) => live && setBundle(b)).catch((e: Error) => live && setError(e.message))
    getInsights(matchId).then((r) => live && setInsights(r)).catch(() => {})
    getClipManifest(matchId).then((r) => live && setManifest(r)).catch(() => {})
    return () => { live = false }
  }, [matchId])
  const onVideo = useCallback((v: HTMLVideoElement | null) => setMaster(v), [])

  if (error) {
    return (
      <div className="flex flex-col gap-3">
        <Button variant="ghost" size="sm" className="self-start" onClick={() => go('/')}><ArrowLeft /> Watch</Button>
        <Alert><AlertTriangle className="mt-0.5 size-4 shrink-0" /><div><p className="font-medium">Could not load this match</p><p className="text-muted-foreground">{error}</p></div></Alert>
      </div>
    )
  }
  if (!bundle) return <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Loading match...</p>
  const { meta } = bundle
  const duration = meta.video.frames / meta.video.fps
  const field = 'flex items-center gap-2 text-xs text-muted-foreground'
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Three lenses · {meta.teams.home.name} vs {meta.teams.away.name}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <div className={field}>Language <Segmented name="Language" value={lang} options={[{ value: 'en', label: 'EN' }, { value: 'es', label: 'ES' }]} onChange={setLang} /></div>
          <div className={field}>My club <ClubSegmented value={club} onChange={setClub} clubs={{ home: meta.teams.home.short, away: meta.teams.away.short }} /></div>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">The same match, three audiences. The Analyst video drives the other two.</p>
      <div className="grid items-start gap-5 xl:grid-cols-3">
        {PANES.map((lens, k) => (
          <Pane
            key={lens} matchId={matchId} lens={lens} lang={lang} club={club} time={time} master={master} bundle={bundle}
            insights={insights} manifest={manifest} duration={duration}
            {...(k === 0 ? { onTime: setTime, onVideo } : {})}
          />
        ))}
      </div>
    </div>
  )
}
