import { useEffect, useState } from 'react'
import { previewUrl } from '@/api/client'
import type { JobStatus } from '@/api/types'
import { mmss } from '@/lib/format'
import { STAGES, stageRows, type Row } from '@/lib/newMatch'
import { cn } from '@/lib/utils'

const ICON: Record<Row['state'], string> = { todo: '○', active: '●', done: '✓', failed: '✕' }
const timeText = (r: Row) => (r.secs === null ? '' : `${mmss(r.secs)}${r.total ? ' total' : ''}`)

/** Who works in each step and on what ("Who · what"), shown in turn under the active step. The status only says
 *  which step runs, so these lines name the step's real agents and models, without a made-up progress number. */
const ACTIVITY: Partial<Record<string, string[]>> = {
  analyzing: ['xG model · scoring every shot', 'xPass model · rating every pass', 'Goals-added model · valuing every action', 'Tracking · finding pressure spells and broken lines'],
  agents: ['Tactical Analyst · reading the possession phases', 'Tactical Analyst · calling the tactics tools', 'Tactical Analyst · writing the tactical notes'],
  explaining: ['Explainer · writing why each moment matters', 'Causal Judge · checking every claim against the data', 'Explainer · revising what the judge flagged'],
  personalizing: ['Lens Agent · rewording each moment per audience', 'Supporter Agent · writing for each club’s fans', 'Fan Judge · checking stance, language and facts',
    'Translator · English and Spanish', 'Recap Agent · picking the top moments', 'Studio Script Agent · drafting the presenter’s script'],
  directing: ['Director · deciding which graphic airs when', 'Director · planning the overlays per audience'],
  rendering_assets: ['Heatmaps · drawing every player', 'Broadcast · timing the on-air graphics', 'Reels · cutting 9:16 clips of goals and shots'],
}

function Activity({ stage, small }: { stage: string; small?: boolean }) {
  const lines = ACTIVITY[stage]
  const [i, setI] = useState(0)
  useEffect(() => {
    setI(0)
    if (!lines) return
    const t = setInterval(() => setI((n) => n + 1), 2400)
    return () => clearInterval(t)
  }, [lines])
  if (!lines) return null
  const [who, what] = lines[i % lines.length].split(' · ')
  return (
    <span className="flex flex-col gap-1">
      <span key={i} className={cn('fade-in truncate font-mono text-muted-foreground', small ? 'text-[10px]' : 'text-[11.5px]')}>
        <span className="text-primary">{who}</span>{what && ` · ${what}`}<span className="tai-dots" />
      </span>
      <span className="relative h-px w-full overflow-hidden bg-foreground/10"><span className="tai-sweep absolute inset-y-0 left-0 w-2/5 bg-primary/70" /></span>
    </span>
  )
}

/** Ticks while `on`, so elapsed times move. */
function useNow(on: boolean) {
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    if (!on) return
    const t = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(t)
  }, [on])
  return now
}

/** Latest video frame of the running job. The last good image stays until the next one has loaded. */
function usePreview(jobId: string, on: boolean) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    if (!on) return
    let n = 0
    let stop = false
    const tick = () => {
      if (stop) return
      const url = previewUrl(jobId, n++)
      const img = new Image()
      img.onload = () => { if (!stop) setSrc(url) }
      img.src = url
    }
    tick()
    const t = setInterval(tick, 200)
    return () => { stop = true; clearInterval(t) }
  }, [jobId, on])
  return src
}

