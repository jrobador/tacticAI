import { useState, type ReactNode } from 'react'
import { Check } from 'lucide-react'
import type { BrandTokens, Overlay } from '@/api/types'
import { mmss } from '@/lib/format'
import { cn } from '@/lib/utils'

type State = 'next' | 'on_air' | 'aired'
const STATE_LABEL: Record<State, string> = { next: 'Next', on_air: 'On air', aired: 'Aired' }
const stateOf = (o: Overlay, t: number): State => (t < o.show_t_s ? 'next' : t < o.show_t_s + o.duration_s ? 'on_air' : 'aired')

/**
 * Broadcast console: the queue of graphics (next, on air, aired) by the video clock. Approve only marks the graphic here:
 * there is no real output. The brand tokens style the graphics of the console and nothing else.
 */
export function BroadcastConsole({ overlays, time, brand, actions }: {
  overlays: Overlay[]; time: number; brand: BrandTokens | null; actions?: (o: Overlay) => ReactNode
}) {
  const [approved, setApproved] = useState<Set<string>>(new Set())
  const toggle = (id: string) => setApproved((s) => { const n = new Set(s); if (!n.delete(id)) n.add(id); return n })
  const queue = [...overlays].sort((a, b) => a.show_t_s - b.show_t_s)
  const onAir = queue.filter((o) => stateOf(o, time) === 'on_air').length
  return (
    <section aria-label="Broadcast console" className="flex flex-col gap-2 rounded-lg border bg-card p-3">
      <header className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Broadcast console</h2>
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          {brand && <><img src={brand.logo} alt="" className="size-5 object-contain" />{brand.name}</>}
          <span className={cn('rounded-full border px-2 py-0.5', onAir > 0 && 'border-primary text-primary')}>{onAir > 0 ? `${onAir} on air` : 'off air'}</span>
        </span>
      </header>
      {queue.length === 0 && <p className="text-sm text-muted-foreground">No graphics in the queue for this profile.</p>}
      <ol className="flex max-h-[28rem] flex-col gap-2 overflow-y-auto pr-1">
        {queue.map((o) => {
          const st = stateOf(o, time)
          const ok = approved.has(o.insight_id)
          const style = brand ? { background: brand.colors.background, color: brand.colors.foreground, fontFamily: brand.font_family, borderColor: st === 'on_air' ? brand.colors.accent : undefined } : undefined
          return (
            <li key={o.overlay_id} data-state={st} style={style} className={cn('rounded-md border p-3', st === 'aired' && 'opacity-60', st === 'on_air' && 'border-2')}>
              <div className="flex items-center justify-between gap-2 text-[11px] uppercase tracking-wide" style={brand ? { color: brand.colors.accent } : undefined}>
                <span className="font-semibold">{STATE_LABEL[st]}</span>
                <span className="tabular-nums">{mmss(o.show_t_s)} · {o.duration_s}s</span>
              </div>
              <p className="mt-1 font-semibold leading-tight">{o.title}</p>
              <p className="mt-0.5 text-xs opacity-80">{o.text}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <button
                  type="button" aria-pressed={ok} onClick={() => toggle(o.insight_id)}
                  className="inline-flex h-7 items-center gap-1 rounded-md border px-2 text-xs font-medium"
                  style={brand ? { borderColor: brand.colors.accent, background: ok ? brand.colors.accent : 'transparent', color: ok ? brand.colors.background : brand.colors.foreground } : undefined}
                >
                  <Check className="size-3" /> {ok ? 'Approved' : 'Approve'}
                </button>
                {actions?.(o)}
              </div>
              <details className="mt-2 text-xs">
                <summary className="cursor-pointer opacity-80">JSON</summary>
                <pre className="mt-1 max-h-48 overflow-auto rounded bg-black/30 p-2 text-[11px] leading-snug">{JSON.stringify(o, null, 2)}</pre>
              </details>
            </li>
          )
        })}
      </ol>
      <p className="text-[11px] text-muted-foreground">Approve marks the graphic in this console. There is no real broadcast output.</p>
    </section>
  )
}
