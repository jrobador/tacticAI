import { useState } from 'react'
import { clipUrl } from '@/api/client'
import type { ClipManifest, Insight, MatchBundle, Overlay, Recap } from '@/api/types'
import { downloadCard } from '@/lib/card'
import { minute, mmss } from '@/lib/format'
import { cn } from '@/lib/utils'
import { momentText, type Texts } from './MomentsTab'
import { AUDIENCE_NAME, kindLabel, mainMetricKey, numOf, type Profile } from './model'

const title = 'font-sans text-sm font-semibold'

interface Props {
  matchId: string
  bundle: MatchBundle
  profile: Profile
  insights: Insight[]
  /** The broadcast /overlays: the queue (slot is null, nothing is drawn from it unless approved). */
  queue: Overlay[]
  time: number
  approved: Set<string>
  onApprove: (insightId: string) => void
  texts: Texts
  recap: Recap | null
  recapLoading: boolean
  manifest: ClipManifest | null
  short: Record<'home' | 'away', string>
  onSeek: (t: number) => void
}

export function OnAirTab(p: Props) {
  const byId = new Map(p.insights.map((i) => [i.insight_id, i]))
  const sorted = [...p.queue].sort((a, b) => a.show_t_s - b.show_t_s)
  return (
    <div className="flex flex-col gap-[22px]">
      <div className="flex flex-col">
        <span className={title}>On-air queue</span>
        <span className="pb-2 pt-0.5 text-xs leading-normal text-dim">
          Moments with importance 0.3 or more. Approve puts a graphic in the queue; it goes on air when the video reaches it. In Broadcast, the video shows only what is on air.
        </span>
        {sorted.length === 0 && <span className="text-[12.5px] text-dim">No graphics in the queue for this profile.</span>}
        {sorted.map((o) => {
          const ok = p.approved.has(o.insight_id)
          const st = p.time < o.show_t_s ? 'next' : p.time < o.show_t_s + o.duration_s ? 'on_air' : 'aired'
          const ins = byId.get(o.insight_id)
          const key = mainMetricKey(ins, o.metrics)
          const n = key ? numOf(key, o.metrics[key]) : null
          return (
            <div key={o.overlay_id} className={cn('-mx-1.5 grid grid-cols-[42px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-md border-t border-foreground/[.07] px-1.5 py-[9px] transition-colors duration-300', ok && st === 'on_air' && 'bg-primary/[.08]')}>
              <button type="button" title="Jump to this moment" onClick={() => p.onSeek(o.show_t_s + 0.01)} className="text-left font-mono text-[11.5px] font-medium text-muted-foreground hover:text-foreground">{mmss(ins?.clock_s ?? o.show_t_s)}</button>
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="truncate font-heading text-xs font-bold tracking-[.01em]">{o.title}</span>
                {n && <span className="text-[11px] text-dim">{n.txt} {n.u}</span>}
              </span>
              {!ok && <button type="button" onClick={() => p.onApprove(o.insight_id)} className="rounded-[7px] border border-foreground/25 px-[11px] py-1.5 text-xs font-semibold hover:border-primary hover:text-primary active:scale-[.96]">Approve</button>}
              {ok && st === 'on_air' && (
                <span className="flex items-center gap-1.5 rounded-full bg-primary px-[9px] py-[5px] text-[11.5px] font-bold text-primary-foreground">
                  <span className="tai-pulse size-[7px] rounded-full bg-background" />On air
                </span>
              )}
              {ok && st === 'next' && <span className="rounded border border-foreground px-2 py-1 text-[11.5px] font-semibold">Next</span>}
              {ok && st === 'aired' && <span className="text-[11.5px] font-semibold text-muted-foreground">✓ Aired</span>}
            </div>
          )
        })}
      </div>
      <Clips {...p} />
      <RecapBlock {...p} byId={byId} />
    </div>
  )
}

