// The five overlay designs over the video, one layer per audience.
import type { CSSProperties, ReactNode } from 'react'
import type { Insight, Overlay } from '@/api/types'
import { mmss } from '@/lib/format'
import { cn } from '@/lib/utils'
import { kindLabel, mainMetricKey, numOf, type Num, type Profile } from './model'
import { Term } from './Term'

export const reducedMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
const ease = (x: number) => 1 - Math.pow(1 - Math.max(0, Math.min(1, x)), 3)

type Corner = 'tl' | 'tr' | 'bl' | 'br'
// The bottom-right corner holds the live stats, so the director's bottom_right slot is drawn top-left, under the score bug.
const CORNER: Record<string, Corner> = { bottom_left: 'bl', top_right: 'tr', bottom_right: 'tl' }
// Where each corner sits over the video and where a card comes from (layout, not data).
const POS: Record<Corner, CSSProperties> = { tl: { top: 58, left: 18 }, tr: { top: 58, right: 18 }, bl: { bottom: 18, left: 18 }, br: { bottom: 18, right: 18 } }
const OFF: Record<Corner, [number, number]> = { tl: [-16, -8], tr: [16, -8], bl: [-16, 8], br: [16, 8] }

const OUT = 'cubic-bezier(.2,.7,.2,1)'
const MONO = 'font-mono'

/** What the layers draw for one overlay at video time t. */
export interface OvView {
  id: string
  insightId: string
  kicker: string
  at: string
  title: string
  text: string
  nums: Num[]
  one: Num | null
  corner: Corner
  live: boolean
  show_t_s: number
  tag: string
  focusOn: boolean
  dim: boolean
}

export function buildViews(list: Overlay[], insights: Map<string, Insight>, t: number, profile: Profile, playerName: string | null): OvView[] {
  const rm = reducedMotion()
  return list.map((o) => {
    const ins = insights.get(o.insight_id)
    const live = t >= o.show_t_s && t < o.show_t_s + o.duration_s
    const k = rm || !live ? 1 : ease((t - o.show_t_s) / 0.6)
    const mainKey = mainMetricKey(ins, o.metrics)
    const focusOn = !!profile.player && !!ins?.players.includes(profile.player)
    const tag = focusOn ? `Focus · ${playerName ?? ''}` : profile.club !== 'neutral' && ins ? (ins.team === profile.club ? 'Your side' : 'Opponent') : ''
    return {
      id: o.overlay_id, insightId: o.insight_id, kicker: ins ? kindLabel(ins.kind) : o.title, at: mmss(ins?.clock_s ?? o.show_t_s), title: o.title, text: o.text,
      nums: Object.entries(o.metrics).slice(0, 3).map(([key, m]) => numOf(key, m, k)),
      one: mainKey ? numOf(mainKey, o.metrics[mainKey], k) : null,
      corner: CORNER[o.slot ?? ''] ?? 'bl', live, show_t_s: o.show_t_s, tag, focusOn,
      dim: !!profile.player && !focusOn,
    }
  })
}

/** Latest `n` live views (the overlays that fit the slots at once). */
export const latest = (views: OvView[], n: number) => new Set(views.filter((v) => v.live).sort((a, b) => a.show_t_s - b.show_t_s).slice(-n).map((v) => v.id))

interface LayerProps {
  views: OvView[]
  /** The audience of the layer is the one selected: the layer fades in and takes clicks. */
  active: boolean
  openId: string | null
  onOpen: (insightId: string) => void
  /** Ids to draw (the live ones for the audience). */
  on: Set<string>
}

const layerStyle = (active: boolean): CSSProperties => ({ opacity: active ? 1 : 0, transition: 'opacity 300ms ease-out' })
const hidden = (corner: Corner): string => { const o = OFF[corner]; return `translate(${o[0]}px,${o[1]}px)` }
const Layer = ({ active, children }: { active: boolean; children: ReactNode }) => (
  <div className="pointer-events-none absolute inset-0" style={layerStyle(active)} aria-hidden={!active}>{children}</div>
)
const press = (open: () => void) => ({
  role: 'button' as const, tabIndex: 0, onClick: (e: React.MouseEvent) => { e.stopPropagation(); open() },
  onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open() } },
})
const border = (v: OvView, openId: string | null) => (openId === v.insightId ? 'var(--lime)' : v.focusOn ? 'rgba(240,240,240,.6)' : 'rgba(240,240,240,.14)')

function NumLabel({ n, className }: { n: Num; className?: string }) {
  return n.concept ? <Term k={n.concept} className={className}>{n.u}</Term> : <span className={className}>{n.u}</span>
}

