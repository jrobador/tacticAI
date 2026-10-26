import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Pause, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { mmss } from '@/lib/format'

export interface SeekRequest { t: number; n: number }
interface Props {
  src: string | null // null: no mp4 (mock mode), a clock stands in for the video
  duration: number
  seek: SeekRequest | null
  onTime: (t: number) => void
  onVideo?: (v: HTMLVideoElement | null) => void // the element, for mirrors that follow it
  onLoop?: () => void // the video wrapped around to the start (it loops, so it never ends)
  children?: ReactNode // the overlay layer, drawn over the video
}

/**
 * The video (the engine already draws score and clock in it, so the UI adds none) or, without a file, a stand-in clock.
 * It starts muted and loops; if the browser blocks autoplay, a large play button asks for the click.
 */
export function Player({ src, duration, seek, onTime, onVideo, onLoop, children }: Props) {
  const video = useRef<HTMLVideoElement>(null)
  const [fallback, setFallback] = useState(false)
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [blocked, setBlocked] = useState(false)
  const standIn = src === null || fallback
  const last = useRef(0)
  const clock = useRef(0) // stand-in clock
  const loopRef = useRef(onLoop)
  loopRef.current = onLoop
  const tick = (t: number) => {
    if (last.current - t > duration / 2) onLoop?.()
    last.current = t
    onTime(t)
  }

  useEffect(() => {
    onVideo?.(standIn ? null : video.current)
    return () => onVideo?.(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [standIn])

  useEffect(() => {
    if (!seek) return
    if (!standIn && video.current) video.current.currentTime = seek.t
    clock.current = seek.t
    setT(seek.t)
    onTime(seek.t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seek])

  useEffect(() => {
    if (standIn) return
    video.current?.play().catch(() => setBlocked(true))
  }, [standIn])

  useEffect(() => {
    if (!standIn || !playing) return
    const id = setInterval(() => {
      const next = clock.current + 0.1
      if (next >= duration) loopRef.current?.() // loops like the video
      clock.current = next >= duration ? 0 : next
      setT(clock.current)
    }, 100)
    return () => clearInterval(id)
  }, [standIn, playing, duration])

  useEffect(() => {
    if (standIn) onTime(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t, standIn])

  const bigPlay = (onClick: () => void) => (
    <button type="button" onClick={onClick} aria-label="Play the match" className="absolute inset-0 z-20 flex items-center justify-center bg-background/40 backdrop-blur-[2px]">
      <span className="flex size-20 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-xl transition-transform hover:scale-105"><Play className="size-9 translate-x-0.5" /></span>
    </button>
  )

  if (!standIn) {
    return (
      <div className="relative">
        <video
          ref={video}
          src={src ?? undefined}
          controls
          muted
          loop
          autoPlay
          playsInline
          className="aspect-video w-full rounded-lg bg-black"
          onPlay={() => setBlocked(false)}
          onTimeUpdate={(e) => tick(e.currentTarget.currentTime)}
          onSeeked={(e) => { last.current = e.currentTarget.currentTime; onTime(e.currentTarget.currentTime) }}
          onError={() => setFallback(true)}
        />
        {children}
        {blocked && bigPlay(() => { void video.current?.play() })}
      </div>
    )
  }
  return (
    <div className="relative flex aspect-video w-full flex-col justify-between rounded-lg border bg-muted p-4">
      <p className="max-w-md text-sm text-muted-foreground">
        {src === null ? 'No video in mock mode.' : 'The video could not be loaded.'} A stand-in clock drives the timeline, the overlays and the live panel.
      </p>
      {children}
      <div className="relative z-[1] flex items-center gap-3">
        <Button size="sm" onClick={() => setPlaying((p) => !p)} aria-label={playing ? 'Pause' : 'Play'}>
          {playing ? <Pause /> : <Play />}
        </Button>
        <input
          type="range" min={0} max={duration} step={0.1} value={t} aria-label="Seek"
          onChange={(e) => { clock.current = Number(e.target.value); setT(clock.current) }}
          className="h-1.5 flex-1 accent-[var(--lime)]"
        />
        <span className="w-24 text-right text-sm tabular-nums">{mmss(t)} / {mmss(duration)}</span>
      </div>
    </div>
  )
}
