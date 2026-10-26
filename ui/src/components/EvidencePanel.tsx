import { useEffect, type ReactNode } from 'react'
import { Link2, X } from 'lucide-react'
import type { Insight, Overlay } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { label, minute, mmss } from '@/lib/format'
import { CLAIM_LABELS, FACTOR_LABELS, fmtMetric, metricLabel, refLinks, resolve, SOURCE_BY_KIND, unitLabel } from '@/lib/overlays'

interface Props {
  overlay: Overlay
  insight: Insight | undefined // undefined while explain/insights.jsonl loads or when it has no such id
  eventTimes: number[]
  onSeek: (t: number) => void
  onClose: () => void
  actions?: ReactNode // 9:16 card and clip download
}

const pct = (v: number) => `${Math.round(v * 100)}%`

/** Evidence behind one overlay, straight from explain/insights.jsonl: metrics with unit and source, claims, importance and refs. */
export function EvidencePanel({ overlay, insight, eventTimes, onSeek, onClose, actions }: Props) {
  useEffect(() => {
    const on = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [onClose])

  return (
    <div
      role="dialog"
      aria-label={`Evidence for ${overlay.title}`}
      className="fade-in pointer-events-auto absolute top-3 left-3 z-10 flex max-h-[calc(100%-1.5rem)] w-[340px] max-w-[calc(100%-1.5rem)] flex-col gap-3 overflow-y-auto rounded-lg border bg-card/95 p-4 text-sm shadow-xl backdrop-blur"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-primary">Evidence</p>
          <h3 className="font-heading text-base font-semibold leading-tight">{overlay.title}</h3>
        </div>
        <button type="button" onClick={onClose} aria-label="Close evidence" className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
          <X className="size-4" />
        </button>
      </div>

      {actions}

      {!insight ? (
        <p className="text-muted-foreground">Loading the insight...</p>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            {label(insight.kind)} · {label(insight.subtype)} · minute {minute(insight.clock_s)} · video {mmss(insight.show_t_s)}
          </p>
          <p>{resolve(insight.text.fact, insight.metrics)}. <span className="text-muted-foreground">{resolve(insight.text.why, insight.metrics)}.</span></p>

          <section>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Numbers</h4>
            <ul className="divide-y divide-border rounded-md border">
              {Object.entries(insight.metrics).map(([k, m]) => (
                <li key={k} className="flex items-baseline justify-between gap-3 px-2 py-1.5">
                  <span>{metricLabel(k)}</span>
                  <span><b className="font-heading text-primary">{fmtMetric(m)}</b> <span className="text-xs text-muted-foreground">{unitLabel(m.unit)}</span></span>
                </li>
              ))}
            </ul>
            <p className="mt-1 text-xs text-muted-foreground">Source: {SOURCE_BY_KIND[insight.kind] ?? 'Interpret'}</p>
          </section>

          {insight.claims.length > 0 && (
            <section>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Claims (computed by code)</h4>
              <div className="flex flex-wrap gap-1">{insight.claims.map((c) => <Badge key={c} variant="default">{CLAIM_LABELS[c] ?? label(c)}</Badge>)}</div>
            </section>
          )}

          <section>
            <h4 className="mb-1 flex items-baseline justify-between text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <span>Importance</span><span className="font-heading text-sm text-foreground">{insight.importance.value.toFixed(2)}</span>
            </h4>
            <ul className="flex flex-col gap-1">
              {Object.entries(insight.importance.factors).map(([k, v]) => (
                <li key={k} className="grid grid-cols-[130px_1fr_40px] items-center gap-2 text-xs">
                  <span className="text-muted-foreground">{FACTOR_LABELS[k] ?? label(k)}</span>
                  <span className="h-1.5 rounded-full bg-muted"><span className="block h-full rounded-full bg-primary" style={{ width: v === null ? 0 : pct(v) }} /></span>
                  <span className="text-right">{v === null ? 'n/a' : v.toFixed(2)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-1 text-xs text-muted-foreground">Mean of the available factors, equal weights.</p>
          </section>

          <section>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Source</h4>
            <div className="flex flex-wrap gap-1.5">
              {refLinks(insight, eventTimes).map((r) => (
                <button key={r.label} type="button" onClick={() => onSeek(r.t)} className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs hover:border-primary hover:text-primary">
                  <Link2 className="size-3" /> {r.label} · {mmss(r.t)}
                </button>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  )
}