export function GenCard({ jobId, title, status, error }: { jobId: string; title: string | null; status: JobStatus | null; error: string | null }) {
  const state = status?.state ?? 'queued'
  const running = state !== 'done' && state !== 'failed' && state !== 'no_winner'
  const now = useNow(running)
  const rows = stageRows(status, now)
  const live = state === 'rendering'
  const frame = usePreview(jobId, live)
  const failed = state === 'failed' || state === 'no_winner'
  const started = status?.stages?.queued ? Date.parse(status.stages.queued) : null
  const total = rows[8].total ? rows[8].secs : started !== null ? (now - started) / 1000 : null
  const elapsed = total === null ? '' : mmss(total)
  const name = title ?? 'your match'
  const heading = failed ? 'Stopped' : state === 'done' ? 'Done · opening the match' : `Making “${name}”`
  const showVideo = !failed && rows[1].state !== 'todo'

  if (!showVideo) {
    return (
      <div className="grid min-h-[52vh] place-items-center py-5">
        <div className="flex w-full max-w-[560px] flex-col gap-3.5 rounded-[18px] border border-foreground/10 bg-[#0f192b] px-6 py-[22px]">
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-heading text-[17px] font-semibold">{heading}</span>
            <span className="font-mono text-[12.5px] text-muted-foreground">{elapsed}</span>
          </div>
          {error && <p className="text-xs text-muted-foreground" role="status">Connection problem: {error}. Retrying.</p>}
          <div className="flex flex-col">
            {rows.map((r, i) => (
              <div key={r.label} className={cn('-mx-2 grid grid-cols-[20px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-lg px-2 py-2 transition-colors duration-300', r.state === 'active' && 'bg-primary/[.06]')}>
                <span className={cn('text-center text-xs font-bold', r.state === 'todo' ? 'text-[#4a5263]' : r.state === 'failed' ? 'text-foreground' : 'text-primary', r.state === 'active' && 'tai-pulse')}>{ICON[r.state]}</span>
                <span className="flex flex-col gap-px">
                  <span className={cn('text-[14.5px] font-medium', r.state === 'todo' && 'text-dim')}>{r.label}</span>
                  {r.seed && <span className="font-mono text-[11.5px] text-muted-foreground">{r.seed}</span>}
                  {r.state === 'active' && <Activity stage={STAGES[i][0]} />}
                </span>
                <span className="flex items-baseline gap-2">
                  <span className="text-[10.5px] font-medium text-dim">{r.word}</span>
                  <span className="min-w-[38px] text-right font-mono text-[12.5px] text-muted-foreground">{timeText(r)}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('relative aspect-video max-h-[calc(100vh-200px)] w-full overflow-hidden rounded-2xl border border-foreground/10 bg-[#0e1a2d] transition-opacity duration-500', state === 'done' && 'opacity-0')}>
      {frame ? (
        <img src={frame} alt="Live frame of the recording" className="absolute inset-0 size-full object-cover" />
      ) : (
        <div className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">{live ? 'Waiting for the first frame…' : 'Recording finished'}</div>
      )}
      <div className="absolute left-3.5 top-3.5 flex flex-col gap-0.5 rounded-[9px] border border-foreground/15 bg-background/90 px-[11px] py-[7px]">
        <span className="flex items-center gap-[7px] text-[12.5px] font-semibold">
          <span className={cn('size-2 rounded-full', live ? 'tai-pulse bg-primary' : 'bg-dim')} />
          {live ? 'Recording · live from the engine' : 'Recording finished'}
        </span>
        <span className="font-mono text-[11px] text-muted-foreground">{live ? 'Plays slower than real time' : `Making “${name}”`}</span>
      </div>
      <div className="absolute right-3.5 top-3.5 flex w-[236px] flex-col gap-0.5 rounded-xl border border-foreground/15 bg-background/90 px-3 py-2.5">
        <div className="flex items-baseline justify-between pb-1">
          <span className="text-xs font-semibold">Progress</span>
          <span className="font-mono text-[11px] text-muted-foreground">{elapsed}</span>
        </div>
        {rows.map((r, i) => (
          <div key={r.label} className="grid grid-cols-[14px_minmax(0,1fr)_auto] items-center gap-x-[7px] gap-y-1 py-0.5">
            <span className={cn('text-center text-[10px] font-bold', r.state === 'todo' ? 'text-[#4a5263]' : 'text-primary', r.state === 'active' && 'tai-pulse')}>{ICON[r.state]}</span>
            <span className={cn('truncate text-[11.5px] font-medium', r.state === 'todo' && 'text-dim')}>{r.label}</span>
            <span className="font-mono text-[10.5px] text-muted-foreground">{timeText(r)}</span>
            {r.state === 'active' && <span className="col-span-2 col-start-2 min-w-0"><Activity stage={STAGES[i][0]} small /></span>}
          </div>
        ))}
      </div>
    </div>
  )
}
