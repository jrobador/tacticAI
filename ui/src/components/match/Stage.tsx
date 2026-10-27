// The video with its score bug and overlay layers, and the controls row.
import { useEffect, useState, type ReactNode } from 'react'
import type { EnrichedEvent } from '@/api/types'
import { eventTitle, mmss, type Names } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { usePlayback } from './usePlayback'

/** Seconds left of a hold, counting down from `s`. */
export function Countdown({ s }: { s: number }) {
  const [left, setLeft] = useState(s)
  useEffect(() => {
    const id = setInterval(() => setLeft((x) => Math.max(0, x - 1)), 1000)
    return () => clearInterval(id)
  }, [])
  return <span className="font-mono">{left}</span>
}

export type Playback = ReturnType<typeof usePlayback>
const STRIPES = 'bg-[repeating-linear-gradient(135deg,#111D32_0_14px,#0E192C_14px_28px)]'

interface StageProps {
  src: string | null
  pb: Playback
  short: Record<'home' | 'away', string>
  score: Record<'home' | 'away', number>
  clock: string
  children: ReactNode
}

export function VideoStage({ src, pb, short, score, clock, children }: StageProps) {
  return (
    <div
      className={cn('relative aspect-video w-full overflow-hidden rounded-[14px] border border-foreground/10 [container-type:inline-size]', STRIPES)}
    >
      {pb.standIn ? (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-1.5 text-center">
          <span className="font-mono text-[13px] font-semibold tracking-[.14em] text-dim">{src === null ? 'NO VIDEO IN MOCK MODE' : 'THE VIDEO COULD NOT BE LOADED'}</span>
          <span className="font-mono text-xs text-[#5e6573]">A stand-in clock drives the overlays</span>
        </div>
      ) : (
        <video
          ref={pb.videoRef} src={src ?? undefined} muted loop autoPlay playsInline preload="auto" aria-label="Match video"
          className="absolute left-0 top-0 size-full object-cover"
          onLoadedData={() => pb.play(true)} onPlay={pb.onPlay} onPause={pb.onPause}
          onTimeUpdate={(e) => pb.onTimeUpdate(e.currentTarget.currentTime)} onError={pb.onError}
        />
      )}
      <div className="absolute left-3 top-3 z-[3] flex items-center gap-[9px] rounded-lg border border-foreground/10 bg-[rgba(12,23,42,.9)] px-[11px] py-1.5 font-heading text-[13.5px] font-semibold">
        <span>{short.home}</span>
        <span className="min-w-7 text-center text-primary">{score.home}–{score.away}</span>
        <span>{short.away}</span>
        <span className="h-3.5 w-px bg-foreground/20" />
        <span className="flex items-center gap-1.5 font-mono text-[12.5px] font-semibold">
          <span className={cn('size-[7px] rounded-full', pb.playing ? 'tai-pulse bg-primary' : 'bg-dim')} />{clock}
        </span>
      </div>
      {/* A click on the picture (not on an overlay card) plays or pauses. */}
      <div className="absolute inset-0 z-[2] cursor-pointer" onClick={(e) => { if (e.target === e.currentTarget) pb.toggle() }}>{children}</div>
    </div>
  )
}


interface ControlsProps {
  pb: Playback
  duration: number
  events: EnrichedEvent[]
  names: Names
  focusId: string | null
  onSeek: (t: number) => void
}

export function Controls({ pb, duration, events, names, focusId, onSeek }: ControlsProps) {
  const pct = `${Math.min(100, (pb.time / duration) * 100).toFixed(2)}%`
  return (
    <div className="flex items-center gap-3">
      <button
        type="button" onClick={pb.toggle} aria-label={pb.playing ? 'Pause' : 'Play'}
        className="grid size-8 flex-none place-items-center rounded-full border border-foreground/20 bg-[#152034] text-[11px] font-semibold hover:border-primary active:scale-[.94]"
      >
        {pb.playing ? '❚❚' : '▶'}
      </button>
      <div
        className="relative h-7 flex-1 cursor-pointer" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); onSeek(((e.clientX - r.left) / r.width) * duration) }}
      >
        <span className="absolute inset-x-0 top-[13px] h-0.5 rounded-sm bg-foreground/20" />
        <span className="absolute left-0 top-[13px] h-0.5 rounded-sm bg-foreground" style={{ width: pct }} />
        {events.map((e, i) => {
          const focus = !!focusId && (e.player_id === focusId || e.to_player_id === focusId)
          const label = `${mmss(e.t_s)} · ${eventTitle(e, names)}`
          const shape =
            e.type === 'goal' ? { size: 12, radius: '50%', bg: 'var(--lime)', border: '0', tf: '' }
            : e.type === 'shot' ? { size: 11, radius: '50%', bg: 'var(--navy)', border: '2px solid var(--lime)', tf: '' }
            : e.type === 'pass' ? { size: 8, radius: '1px', bg: 'var(--offwhite)', border: '0', tf: 'rotate(45deg)' }
            : { size: 7, radius: '50%', bg: 'var(--dim)', border: '0', tf: '' }
          return (
            <button
              key={`${e.t_s}-${i}`} type="button" title={label} aria-label={label}
              onClick={(ev) => { ev.stopPropagation(); onSeek(e.t_s) }}
              className="absolute top-0.5 grid size-6 -ml-3 place-items-center border-0 bg-transparent p-0"
              style={{ left: `${((e.t_s / duration) * 100).toFixed(2)}%` }}
            >
              <span
                className="transition-transform duration-150"
                style={{
                  width: shape.size, height: shape.size, borderRadius: shape.radius, background: shape.bg, border: shape.border,
                  transform: `${shape.tf} ${focus ? 'scale(1.45)' : ''}`.trim() || 'none', boxShadow: '0 0 0 2px var(--navy)',
                }}
              />
            </button>
          )
        })}
        <span className="absolute top-[3px] -ml-px h-[22px] w-0.5 rounded-[1px] bg-primary" style={{ left: pct }} />
      </div>
    </div>
  )
}
