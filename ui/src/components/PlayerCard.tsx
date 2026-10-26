import type { Heatmaps, Insight, PlayerCard as Card, RosterPlayer } from '@/api/types'
import { MiniPitch } from '@/components/MiniPitch'
import { CREST, label, mmss } from '@/lib/format'
import { resolve } from '@/lib/overlays'

const REASONS: Record<string, string> = {
  saves_not_validated: 'Goalkeeper rating is not validated yet.',
  vaep_model_missing: 'This match has no goals-added model.',
}

/** Heat map on the pitch: grid[i][j] with i along x (home attacks +x, to the right) and j along y. null grid: not enough data. */
export function Heatmap({ map, playerId }: { map: Heatmaps | null; playerId: string }) {
  const entry = map?.players[playerId]
  if (!map || !entry || !entry.grid) {
    return <p className="rounded-md bg-muted px-3 py-8 text-center text-sm text-muted-foreground">Not enough data for a heat map.</p>
  }
  const [x0, x1] = map.bounds.x
  const [y0, y1] = map.bounds.y
  const cw = (x1 - x0) / map.x_bins
  const ch = (y1 - y0) / map.y_bins
  const max = Math.max(...entry.grid.flat(), 1e-9)
  return (
    <div>
      <MiniPitch data={null} className="h-auto" owner={null}>
        {entry.grid.flatMap((col, i) => col.map((v, j) => (
          v > 0 ? <rect key={`${i}-${j}`} x={x0 + i * cw} y={y0 + j * ch} width={cw} height={ch} fill="var(--lime)" fillOpacity={0.1 + 0.8 * (v / max)}><title>{`${v.toFixed(2)} s`}</title></rect> : null
        )))}
      </MiniPitch>
      <p className="mt-1 flex justify-between text-[11px] text-muted-foreground"><span>Own goal</span><span>Seconds in open play: {entry.eligible_s.toFixed(1)} · home attacks →</span><span>Opp. goal</span></p>
    </div>
  )
}

/** Player Focus card: identity, goals-added rating with its breakdown, heat map and the player's moments (click jumps the video). */
export function PlayerCard({ card, player, crestName, heatmaps, insights, onSeek }: {
  card: Card; player: RosterPlayer | undefined; crestName: string; heatmaps: Heatmaps | null; insights: Insight[]; onSeek: (t: number) => void
}) {
  const r = card.rating
  const moments = card.insight_ids.map((id) => insights.find((i) => i.insight_id === id)).filter((i): i is Insight => !!i)
  return (
    <section aria-label="Player focus" className="rounded-lg border bg-card p-4">
      <header className="mb-3 flex items-center gap-3">
        {player && <img src={CREST[player.team]} alt={crestName} className="size-10 object-contain" />}
        <div>
          <h2 className="font-heading text-lg font-semibold leading-tight">{player ? `#${player.number} ${player.name}` : card.player_id}</h2>
          <p className="text-xs text-muted-foreground">{player ? `${player.role} · ${crestName}` : 'Player focus'}</p>
        </div>
        <div className="ml-auto text-right">
          <p className="font-heading text-3xl font-semibold text-primary">{r?.value == null ? '—' : `${r.value >= 0 ? '+' : ''}${r.value.toFixed(2)}`}</p>
          <p className="text-[11px] text-muted-foreground">goals added (engine)</p>
        </div>
      </header>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-4">
          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Rating breakdown</h3>
            {r && r.breakdown.length > 0 ? (
              <table className="w-full text-xs">
                <thead className="text-muted-foreground"><tr><th className="text-left font-normal">Action</th><th className="text-right font-normal">Count</th><th className="text-right font-normal">Off.</th><th className="text-right font-normal">Def.</th><th className="text-right font-normal">Points</th></tr></thead>
                <tbody>
                  {r.breakdown.map((b) => (
                    <tr key={b.item} className="border-t"><td className="py-1">{label(b.item)}</td><td className="text-right">{b.count}</td><td className="text-right">{b.offensive.toFixed(2)}</td><td className="text-right">{b.defensive.toFixed(2)}</td><td className="text-right font-medium">{b.points.toFixed(2)}</td></tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-sm text-muted-foreground">{REASONS[r?.reason ?? ''] ?? 'No rated actions in this match.'}</p>
            )}
          </div>
          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Moments</h3>
            {moments.length === 0 ? <p className="text-sm text-muted-foreground">No key moments for this player.</p> : (
              <ul className="flex flex-col gap-1">
                {moments.map((i) => (
                  <li key={i.insight_id}>
                    <button type="button" onClick={() => onSeek(i.show_t_s)} className="flex w-full items-baseline gap-2 rounded-md border px-2 py-1.5 text-left text-sm hover:border-primary">
                      <span className="text-xs text-primary tabular-nums">{mmss(i.show_t_s)}</span>
                      <span>{resolve(i.text.fact, i.metrics)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Heat map</h3>
          <Heatmap map={heatmaps} playerId={card.player_id} />
        </div>
      </div>
    </section>
  )
}
