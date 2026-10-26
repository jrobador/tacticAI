import { useMemo } from 'react'
import type { EnrichedEvent, MatchBundle, Side } from '@/api/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { TeamTag } from '@/components/TeamTag'
import { DASH, eventTitle, fix, minute, mmss, noteText, visibleNote, type Names } from '@/lib/format'

interface Props { bundle: MatchBundle; names: Names; time: number }

const pct = (v: number | null) => (v === null ? DASH : `${Math.round(v * 100)}%`)
const bar = (v: number | null) => `${Math.round((v ?? 0) * 100)}%`

/**
 * Synced to the video clock: events with t_s <= time, the last window whose end_t_s <= time,
 * notes whose until_t_s <= time. Everything is recomputed from the files, so seeking back drops later items.
 * Momentum is deliberately never read here.
 */
export function LivePanel({ bundle, names, time }: Props) {
  const { meta, events, timeline, notes } = bundle
  const recent = useMemo(() => events.filter((e) => e.t_s <= time).slice(-6).reverse(), [events, time])
  const win = useMemo(() => timeline.filter((w) => w.end_t_s <= time).at(-1) ?? null, [timeline, time])
  const known = useMemo(
    () => notes.filter((n) => visibleNote(n) && n.until_t_s <= time).sort((a, b) => b.until_t_s - a.until_t_s),
    [notes, time],
  )
  const sides: Side[] = ['home', 'away']

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="text-base">Live panel</CardTitle>
        <span className="text-xs tabular-nums text-muted-foreground">{mmss(time)}</span>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-5 overflow-y-auto">
        <section aria-label="Recent events">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Recent events</h4>
          {recent.length === 0 ? <p className="text-sm text-muted-foreground">Nothing has happened yet.</p> : (
            <ul className="flex flex-col gap-1.5">
              {recent.map((e: EnrichedEvent, i) => (
                <li key={`${e.t_s}-${e.type}-${i}`} className="flex gap-2 text-sm">
                  <span className="w-9 shrink-0 font-semibold tabular-nums">{minute(e.clock_s)}</span>
                  <span>{eventTitle(e, names)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Last closed window">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Last closed window</h4>
          {!win ? <p className="text-sm text-muted-foreground">The first window closes at {mmss(timeline[0]?.end_t_s ?? 0)}.</p> : (
            <div className="text-sm">
              <p className="mb-2 text-xs text-muted-foreground">{minute(win.start_clock_s)} to {minute(win.end_clock_s)}</p>
              <div className="mb-2 flex h-2 overflow-hidden rounded-full bg-muted" role="img" aria-label={`Possession: home ${pct(win.home.possession_share)}, away ${pct(win.away.possession_share)}`}>
                <div className="bg-primary" style={{ width: bar(win.home.possession_share) }} />
                <div className="bg-foreground/70" style={{ width: bar(win.away.possession_share) }} />
              </div>
              <table className="w-full">
                <thead>
                  <tr className="text-xs text-muted-foreground">
                    <th className="text-left font-normal" />
                    {sides.map((s) => <th key={s} className="text-right font-normal"><TeamTag side={s} short name={meta.teams[s].short} className="justify-end" /></th>)}
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  <tr><td className="text-muted-foreground">Possession</td>{sides.map((s) => <td key={s} className="text-right">{pct(win[s].possession_share)}</td>)}</tr>
                  <tr><td className="text-muted-foreground">Pressure</td>{sides.map((s) => <td key={s} className="text-right">{fix(win[s].pressure)}</td>)}</tr>
                  <tr><td className="text-muted-foreground">Engine xG</td>{sides.map((s) => <td key={s} className="text-right">{fix(win[s].xg)}</td>)}</tr>
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section aria-label="Tactical notes">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Confirmed tactical notes</h4>
          {known.length === 0 ? <p className="text-sm text-muted-foreground">No note confirmed yet.</p> : (
            <ul className="flex flex-col gap-2">
              {known.map((n, i) => (
                <li key={`${n.t_s}-${n.kind}-${i}`} className="rounded-md border p-2 text-sm">
                  <TeamTag side={n.team} short name={meta.teams[n.team].short} className="mb-1 text-xs text-muted-foreground" />
                  <p>{noteText(n, names, meta.teams[n.team].name)}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </CardContent>
    </Card>
  )
}
