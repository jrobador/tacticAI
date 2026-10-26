import type { Insight, MatchBundle } from '@/api/types'
import { PHASE_LABEL, mmss } from '@/lib/format'
import { fmtMetric, resolve, unitLabel } from '@/lib/overlays'
import { cn } from '@/lib/utils'
import {
  AUDIENCE_NAME, AUDIENCE_RULE, FACTORS, KIND_CONCEPT, METRIC_MODEL, SPOTLIGHT_METRICS, kindLabel, priority, refText, segments, finalText, type Profile,
} from './model'
import { CheckedBadge, Term } from './Term'

export type Texts = Record<string, { title: string; text: string }> | null

/** The text of a moment for the audience, language and side: the variant when there is one, else the insight text. */
export function momentText(i: Insight, texts: Texts): string {
  const v = texts?.[i.insight_id]
  return v ? resolve(v.text, i.metrics) : finalText(i)
}

const phaseOf = (i: Insight, b: MatchBundle) => {
  const id = i.refs.candidate_id
  const c = id == null ? undefined : b.phases.find((p) => p.candidate_id === id)
  return c ? (PHASE_LABEL[c.phase] ?? c.phase) : null
}

interface Props {
  insights: Insight[] // momentum shifts already left out, in time order
  bundle: MatchBundle
  profile: Profile
  texts: Texts
  /** Insight ids the current audience shows (from /overlays); null while it loads. */
  shown: Set<string> | null
  /** Overlay window of every moment, to outline the one on screen. */
  windows: Map<string, [number, number]>
  time: number
  openId: string | null
  onOpen: (id: string | null) => void
  onSeek: (t: number) => void
  onOpenHow: () => void
}

export function MomentsTab(p: Props) {
  const open = p.openId ? p.insights.find((i) => i.insight_id === p.openId) : undefined
  return open ? <Detail {...p} insight={open} /> : <List {...p} />
}

function Factors({ i, bars }: { i: Insight; bars: 'mini' | 'full' }) {
  return (
    <>
      {FACTORS.map(([k, l]) => {
        const v = i.importance.factors[k]
        const w = `${Math.round((v ?? 0) * 100)}%`
        return bars === 'mini' ? (
          <span key={k} title={`${l} ${v == null ? 'n/a' : v.toFixed(2)}`} className="flex min-w-0 flex-col gap-[3px]">
            <span className="truncate text-[9.5px] font-medium text-dim">{l}</span>
            <span className="h-1 overflow-hidden rounded-sm bg-[#1f2b40]"><span className="block h-full rounded-sm bg-foreground" style={{ width: w }} /></span>
          </span>
        ) : (
          <div key={k} className="grid grid-cols-[96px_minmax(0,1fr)_36px] items-center gap-2.5">
            <span className="text-xs font-medium text-muted-foreground">{l}</span>
            <span className="h-[5px] overflow-hidden rounded-[3px] bg-[#1f2b40]"><span className="block h-full bg-foreground" style={{ width: w }} /></span>
            <span className="text-right font-heading text-[12.5px] font-semibold">{v == null ? 'n/a' : v.toFixed(2)}</span>
          </div>
        )
      })}
    </>
  )
}

function List({ insights, bundle, profile, texts, shown, windows, time, onOpen, onSeek }: Props) {
  const rule = AUDIENCE_RULE[profile.lens]
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs leading-normal text-dim">{insights.length} moments in time order, detected by code. The one on screen is outlined.</span>
      {insights.length === 0 && <span className="text-[12.5px] text-dim">No moments for this match: the Explain stage has not run on it.</span>}
      {insights.map((i) => {
        const w = windows.get(i.insight_id) ?? [i.show_t_s, i.show_t_s + 6]
        const live = time >= w[0] && time < w[1]
        const phase = phaseOf(i, bundle)
        const adj = priority(i, profile.club, profile.player)
        const below = shown !== null && !shown.has(i.insight_id)
        const wrongMetric = profile.lens === 'one_metric' && !SPOTLIGHT_METRICS.find((m) => m.id === profile.metric)?.kinds.includes(i.kind)
        const why = adj < rule.min - 1e-9 ? `importance ${adj.toFixed(2)} is under ${rule.min.toFixed(1)}.` : wrongMetric ? 'not a moment of the chosen metric.' : 'the Director left it out.'
        const concept = KIND_CONCEPT[i.kind]
        return (
          <div
            key={i.insight_id} role="button" tabIndex={0} onClick={() => onOpen(i.insight_id)}
            onKeyDown={(e) => { if (e.key === 'Enter') onOpen(i.insight_id) }}
            className={cn('flex cursor-pointer flex-col gap-2 rounded-xl border bg-[#0f192b] px-3 py-[11px] transition-colors duration-200 hover:bg-[#142036]', live ? 'border-primary/55' : 'border-foreground/10')}
          >
            <span className="flex items-center gap-2">
              {concept ? <Term k={concept} className="font-mono text-[10px] font-semibold uppercase tracking-[.06em] text-primary">{kindLabel(i.kind)}</Term>
                : <span className="font-mono text-[10px] font-semibold uppercase tracking-[.06em] text-primary">{kindLabel(i.kind)}</span>}
              {phase && <Term k="phase" className="rounded border border-foreground/35 px-1.5 py-0.5 font-mono text-[9.5px] font-semibold uppercase tracking-[.05em] text-foreground no-underline">Phase · {phase}</Term>}
              <button type="button" title="Jump to this moment" onClick={(e) => { e.stopPropagation(); onSeek(i.show_t_s + 0.01) }} className="font-mono text-[11px] font-medium text-muted-foreground hover:text-foreground">{mmss(i.clock_s)} ↗</button>
              <CheckedBadge className="ml-auto text-[11px]" />
            </span>
            <span className="text-[13.5px] font-medium leading-[1.45] [text-wrap:pretty]">{momentText(i, texts)}</span>
            {below && <span className="text-[11.5px] text-dim">Not shown for {AUDIENCE_NAME[profile.lens]}: {why}</span>}
            <span className="grid grid-cols-[auto_repeat(4,minmax(0,1fr))] items-end gap-2">
              <span className="flex flex-col gap-px pr-0.5">
                <span className="font-heading text-base font-semibold leading-none">{i.importance.value.toFixed(2)}</span>
                <Term k="importance" className="text-[9.5px] font-medium text-dim decoration-foreground/45 underline-offset-2">importance</Term>
              </span>
              <Factors i={i} bars="mini" />
            </span>
          </div>
        )
      })}
    </div>
  )
}

