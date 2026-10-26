import { ChevronRight } from 'lucide-react'
import type { Trail } from '@/api/types'
import { trailSteps } from '@/lib/overlays'

/** Agent trail of the overlay on screen, plus the always-visible Microsoft strip. */
export function TrailStrip({ trail, available }: { trail: Trail | null; available: boolean }) {
  const steps = trail ? trailSteps(trail) : null
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 rounded-lg border bg-card px-4 py-2 text-xs">
      <div className="flex min-h-5 flex-wrap items-center gap-1.5" aria-label="Agent trail" aria-live="polite">
        <span className="font-semibold uppercase tracking-wide text-muted-foreground">Agent trail</span>
        {steps ? (
          steps.map((s, i) => (
            <span key={s} className="flex items-center gap-1.5">
              {i > 0 && <ChevronRight className="size-3 text-muted-foreground" />}
              <span className={s.startsWith('Template') || s.startsWith('Rules') ? 'text-muted-foreground' : 'text-primary'}>{s}</span>
            </span>
          ))
        ) : (
          <span className="text-muted-foreground">{available ? 'appears with the next overlay' : 'no overlays for this match'}</span>
        )}
      </div>
      <p className="text-muted-foreground">Built on <b className="font-medium text-foreground">Microsoft Foundry</b> · <b className="font-medium text-foreground">Agent Framework</b> · <b className="font-medium text-foreground">Azure Container Apps</b></p>
    </div>
  )
}
