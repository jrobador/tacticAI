import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowLeft, Check, CircleDot, Loader2 } from 'lucide-react'
import { watchJob } from '@/api/client'
import type { JobState, JobStatus } from '@/api/types'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { go } from '@/lib/nav'
import { cn } from '@/lib/utils'

const STEPS: { state: JobState; text: string }[] = [
  { state: 'searching', text: 'Searching seeds' },
  { state: 'rendering', text: 'Recording' },
  { state: 'analyzing', text: 'Analyzing' },
  { state: 'agents', text: 'Running agents' },
]
const order: JobState[] = ['queued', 'searching', 'rendering', 'analyzing', 'agents', 'done']

function headline(s: JobStatus | null): string {
  if (!s || s.state === 'queued') return 'Queued'
  if (s.state === 'searching') return s.progress ? `Seed ${s.progress.done} of ${s.progress.total}` : 'Searching seeds'
  if (s.state === 'rendering') return 'Recording'
  if (s.state === 'analyzing') return 'Analyzing'
  if (s.state === 'agents') return 'Running agents'
  return s.state
}

export function Generating({ jobId, hasRecipe }: { jobId: string; hasRecipe: boolean }) {
  const [status, setStatus] = useState<JobStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setStatus(null)
    setError(null)
    return watchJob(jobId, setStatus, (e) => setError(e.message))
  }, [jobId])

  useEffect(() => {
    if (status?.state === 'done' && status.match_id) {
      const t = setTimeout(() => go(`/matches/${status.match_id}`), 600)
      return () => clearTimeout(t)
    }
  }, [status])

  const state = status?.state ?? 'queued'
  const pct = state === 'searching' && status?.progress ? Math.round((status.progress.done / Math.max(1, status.progress.total)) * 100) : state === 'done' ? 100 : null
  const failed = state === 'failed'
  const noWinner = state === 'no_winner'

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 pt-6">
      <h1 className="text-xl font-semibold">{failed ? 'Generation failed' : noWinner ? 'No match found' : state === 'done' ? 'Done' : 'Generating your match'}</h1>

      {error && <Alert><AlertTriangle className="mt-0.5 size-4 shrink-0" /><p>{error}</p></Alert>}

      {failed && (
        <Alert>
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium">{status?.message ?? 'The job failed.'}</p>
            <p className="mt-1 text-muted-foreground">Job <code className="text-foreground">{jobId}</code></p>
          </div>
        </Alert>
      )}

      {noWinner && (
        <Alert>
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium">{status?.message}</p>
            <p className="mt-1 text-muted-foreground">Try more seeds or relax what you are looking for. Nothing is retried automatically.</p>
          </div>
        </Alert>
      )}

      {(failed || noWinner) ? (
        <div className="flex gap-2">
          {hasRecipe && <Button onClick={() => go('/recipe')}><ArrowLeft /> Back to the recipe</Button>}
          <Button variant="outline" onClick={() => go('/ask')}>Library</Button>
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col gap-5 p-5">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-lg font-medium" aria-live="polite">
                {state !== 'done' && <Loader2 className="size-5 animate-spin text-primary" />}
                {headline(status)}
              </span>
              {pct !== null && <span className="text-sm text-muted-foreground">{pct}%</span>}
            </div>
            <Progress value={pct} label={`Progress: ${headline(status)}`} />
            <ol className="grid grid-cols-4 gap-2 text-xs">
              {STEPS.filter((s) => s.state !== 'searching' || status?.kind !== 'library').map((s) => {
                const cur = order.indexOf(state)
                const mine = order.indexOf(s.state)
                const done = cur > mine
                const active = cur === mine
                return (
                  <li key={s.state} className={cn('flex items-center gap-1.5 rounded-md border p-2', active && 'border-primary text-foreground', !active && !done && 'text-muted-foreground')}>
                    {done ? <Check className="size-3.5 text-primary" /> : <CircleDot className={cn('size-3.5', active && 'text-primary')} />}
                    {s.text}
                  </li>
                )
              })}
            </ol>
            <p className="text-xs text-muted-foreground">Job <code>{jobId}</code>. You can leave this page; the job keeps running.</p>
          </CardContent>
        </Card>
      )}

      {state === 'done' && status?.message && <p className="text-sm text-muted-foreground">{status.message}</p>}
    </div>
  )
}