const head = 'font-mono text-[10.5px] font-medium uppercase tracking-[.06em] text-dim'

function Detail({ insight: i, bundle, profile, texts, onOpen, onOpenHow }: Props & { insight: Insight }) {
  const phase = phaseOf(i, bundle)
  const concept = KIND_CONCEPT[i.kind]
  const refs = refText(i.refs)
  const detected = `${kindLabel(i.kind)} · ${i.subtype.replace(/_/g, ' ')}${refs ? ` (${refs})` : ''}`
  return (
    <div className="flex flex-col gap-3.5">
      <button type="button" onClick={() => onOpen(null)} className="self-start rounded-[7px] border border-foreground/20 px-2.5 py-1.5 text-xs font-semibold hover:border-primary hover:text-primary">← All moments</button>
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex flex-wrap items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-[.06em] text-primary">
          {concept ? <Term k={concept} className="font-mono text-[11px] font-semibold uppercase tracking-[.06em] text-primary">{kindLabel(i.kind)}</Term> : kindLabel(i.kind)}
          <span>· {mmss(i.clock_s)}</span>
          {phase && <Term k="phase" className="rounded border border-foreground/35 px-1.5 py-0.5 font-mono text-[9.5px] font-semibold tracking-[.05em] text-foreground no-underline">Phase · {phase}</Term>}
        </span>
        <CheckedBadge className="ml-auto text-xs" size={16} />
      </div>
      <div className="flex flex-col gap-[3px]">
        <span className={head}>On screen · {AUDIENCE_NAME[profile.lens]}</span>
        <span className="font-heading text-base font-semibold leading-[1.35] [text-wrap:pretty]">{momentText(i, texts)}</span>
      </div>
      <div className="grid grid-cols-1 gap-2">
        <div className="flex flex-col gap-1.5 rounded-[10px] border border-dashed border-foreground/25 px-3 py-[11px]">
          <span className={head}>Explainer wrote</span>
          <span className="text-sm leading-[1.7] [text-wrap:pretty]">
            {segments(i).map((s, n) => s.ph
              ? <span key={n} className="rounded border border-primary/45 px-[3px] font-mono text-primary">{s.raw}</span>
              : <span key={n}>{s.raw}</span>)}
          </span>
        </div>
        <div className="flex flex-col gap-1.5 rounded-[10px] border border-foreground/20 bg-[#0f192b] px-3 py-[11px]">
          <span className={head}>Final text</span>
          <span className="text-sm leading-[1.7] [text-wrap:pretty]">
            {segments(i).map((s, n) => <span key={n} className={s.ph ? 'font-semibold text-primary' : undefined}>{s.out}</span>)}
          </span>
        </div>
      </div>
      <div className="flex flex-col">
        <span className={cn(head, 'pb-0.5')}>Every number and its source</span>
        <span className="pb-1.5 text-xs leading-normal text-dim">Each value is one of the moment's metrics, taken from an event or a tactical note of the analysis, and from the model when there is one.</span>
        {Object.entries(i.metrics).map(([k, m]) => (
          <div key={k} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-2.5 gap-y-0.5 border-t border-foreground/10 py-2">
            <span className="font-mono text-xs leading-normal [overflow-wrap:anywhere]">
              <span className="text-primary">{k}</span> <span className="text-dim">←</span> {refs || 'the analysis'}
              {METRIC_MODEL[k] && <span className="text-muted-foreground"> · {METRIC_MODEL[k]}</span>}
            </span>
            <span className="text-right font-heading text-sm font-semibold">{fmtMetric(m)} <span className="text-[11px] font-medium text-dim">{unitLabel(m.unit)}</span></span>
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-1.5">
        <span className={cn(head, 'flex justify-between')}>
          <Term k="importance" className="font-mono text-[10.5px] font-medium uppercase tracking-[.06em]">Importance</Term>
          <span className="text-foreground">{i.importance.value.toFixed(2)}</span>
        </span>
        <Factors i={i} bars="full" />
      </div>
      <span className="text-xs leading-normal text-dim">
        Detected by code from {detected} · Text: <Term k="mode" className="text-xs font-semibold text-foreground">{i.text.source === 'agent' ? 'Agent' : 'Template'}</Term>.{' '}
        <button type="button" onClick={onOpenHow} className="text-xs font-semibold text-primary hover:text-foreground">How this match was made →</button>
      </span>
    </div>
  )
}
