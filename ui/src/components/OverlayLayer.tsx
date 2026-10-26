import { useEffect, useRef, useState } from 'react'
import type { Lens, Overlay, Slot } from '@/api/types'
import { cn } from '@/lib/utils'
import { fmtMetric, metricLabel, unitLabel, visibleOverlays } from '@/lib/overlays'

// Slots sit above the native video controls (bottom) and below the top edge.
const SLOT: Record<Slot, string> = {
  bottom_left: 'bottom-14 left-3 items-start',
  bottom_right: 'bottom-14 right-3 items-end',
  top_right: 'top-3 right-3 items-end',
}
const FROM_RIGHT: Slot[] = ['top_right', 'bottom_right']

const reduced = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

/** Counts a number up from 0 when it appears; reduced motion shows the final value at once. */
function CountUp({ value, unit, animate }: { value: number; unit: string; animate: boolean }) {
  const [v, setV] = useState(animate && !reduced() ? 0 : value)
  useEffect(() => {
    if (!animate || reduced()) { setV(value); return }
    let raf = 0
    const start = performance.now()
    const tick = (now: number) => {
      const k = Math.min(1, (now - start) / 700)
      setV(value * (1 - Math.pow(1 - k, 3)))
      if (k < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, animate])
  return <>{fmtMetric({ value: v, unit })}</>
}

function Card({ o, t, lens, onOpen, compact }: { o: Overlay; t: number; lens: Lens; onOpen: (o: Overlay) => void; compact?: boolean }) {
  const leaving = t >= o.show_t_s + o.duration_s
  // Entering only plays when the overlay has just appeared (not after a seek into its middle or a lens switch).
  const fresh = t - o.show_t_s < 0.6
  const motion = leaving ? 'ov-out' : fresh ? (o.slot && FROM_RIGHT.includes(o.slot) ? 'ov-in-right' : 'ov-in-left') : ''
  const dense = lens === 'analyst'
  const entries = Object.entries(o.metrics).slice(0, compact ? 1 : undefined)
  return (
    <button
      type="button"
      onClick={() => onOpen(o)}
      aria-label={`${o.title}. Open evidence`}
      className={cn(
        'pointer-events-auto rounded-lg border border-l-4 border-border border-l-primary bg-background/90 text-left shadow-lg backdrop-blur transition-colors hover:bg-background focus-visible:outline-2',
        compact ? 'w-[32%] min-w-[96px] p-1.5' : cn('max-w-[300px] p-3', dense ? 'w-[280px]' : 'w-[300px]'),
        motion,
      )}
    >
      <p className={cn('font-heading font-semibold leading-tight', compact ? 'text-[10px]' : dense ? 'text-sm' : 'text-lg')}>{o.title}</p>
      {o.text && !compact && <p className={cn('mt-1 text-muted-foreground', dense ? 'text-xs' : 'text-sm')}>{o.text}</p>}
      <div className={cn('flex flex-wrap gap-x-4 gap-y-1', compact ? 'mt-1' : 'mt-2')}>
        {entries.map(([k, m]) => (
          <div key={k}>
            <span className={cn('font-heading font-semibold text-primary', compact ? 'text-xs' : dense ? 'text-base' : 'text-2xl')}>
              <CountUp value={m.value} unit={m.unit} animate={fresh && !leaving} />
            </span>{' '}
            <span className="text-[11px] text-muted-foreground">{unitLabel(m.unit)}{dense && !compact ? ` · ${metricLabel(k)}` : ''}</span>
          </div>
        ))}
      </div>
      {!compact && <p className="mt-2 text-[11px] text-primary">Evidence →</p>}
    </button>
  )
}

function Layer({ overlays, t, lens, onOpen, out, compact }: { overlays: Overlay[]; t: number; lens: Lens; onOpen: (o: Overlay) => void; out?: boolean; compact?: boolean }) {
  const visible = visibleOverlays(overlays, t)
  return (
    <div className={cn('absolute inset-0', out ? 'fade-out pointer-events-none' : 'fade-in')}>
      {(Object.keys(SLOT) as Slot[]).map((slot) => {
        const here = visible.filter((o) => o.slot === slot)
        return here.length ? (
          <div key={slot} className={cn('absolute flex flex-col gap-2', SLOT[slot])}>
            {here.map((o) => <Card key={o.overlay_id} o={o} t={t} lens={lens} onOpen={onOpen} compact={compact} />)}
          </div>
        ) : null
      })}
    </div>
  )
}

interface Props { overlays: Overlay[]; time: number; lens: Lens; onOpen: (o: Overlay) => void; compact?: boolean }

/** Overlays over the video, synced to its clock. A new set (lens, language or club) crossfades with the old one. */
export function OverlayLayer({ overlays, time, lens, onOpen, compact }: Props) {
  const [prev, setPrev] = useState<{ overlays: Overlay[]; lens: Lens } | null>(null)
  const [gen, setGen] = useState(0)
  const last = useRef({ overlays, lens })
  useEffect(() => {
    if (last.current.overlays === overlays) return
    setPrev(last.current)
    setGen((g) => g + 1)
    last.current = { overlays, lens }
    const id = setTimeout(() => setPrev(null), 320)
    return () => clearTimeout(id)
  }, [overlays, lens])
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-lg">
      {prev && <Layer key="prev" overlays={prev.overlays} t={time} lens={prev.lens} onOpen={onOpen} out compact={compact} />}
      <Layer key={gen} overlays={overlays} t={time} lens={lens} onOpen={onOpen} compact={compact} />
    </div>
  )
}