function Clips({ matchId, bundle, insights, manifest, texts }: Props) {
  const [sel, setSel] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const has = (id: string) => !!manifest?.clips.some((c) => c.insight_id === id)
  const cur = insights.find((i) => i.insight_id === sel) ?? insights.find((i) => has(i.insight_id)) ?? insights[0]
  if (!cur) return <div className="flex flex-col gap-2.5"><span className={title}>9:16 clips</span><span className="text-[12.5px] text-dim">No moments to cut for this match.</span></div>
  const key = mainMetricKey(cur, cur.metrics)
  const num = key ? numOf(key, cur.metrics[key]) : null
  const text = momentText(cur, texts)
  const main = cur.players[cur.players.length - 1]
  const player = main ? bundle.roster.players.find((r) => r.player_id === main) : undefined
  const rating = main ? (bundle.players.find((r) => r.player_id === main)?.rating.value ?? null) : null
  const png = () => {
    setError(null)
    downloadCard({
      filename: `tacticai-${matchId}-${cur.insight_id}`, kicker: `Minute ${minute(cur.clock_s)} · ${bundle.meta.teams[cur.team].name}`,
      title: kindLabel(cur.kind), text, player: player ? `#${player.number} ${player.name}` : null, rating,
    }).catch((e: Error) => setError(e.message))
  }
  return (
    <div className="flex flex-col gap-2.5">
      <span className={title}>9:16 clips</span>
      <div className="flex items-start gap-3">
        <div className="flex flex-none flex-col gap-1.5">
          <div className="flex aspect-[9/16] w-[132px] flex-col overflow-hidden rounded-xl border border-foreground/15 bg-background">
            <div className="grid flex-1 place-items-center bg-[repeating-linear-gradient(135deg,#111D32_0_8px,#0E192C_8px_16px)] font-mono text-[7.5px] font-semibold tracking-[.1em] text-[#5e6573]">CLIP</div>
            <div className="flex flex-[1.1] flex-col gap-1 px-[9px] py-2">
              <span className="font-mono text-[7.5px] font-semibold uppercase text-primary">{kindLabel(cur.kind)} · {mmss(cur.clock_s)}</span>
              <span className="line-clamp-5 font-heading text-[9.5px] font-semibold leading-[1.3] [text-wrap:pretty]">{text}</span>
              {num && <span className="mt-auto font-heading text-[15px] font-semibold leading-none text-primary">{num.txt} <span className="font-sans text-[7px] font-medium text-muted-foreground">{num.u}</span></span>}
              <img src="/tacticai-logo-dark-bg.png" alt="tacticAI" className="h-2 w-auto self-start" />
            </div>
          </div>
          <button type="button" onClick={png} className="rounded-[7px] border border-foreground/25 px-2 py-1 text-[11px] font-semibold hover:border-primary hover:text-primary">Card as PNG</button>
          {error && <span role="alert" className="text-[11px] text-muted-foreground">{error}</span>}
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          {insights.map((i) => (
            <div
              key={i.insight_id} role="button" tabIndex={0} onClick={() => setSel(i.insight_id)} onKeyDown={(e) => { if (e.key === 'Enter') setSel(i.insight_id) }}
              className={cn('-mx-1.5 grid cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-md px-1.5 py-1.5', i.insight_id === cur.insight_id && 'bg-[#16223a]')}
            >
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-xs font-semibold">{kindLabel(i.kind)}</span>
                <span className="font-mono text-[10.5px] font-medium text-dim">{mmss(i.clock_s)}</span>
              </span>
              {has(i.insight_id) ? (
                <a
                  href={clipUrl(matchId, i.insight_id)} download={`${i.insight_id}.mp4`} onClick={(e) => e.stopPropagation()}
                  className="min-w-[88px] rounded-[7px] border border-primary bg-primary px-2 py-[5px] text-center text-[11.5px] font-semibold text-primary-foreground"
                >
                  Download
                </a>
              ) : (
                <span className="min-w-[88px] rounded-[7px] border border-foreground/15 px-2 py-[5px] text-center text-[11.5px] font-semibold text-dim">No clip</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function RecapBlock({ profile, recap, recapLoading, short, byId, onSeek, texts }: Props & { byId: Map<string, Insight> }) {
  const tops = (recap?.insight_ids ?? []).map((id) => byId.get(id)).filter((i): i is Insight => !!i).sort((a, b) => a.show_t_s - b.show_t_s)
  const side = profile.club === 'neutral' ? 'Neutral' : short[profile.club]
  return (
    <div className="flex flex-col">
      <span className={title}>Recap</span>
      <span className="pb-1.5 pt-0.5 text-xs text-dim">
        Recap Agent · {AUDIENCE_NAME[profile.lens]} · {profile.lang === 'en' ? 'English' : 'Español'} · {side}
        {recap && recap.lens !== profile.lens ? ` (the ${AUDIENCE_NAME[recap.lens]} recap)` : ''}
      </span>
      {recapLoading && <p className="text-sm text-dim">Loading the recap...</p>}
      {!recapLoading && !recap && <p className="text-sm text-dim">No recap for this match, audience and side.</p>}
      {recap && (
        <>
          <p className="mb-2.5 text-sm leading-[1.55] [text-wrap:pretty]">{recap.text}</p>
          {tops.length > 0 && <span className="pb-1 pt-0.5 font-mono text-[10.5px] font-medium uppercase tracking-[.06em] text-dim">Top {tops.length} moment{tops.length === 1 ? '' : 's'}</span>}
          {tops.map((i) => {
            const key = mainMetricKey(i, i.metrics)
            const n = key ? numOf(key, i.metrics[key]) : null
            return (
              <button
                key={i.insight_id} type="button" onClick={() => onSeek(i.show_t_s + 0.01)}
                className="-mx-1.5 flex flex-col gap-1 rounded-md border-0 border-t border-foreground/10 px-1.5 py-2.5 text-left hover:bg-[#16223a]"
              >
                <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[.05em] text-primary">{kindLabel(i.kind)} · {mmss(i.clock_s)}</span>
                <span className="text-[13.5px] font-medium leading-[1.45] [text-wrap:pretty]">{momentText(i, texts)}</span>
                {n && <span className="text-[11px] font-medium text-muted-foreground">{n.txt} {n.u}</span>}
              </button>
            )
          })}
        </>
      )}
    </div>
  )
}
