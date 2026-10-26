import { useEffect } from 'react'
import type { Insight, MatchBundle } from '@/api/types'
import { mmss } from '@/lib/format'
import { stageRows } from '@/lib/newMatch'
import { cn } from '@/lib/utils'
import type { RunInfo, Split } from './data'
import { kindLabel } from './model'
import { Term } from './Term'

type Mode = 'Agent' | 'Template' | 'Rules'
interface Trail { name: string; mode: Mode; calls: string; tools: string; received?: string; returned?: string; result?: string }

const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`
const split = (s: Split | null, a: string, b: string) => (s ? `${s.agent} ${a} · ${s.fallback} ${b}` : '')

/** One fact per stage, from the files of the match. A part whose file is missing is left out. */
function facts(b: MatchBundle, run: RunInfo, insights: Insight[]): string[] {
  const j = run.job
  const text = (xs: Insight[]) => `${xs.filter((i) => i.text.source === 'agent').length} Agent · ${xs.filter((i) => i.text.source !== 'agent').length} Template`
  const t = b.agents?.tactical
  return [
    j?.search ? `${j.search.seeds} seeds · ${j.search.met} met the condition · winner seed ${j.search.seed}` : b.meta.source.detail,
    `${b.quality.tracking_lines} tracking frames · ${(b.meta.video.frames / b.meta.video.fps).toFixed(1)} s of video`,
    [plural(b.events.length, 'event'), run.sequences != null ? plural(run.sequences, 'sequence') : '', plural(b.notes.length, 'tactical note'), plural(b.phases.length, 'phase candidate')].filter(Boolean).join(' · '),
    t ? `Tactical Analyst picked ${plural(t.phases.length, 'phase')} and ranked ${plural(t.key_notes.length, 'note')}${run.tools ? ` with ${plural(run.tools.length, 'tool call')}` : ''}` : 'No agent output for this match',
    `${plural(insights.length, 'moment')} · ${text(insights)}`,
    [run.variants && `${run.variants.files} variants (${split(run.variants, 'Agent', 'Template')})`, run.recaps && `${run.recaps.files} recaps (${split(run.recaps, 'Agent', 'Template')})`].filter(Boolean).join(' · '),
    run.plans ? `${run.plans.files} overlay plans · ${split(run.plans, 'Agent', 'Rules')}` : '',
    [run.heatmaps != null && `${run.heatmaps} heat maps`, run.clips != null && `${plural(run.clips, '9:16 clip')}`].filter(Boolean).join(' · '),
  ]
}

function trail(b: MatchBundle, run: RunInfo, insights: Insight[], library: boolean | null): Trail[] {
  const t = b.agents?.tactical
  const tools = run.tools ? [...new Set(run.tools)] : []
  const kinds = [...new Set(insights.filter((i) => i.kind !== 'momentum_shift').map((i) => i.kind))].map((k) => `${insights.filter((i) => i.kind === k).length} ${kindLabel(k)}`).join(', ')
  const nShift = insights.filter((i) => i.kind === 'momentum_shift').length
  const agentTexts = insights.filter((i) => i.text.source === 'agent').length
  const { home, away } = b.meta.formations
  const v = run.variants
  const rc = run.recaps
  const pl = run.plans
  return [
    library
      ? { name: 'Scenario Agent', mode: 'Template', calls: 'none · template', tools: 'none', result: `The template's tactical setup, ${home} vs ${away}` }
      : { name: 'Scenario Agent', mode: 'Agent', calls: '1 per request', tools: 'none', result: `Tactical setup: ${home} vs ${away}` },
    {
      name: 'Tactical Analyst', mode: t ? 'Agent' : 'Rules', calls: t ? `1 per match${run.tools ? ` · ${plural(run.tools.length, 'tool call')}` : ''}` : 'code, no model',
      received: `Code's analysis: ${plural(b.events.length, 'event')}${run.sequences != null ? `, ${plural(run.sequences, 'sequence')}` : ''}, ${plural(b.notes.length, 'tactical note')}, ${plural(b.phases.length, 'phase candidate')}`,
      tools: tools.length ? tools.join(' · ') : 'none',
      returned: t ? `Picked ${plural(t.phases.length, 'phase')} and ranked ${plural(t.key_notes.length, 'tactical note')}. It does not create moments.` : 'Nothing: no agent output for this match.',
    },
    { name: 'Moment detection', mode: 'Rules', calls: 'code, no model', tools: 'none', result: `${plural(insights.length - nShift, 'moment')}${kinds ? `: ${kinds}` : ''}.${nShift ? ' Momentum shift is switched off until it is checked against video.' : ''}` },
    { name: 'Explainer', mode: agentTexts ? 'Agent' : 'Template', calls: agentTexts ? '1 per match' : 'none · templates', tools: 'none', result: `${agentTexts} of ${insights.length} texts passed the check; ${insights.length - agentTexts} fell back to a template.` },
    { name: 'Lens', mode: v && v.agent ? 'Agent' : 'Template', calls: v ? `${v.files} per match: 3 audiences × 2 languages × 3 sides` : 'not recorded', tools: 'none', result: v ? `${v.agent} texts rewritten by the Agent, ${v.fallback} from templates. Placeholders untouched; code fills them.` : 'No variant files.' },
    { name: 'Recap Agent', mode: rc && rc.agent ? 'Agent' : 'Template', calls: rc ? `${rc.files} per match` : 'not recorded', tools: 'none', result: rc ? `${rc.agent} recaps by the Agent, ${rc.fallback} from templates.` : 'No recap files.' },
    { name: 'Director', mode: pl && pl.agent ? 'Agent' : 'Rules', calls: pl ? `${pl.files} per match: per audience and side` : 'not recorded', tools: 'none', result: pl ? `Overlay plans: ${pl.agent} by the Agent, ${pl.fallback} from rules. Code checks known moments, allowed slots, durations and overlaps.` : 'No plan files.' },
    { name: 'Match Q&A', mode: 'Agent', calls: 'on demand, from Ask', tools: 'search_moments · search_events · count_events', result: 'Moments and events with timestamps' },
  ]
}

