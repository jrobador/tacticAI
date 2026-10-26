import type { MetricSeries, Side } from '@/api/types'
import { mmss } from '@/lib/format'

const COLOR: Record<Side, string> = { home: 'var(--lime)', away: 'var(--offwhite)' }
const UNIT: Record<string, string> = { '0-1': 'pressure, 0-1', 'engine xG': 'engine xG', '%': 'possession, %', goals_added: 'goals added (engine)' }
const REASON: Record<string, string> = {
  vaep_model_missing: 'This match has no goals-added model, so the cumulative strip is not available.',
  timeline_missing: 'This match has no timeline, so the strip is not available.',
}

const W = 1000
const H = 100

/** Path of a team: windows are horizontal bars with a gap at every null; steps are a staircase of the cumulative value. */
function pathOf(s: MetricSeries, side: Side, duration: number, y: (v: number) => number): string {
  const x = (t: number) => (Math.min(t, duration) / duration) * W
  if (s.mode === 'windows') {
    return s.points
      .filter((p) => p[side] !== null)
      .map((p) => `M${x(p.from_t_s ?? 0)} ${y(p[side] as number)}H${x(p.until_t_s ?? duration)}`)
      .join('')
  }
  let d = ''
  let open = false
  s.points.forEach((p, i) => {
    const v = p[side]
    const until = s.points[i + 1]?.t_s ?? duration
    if (v === null) { open = false; return }
    d += open ? `V${y(v)}H${x(until)}` : `M${x(p.t_s ?? 0)} ${y(v)}H${x(until)}`
    open = true
  })
  return d
}

/** The One Metric strip under the video: steps, gaps where the value is null (never 0), a playhead at the current time. */
export function MetricStrip({ series, duration, time, names, onSeek }: {
  series: MetricSeries; duration: number; time: number; names: Record<Side, string>; onSeek?: (t: number) => void
}) {
  const unit = UNIT[series.unit] ?? series.unit
  if (!series.available) {
    return (
      <div className="rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground" role="status">
        <b className="font-medium text-foreground">{unit}</b> — {REASON[series.reason ?? ''] ?? `Not available (${series.reason ?? 'unknown reason'}).`}
      </div>
    )
  }
  const vals = series.points.flatMap((p) => [p.home, p.away]).filter((v): v is number => v !== null)
  const lo = series.mode === 'steps' ? Math.min(0, ...vals) : 0
  const hi = series.unit === '0-1' ? 1 : series.unit === '%' ? 100 : Math.max(...vals, series.unit === 'engine xG' ? 0.5 : 0.1)
  const y = (v: number) => H - 6 - ((v - lo) / (hi - lo || 1)) * (H - 12)
  const fmt = (v: number) => (series.unit === '%' ? `${Math.round(v)}%` : v.toFixed(2))
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="font-semibold uppercase tracking-wide text-muted-foreground">One metric · {unit}</span>
        <span className="flex items-center gap-4">
          {(['home', 'away'] as const).map((side) => (
            <span key={side} className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-4" style={{ background: COLOR[side] }} />{names[side]}</span>
          ))}
        </span>
      </div>
      <div className="grid grid-cols-[auto_1fr] gap-x-2">
        <div className="flex flex-col justify-between text-[10px] text-muted-foreground"><span>{fmt(hi)}</span><span>{fmt(lo)}</span></div>
        <svg
          viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" className="h-24 w-full cursor-pointer rounded bg-muted"
          aria-label={`${unit} for each team over the match, playhead at ${mmss(time)}`}
          onClick={(e) => {
            const r = e.currentTarget.getBoundingClientRect()
            onSeek?.(((e.clientX - r.left) / r.width) * duration)
          }}
        >
          <line x1={0} x2={W} y1={y(lo)} y2={y(lo)} stroke="var(--offwhite)" strokeOpacity={0.2} vectorEffect="non-scaling-stroke" />
          {(['away', 'home'] as const).map((side) => (
            <path key={side} d={pathOf(series, side, duration, y)} fill="none" stroke={COLOR[side]} strokeWidth={series.mode === 'windows' ? 4 : 2.5} vectorEffect="non-scaling-stroke" />
          ))}
          <line x1={(time / duration) * W} x2={(time / duration) * W} y1={0} y2={H} stroke="var(--lime)" strokeWidth={2} vectorEffect="non-scaling-stroke" data-testid="playhead" />
        </svg>
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground">
        {series.mode === 'steps' ? 'Cumulative, in steps.' : 'One bar per window; a gap means the team had no value in that window.'} Click to jump.
      </p>
    </div>
  )
}