export function AnalystLayer({ views, active, openId, onOpen, on }: LayerProps) {
  const rm = reducedMotion()
  return (
    <Layer active={active}>
      {views.map((v) => {
        const vis = on.has(v.id)
        return (
          <div
            key={v.id} {...press(() => onOpen(v.insightId))} aria-hidden={!vis} tabIndex={vis && active ? 0 : -1}
            className="absolute flex max-h-[calc(100%-76px)] w-[min(310px,42%)] cursor-pointer flex-col gap-[7px] overflow-hidden rounded-[10px] border bg-[rgba(12,23,42,.93)] px-3 py-2.5"
            style={{
              ...POS[v.corner], borderColor: border(v, openId), opacity: vis ? (v.dim ? 0.55 : 1) : 0, transform: vis || rm ? 'none' : hidden(v.corner),
              pointerEvents: vis && active ? 'auto' : 'none', transition: `opacity 420ms ${OUT}, transform 420ms ${OUT}, border-color 200ms ease-out`,
            }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className={cn(MONO, 'text-[10.5px] font-semibold uppercase tracking-[.04em] text-primary')}>{v.kicker} · {v.at}</span>
              {v.tag && <span className={cn(MONO, 'rounded bg-foreground px-[5px] py-0.5 text-[9.5px] font-semibold uppercase text-background')}>{v.tag}</span>}
            </div>
            <div className="text-[13px] font-medium leading-[1.42] [text-wrap:pretty]">{v.text}</div>
            <div className="grid grid-cols-3 gap-2 border-t border-foreground/10 pt-2">
              {v.nums.map((n) => (
                <div key={n.key} className="flex min-w-0 flex-col gap-0.5">
                  <span className="font-heading text-[17px] font-semibold leading-none">{n.txt}</span>
                  <NumLabel n={n} className="text-[10px] leading-tight text-muted-foreground" />
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </Layer>
  )
}

export function FanLayer({ views, active, openId, onOpen, on }: LayerProps) {
  const rm = reducedMotion()
  return (
    <Layer active={active}>
      {views.map((v) => {
        const vis = on.has(v.id)
        return (
          <div
            key={v.id} {...press(() => onOpen(v.insightId))} aria-hidden={!vis} tabIndex={vis && active ? 0 : -1}
            className="absolute flex max-h-[calc(100%-76px)] w-[min(360px,44%)] cursor-pointer flex-col overflow-hidden rounded-[14px] border bg-[rgba(12,23,42,.92)] backdrop-blur-[8px]"
            style={{
              ...POS[v.corner], borderColor: border(v, openId), opacity: vis ? 1 : 0, transform: vis || rm ? 'none' : hidden(v.corner), pointerEvents: vis && active ? 'auto' : 'none',
              padding: 'clamp(10px,1.6cqw,15px) clamp(12px,1.8cqw,17px)', gap: 'clamp(6px,1.1cqw,11px)', transition: `opacity 460ms ${OUT}, transform 460ms ${OUT}, border-color 200ms ease-out`,
            }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className={cn(MONO, 'text-[11px] font-semibold uppercase tracking-[.06em] text-primary')}>{v.kicker}</span>
              {v.tag && <span className={cn(MONO, 'rounded bg-foreground px-[5px] py-0.5 text-[9.5px] font-semibold uppercase text-background')}>{v.tag}</span>}
            </div>
            <div className="font-heading font-semibold leading-[1.22] tracking-[-.015em] [text-wrap:pretty]" style={{ fontSize: 'clamp(14px,2.2cqw,21px)' }}>{v.title}</div>
            <div className="flex items-end gap-5">
              {v.one && (
                <div className="flex flex-col gap-[3px]">
                  <span className="font-heading font-semibold leading-none text-primary" style={{ fontSize: 'clamp(18px,2.9cqw,28px)' }}>{v.one.txt}</span>
                  <NumLabel n={v.one} className="text-[11px] text-muted-foreground" />
                </div>
              )}
            </div>
          </div>
        )
      })}
    </Layer>
  )
}

export function BroadcastLayer({ views, active, openId, onOpen, on }: LayerProps) {
  const rm = reducedMotion()
  return (
    <Layer active={active}>
      {views.map((v) => {
        const vis = on.has(v.id)
        return (
          <div
            key={v.id} {...press(() => onOpen(v.insightId))} aria-hidden={!vis} tabIndex={vis && active ? 0 : -1}
            className="absolute inset-x-[18px] bottom-[18px] flex cursor-pointer items-stretch overflow-hidden rounded-lg border"
            style={{
              borderColor: border(v, openId), opacity: vis ? 1 : 0, transform: vis || rm ? 'none' : 'translateY(14px)', pointerEvents: vis && active ? 'auto' : 'none',
              transition: `opacity 380ms ${OUT}, transform 380ms ${OUT}`,
            }}
          >
            <span className={cn(MONO, 'flex items-center bg-primary px-3.5 text-[11px] font-bold tracking-[.08em] text-primary-foreground')}>LIVE</span>
            <div className="flex flex-1 items-center gap-4 bg-[rgba(12,23,42,.95)] px-3.5 py-[9px]">
              <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
                <span className={cn(MONO, 'text-[10.5px] uppercase tracking-[.06em] text-muted-foreground')}>{v.kicker} · {v.at}</span>
                <span className="font-heading font-bold uppercase tracking-[.01em]" style={{ fontSize: 'clamp(13px,2cqw,20px)' }}>{v.title}</span>
              </div>
              {v.one && (
                <div className="text-right">
                  <div className="font-heading text-[22px] font-semibold leading-none text-primary">{v.one.txt}</div>
                  <div className="mt-[3px] text-[10.5px] font-medium text-muted-foreground">{v.one.u}</div>
                </div>
              )}
            </div>
          </div>
        )
      })}
    </Layer>
  )
}

export function SpotlightLayer({ views, active, openId, onOpen, on }: LayerProps) {
  const rm = reducedMotion()
  return (
    <Layer active={active}>
      {views.map((v) => {
        const vis = on.has(v.id)
        if (!v.one) return null
        return (
          <div
            key={v.id} {...press(() => onOpen(v.insightId))} aria-hidden={!vis} tabIndex={vis && active ? 0 : -1}
            className="absolute right-[18px] top-[58px] flex cursor-pointer flex-col items-end gap-1 rounded-[14px] border bg-[rgba(12,23,42,.88)] px-[18px] py-3.5 text-right"
            style={{
              borderColor: border(v, openId), opacity: vis ? 1 : 0, transform: vis || rm ? 'none' : 'translateY(-10px) scale(.96)', pointerEvents: vis && active ? 'auto' : 'none',
              transition: `opacity 420ms ${OUT}, transform 420ms ${OUT}`,
            }}
          >
            <span className="font-heading font-semibold leading-none tracking-[-.04em] text-primary" style={{ fontSize: 'clamp(36px,6.4cqw,64px)' }}>{v.one.txt}</span>
            <NumLabel n={v.one} className="text-[13px] font-medium text-foreground" />
            <span className={cn(MONO, 'flex items-center gap-1.5 text-[10.5px] uppercase tracking-[.05em] text-muted-foreground')}>
              {v.kicker} · {v.at}
              <span className="grid size-3.5 place-items-center rounded-full bg-primary text-[9px] font-bold text-primary-foreground">✓</span>
            </span>
          </div>
        )
      })}
    </Layer>
  )
}

export function NewcomerLayer({ views, active, openId, onOpen, on }: LayerProps) {
  const rm = reducedMotion()
  return (
    <Layer active={active}>
      {views.map((v) => {
        const vis = on.has(v.id)
        return (
          <div
            key={v.id} {...press(() => onOpen(v.insightId))} aria-hidden={!vis} tabIndex={vis && active ? 0 : -1}
            className="absolute bottom-[18px] left-[18px] flex w-[min(420px,56%)] cursor-pointer flex-col gap-2 rounded-[14px] border bg-foreground px-4 py-3.5 text-background"
            style={{
              borderColor: openId === v.insightId ? 'var(--lime)' : 'transparent', opacity: vis ? 1 : 0, transform: vis || rm ? 'none' : 'translateY(14px)', pointerEvents: vis && active ? 'auto' : 'none',
              transition: `opacity 460ms ${OUT}, transform 460ms ${OUT}`,
            }}
          >
            <span className={cn(MONO, 'text-[11px] font-semibold uppercase tracking-[.06em] text-[#3a4456]')}>{v.kicker}</span>
            <span className="font-medium leading-[1.4] [text-wrap:pretty]" style={{ fontSize: 'clamp(13px,1.8cqw,17px)' }}>{v.text}</span>
            <div className="flex items-baseline gap-2 border-t border-background/15 pt-2">
              {v.one && (
                <>
                  <span className="font-heading text-xl font-semibold">{v.one.txt}</span>
                  <NumLabel n={v.one} className="text-xs text-[#3a4456]" />
                </>
              )}
            </div>
          </div>
        )
      })}
    </Layer>
  )
}

// ---- compact versions for the side-by-side panes ----
