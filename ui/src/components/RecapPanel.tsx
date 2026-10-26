import { X } from 'lucide-react'
import type { Insight, Lens, Recap } from '@/api/types'
import { LENS_LABEL } from '@/components/ProfileBar'
import { mmss } from '@/lib/format'
import { resolve } from '@/lib/overlays'

/** The recap of the active lens and club (analyst recap for broadcast and one_metric). It is per lens, language and club, not per player. */
export function RecapPanel({ recap, loading, lens, clubName, insights, onSeek, onClose }: {
  recap: Recap | null; loading: boolean; lens: Lens; clubName: string; insights: Insight[]; onSeek: (t: number) => void; onClose: () => void
}) {
  const shown = recap ? LENS_LABEL[recap.lens] : LENS_LABEL[lens]
  const borrowed = recap && recap.lens !== lens
  return (
    <div role="dialog" aria-label="Match recap" className="fade-in pointer-events-auto absolute inset-x-3 bottom-3 z-10 flex max-h-[calc(100%-1.5rem)] flex-col gap-2 overflow-y-auto rounded-lg border bg-card/95 p-4 text-sm shadow-xl backdrop-blur md:left-auto md:w-[420px]">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-primary">Recap</p>
          <p className="text-xs text-muted-foreground">
            For the {shown} lens · {clubName}{borrowed ? ` (the ${LENS_LABEL[lens]} lens uses the analyst recap)` : ''} · not per player
          </p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close recap" className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"><X className="size-4" /></button>
      </div>
      {loading && <p className="text-muted-foreground">Loading the recap...</p>}
      {!loading && !recap && <p className="text-muted-foreground">No recap for this match, lens and club.</p>}
      {recap && (
        <>
          <p>{recap.text}</p>
          {recap.insight_ids.length > 0 && (
            <ul className="flex flex-col gap-1">
              {recap.insight_ids.map((id) => {
                const i = insights.find((x) => x.insight_id === id)
                return i ? (
                  <li key={id}>
                    <button type="button" onClick={() => onSeek(i.show_t_s)} className="flex w-full items-baseline gap-2 rounded-md border px-2 py-1.5 text-left hover:border-primary">
                      <span className="text-xs text-primary tabular-nums">{mmss(i.show_t_s)}</span>
                      <span>{resolve(i.text.fact, i.metrics)}</span>
                    </button>
                  </li>
                ) : null
              })}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