const ICON: Record<Mode, string> = { Agent: '●', Template: '▤', Rules: '◆' }
const dim = 'text-dim'

export function HowDrawer({ title, bundle, run, insights, library, suspendEsc, onClose }: {
  title: string; bundle: MatchBundle; run: RunInfo | null; insights: Insight[]; library: boolean | null; suspendEsc: boolean; onClose: () => void
}) {
  useEffect(() => {
    const on = (e: KeyboardEvent) => { if (e.key === 'Escape' && !suspendEsc) onClose() }
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [onClose, suspendEsc])
  const job = run?.job ?? null
  const timed = !!job?.stages
  const rows = stageRows(timed ? job : null, Date.now()).slice(0, 8)
  const total = timed ? stageRows(job, Date.now())[8].secs : null
  const f = run ? facts(bundle, run, insights) : []
  const agents = run ? trail(bundle, run, insights, library) : []
  return (
    <>
      <div className="fade-in fixed inset-0 z-[70] bg-[rgba(5,10,20,.6)]" onClick={onClose} />
      <div role="dialog" aria-label="How this match was made" className="fade-in fixed inset-y-0 right-0 z-[80] flex w-[min(600px,100vw)] flex-col gap-[22px] overflow-auto border-l border-foreground/10 bg-[#0f192b] px-6 pb-8 pt-[22px]">
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <span className="font-mono text-[11px] font-semibold uppercase tracking-[.06em] text-primary">How this match was made</span>
            <span className="font-heading text-xl font-semibold">{title}</span>
            <span className="text-[12.5px] text-muted-foreground">{library === null ? '' : library ? 'Template: searched and recorded in advance' : 'Generated from your request'}</span>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-lg border border-foreground/20 px-[11px] py-[7px] text-[12.5px] font-semibold hover:border-primary hover:text-primary">Close</button>
        </div>

        <div className="flex flex-col gap-2.5">
          <div className="flex items-baseline justify-between"><span className="text-sm font-semibold">Progress trace</span><span className="font-mono text-xs text-muted-foreground">{total != null ? `${mmss(total)} total` : ''}</span></div>
          {timed && (
            <div className="flex h-2 gap-0.5 overflow-hidden rounded">
              {rows.map((r) => <span key={r.label} title={`${r.label} ${r.secs != null ? mmss(r.secs) : ''}`} className="bg-primary" style={{ flex: Math.max(r.secs ?? 0, 0.5) }} />)}
            </div>
          )}
          <div className="flex flex-col">
            {rows.map((r, i) => (
              <div key={r.label} className="grid grid-cols-[18px_minmax(0,1fr)_auto] items-center gap-2.5 border-t border-foreground/[.06] py-[7px]">
                <span className="text-[11px] font-bold text-primary">✓</span>
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-[13.5px] font-medium">{r.label}</span>
                  <span className="font-mono text-[11.5px] leading-[1.45] text-muted-foreground [overflow-wrap:anywhere]">{run ? f[i] : ''}</span>
                </span>
                <span className="font-mono text-xs text-muted-foreground">{r.secs != null ? mmss(r.secs) : ''}</span>
              </div>
            ))}
          </div>
          {!timed && run && <span className={cn('text-xs', dim)}>Stage times were not recorded for this match.</span>}
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-sm font-semibold">Agent trail</span>
          <span className="pb-1 text-xs leading-normal text-dim">What each step was called with, the tools it called and what it produced. When code covered a step, it says “Template” or “Rules”. This is the record of the run, not live telemetry; per-agent timings were not measured.</span>
          {!run && <span className={cn('text-xs', dim)}>Reading the match files…</span>}
          {agents.map((a) => (
            <div key={a.name} className="grid grid-cols-[22px_minmax(0,1fr)] gap-3 border-t border-foreground/[.07] py-3">
              <span className="text-center text-xs font-bold leading-[1.6]">{ICON[a.mode]}</span>
              <div className="flex min-w-0 flex-col gap-1.5">
                <span className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{a.name}</span>
                  <Term k="mode" className={cn('border px-[7px] py-0.5 font-mono text-[10px] font-bold uppercase tracking-[.05em] no-underline', a.mode === 'Agent' ? 'rounded-full border-primary bg-primary text-primary-foreground hover:text-primary-foreground' : 'rounded-[3px] border-foreground/50')}>{a.mode}</Term>
                </span>
                <div className="grid grid-cols-[72px_minmax(0,1fr)] gap-x-2.5 gap-y-1 text-[12.5px] leading-[1.45]">
                  <span className={dim}>Calls</span><span className="text-muted-foreground">{a.calls}</span>
                  {a.received && <><span className={dim}>Received</span><span className="text-muted-foreground">{a.received}</span></>}
                  <span className={dim}>Tools</span><span className="font-mono text-[11.5px] leading-normal [overflow-wrap:anywhere]">{a.tools}</span>
                  {a.returned && <><span className={dim}>Returned</span><span>{a.returned}</span></>}
                  {a.result && <><span className={dim}>Result</span><span>{a.result}</span></>}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
