// How tacticAI works: the engine, our models, the pipeline from a request to a match, Azure, and what changes in production.
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { getModels, listMatches, videoUrl } from '@/api/client'
import type { ModelCard } from '@/api/types'
import { useTracking } from '@/components/match/data'
import { modelText, type ModelId } from '@/components/match/modelInfo'
import { frameAt } from '@/components/match/StatsTab'
import { cn } from '@/lib/utils'

const FACTS: [string, string][] = [
  ['22 players + ball', 'Positions of everyone on the pitch, 10 frames per second, the format of a real tracking feed.'],
  ['Video and tracking', 'One run gives both.'],
  ['104 situations', 'Counters, build-ups and wing attacks already recorded, ready to watch.'],
  ['Plays on request', 'Formations, style, level and the result you want; the engine searches its runs until one produces it.'],
]

/** Public Premier League ranges next to our engine. */
const RANGES = [
  { name: 'Passes per minute of play', min: 0, max: 20, lo: 16, hi: 18, eng: 14.2, leagueL: '16–18', engL: '14.2', minL: '0', maxL: '20 per min', note: 'Our engine plays 1.8 to 3.8 fewer passes per minute than the league range.' },
  { name: 'Passes completed', min: 50, max: 100, lo: 81.5, hi: 83.7, eng: 67.6, leagueL: '81.5–83.7 %', engL: '67.6 %', minL: '50 %', maxL: '100 %', note: 'Our engine completes 13.9 to 16.1 percentage points fewer passes than the league range.' },
  { name: 'Distance run per player per minute', min: 0, max: 300, lo: 117, hi: 123, eng: 260, leagueL: 'about 120 m', engL: 'about 260 m', minL: '0 m', maxL: '300 m', note: 'Our players run about 140 m more per minute than the league figure, a little over twice as far.' },
]

const MODELS: { id: ModelId; name: string; line: string; baseL: string; noun: string }[] = [
  { id: 'xg_v1', name: 'xG', line: 'Ranks a goal above a miss.', baseL: 'distance and angle only', noun: 'shots' },
  { id: 'xpass_v1', name: 'xPass', line: 'Ranks a completed pass above a lost one.', baseL: 'pass length only', noun: 'passes' },
  { id: 'vaep_v1', name: 'VAEP (goals added)', line: 'Ranks an action that leads to a goal above one that does not.', baseL: 'where the action happened only', noun: 'actions' },
]

type Chip = ['a' | 'c', string]
interface Stage { id: string; name: string; line: string; chips: Chip[]; tech: string; text: string[]; tools?: string; techLong: string }
const FLOW: Stage[] = [
  { id: 'source', name: 'Source', line: 'Writes the setup and records the match.', chips: [['a', 'Scenario Agent'], ['c', 'engine search'], ['c', 'record 10 fps']], tech: 'Container Apps Job · Foundry',
    text: ['Scenario Agent receives the request and the current setup and returns a setup with a short summary; code validates it.', 'The engine searches for a run that produces the play and records video and tracking at 10 frames per second. While it records, a live preview shows the match as it is drawn.'],
    techLong: 'Azure Container Apps Job runs the engine.' },
  { id: 'interpret', name: 'Interpret', line: 'Finds the events and what matters.', chips: [['c', 'infer events'], ['c', 'score'], ['a', 'Tactical Analyst'], ['c', 'detect moments']], tech: 'Foundry · Agent Framework',
    text: ['Code infers events from positions and the models score them.', 'Tactical Analyst calls the analysis tools and returns the phases and notes that matter, ranked, with values as placeholders.', 'Code validates them and detects the moments.'],
    tools: 'xg_v1 · xpass_v1 · vaep_v1 · match_context · tactical_evidence · team_shape · pressing_profile · compare_metrics · possession_analysis · player_profile', techLong: 'Agents run on Microsoft Foundry.' },
  { id: 'explain', name: 'Explain', line: 'Writes the fact and the why.', chips: [['a', 'Explainer'], ['a', 'Causal Judge'], ['c', 'fill numbers']], tech: 'Foundry · Agent Framework',
    text: ['Explainer receives every moment with its metrics and returns the fact and the why, with placeholders for the numbers.', 'Causal Judge reads the Tactical Analyst and Explainer texts with their data and rejects any text that claims a cause the data does not show; it fails closed.', 'Code fills in the numbers and checks the text.'],
    techLong: 'Agents run on Microsoft Foundry.' },
  { id: 'personalize', name: 'Personalize', line: 'One text per audience, side and language.', chips: [['a', 'Lens'], ['a', 'Recap'], ['a', 'Translator'], ['a', 'Supporter Agent'], ['a', 'Fan Judge'], ['c', 'numbers survive']], tech: 'Foundry · Agent Framework',
    text: ['Lens writes a title and text for each of three audiences.', 'Recap writes a 3–5 sentence recap for each audience and side.', 'Translator turns the English texts and recaps into Spanish.',
      "For the fan, code detects what a supporter lives and decides what each club's supporter feels about every moment. Supporter Agent writes it in that supporter's voice, per language and club, with a line per moment for whoever follows one player.",
      "Fan Judge checks every fan text against one rubric: the language, the reader's side, facts only, a supporter's voice. A rejected text goes back once with the reasons; if it fails again, a line of data replaces it.",
      'Code checks that every number survives.'],
    techLong: 'Agents run on Microsoft Foundry.' },
  { id: 'render', name: 'Render', line: 'Plans the overlays.', chips: [['a', 'Director'], ['c', 'validate plan']], tech: 'Foundry · Agent Framework',
    text: ['Director returns the overlay plan for each audience and side: which moments, which slot, for how long.', 'Code validates every plan and falls back to rules.'], techLong: 'Agents run on Microsoft Foundry.' },
]
const ASK: Stage = { id: 'ask', name: 'Ask', line: 'Answers a question about the match.', chips: [['a', 'Match Q&A'], ['c', 'check answer']], tech: 'Foundry · Container Apps',
  text: ['Match Q&A answers a question by calling search tools over the match; code checks the answer against the tool results.'], tools: 'search_moments · search_events · count_events', techLong: 'Agents run on Microsoft Foundry.' }

const pct = (v: number, lo: number, hi: number) => `${((v - lo) / (hi - lo)) * 100}%`

function Section({ n, title, lead, children }: { n: string; title: string; lead?: string; children: ReactNode }) {
  return (
    <div className="rise flex flex-col gap-5 border-t border-foreground/10 pt-7">
      <div className="flex flex-col gap-2">
        <span className="font-mono text-[12px] font-semibold tracking-[.06em] text-primary">{n}</span>
        <h2 className="text-[28px] font-semibold leading-[1.15] tracking-[-0.02em]">{title}</h2>
        {lead && <p className="text-pretty text-[15px] leading-[1.6] text-muted-foreground">{lead}</p>}
      </div>
      {children}
    </div>
  )
}

const Panel = ({ className, children }: { className?: string; children: ReactNode }) =>
  <div className={cn('rounded-[14px] border border-foreground/10 bg-panel px-5 py-[18px]', className)}>{children}</div>
const Note = ({ children }: { children: ReactNode }) => <p className="text-pretty text-[13px] leading-[1.55] text-muted-foreground">{children}</p>
const Glyph = ({ open }: { open: boolean }) => <span className="font-mono text-[13px] font-medium text-dim">{open ? '−' : '+'}</span>

function AgentChip({ c }: { c: Chip }) {
  return c[0] === 'a'
    ? <span className="inline-flex items-center gap-[5px] rounded-full border border-primary px-[9px] py-[3px] text-[11.5px] font-medium"><span className="text-[10px] text-primary">✦</span>{c[1]}</span>
    : <span className="inline-flex items-center gap-[5px] rounded-[3px] border border-foreground/20 bg-foreground/5 px-[7px] py-[3px] font-mono text-[11px] font-medium text-foreground/80"><span className="text-dim">{'{ }'}</span>{c[1]}</span>
}

const Check = () => <span className="grid h-[18px] w-[14px] place-items-center rounded-[2px] border-[1.5px] border-foreground bg-panel text-[9px] font-bold">✓</span>

/** The video of a real engine run next to its tracking, frame by frame. */
function EngineDemo({ matchId }: { matchId: string }) {
  const tracking = useTracking(matchId)
  const ref = useRef<HTMLVideoElement>(null)
  const [t, setT] = useState(0)
  useEffect(() => {
    const id = setInterval(() => ref.current && setT(ref.current.currentTime), 100)
    return () => clearInterval(id)
  }, [])
  const f = frameAt(tracking, t)
  const src = videoUrl(matchId)
  // Same projection as the Stats radar: y grows downwards, as in the video.
  const at = (x: number, y: number) => ({ left: pct(x, -52.5, 52.5), top: pct(y, -34, 34) })
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-3">
      <div className="relative aspect-[105/68] overflow-hidden rounded-[10px] border border-foreground/15 bg-[#070E1A]">
        {src && <video ref={ref} src={src} muted loop autoPlay playsInline className="absolute inset-0 size-full object-contain" />}
        <span className="absolute left-2.5 top-2.5 rounded-[5px] bg-[rgba(12,23,42,.85)] px-[7px] py-1 font-mono text-[10px] font-semibold uppercase tracking-[.06em]">Video</span>
      </div>
      <div className="relative aspect-[105/68] overflow-hidden rounded-[10px] border-[1.5px] border-foreground/30 bg-[#0F1B2F]">
        <span className="absolute inset-y-0 left-1/2 w-[1.5px] bg-foreground/30" />
        <span className="absolute left-1/2 top-1/2 aspect-square w-[17.4%] -translate-x-1/2 -translate-y-1/2 rounded-full border-[1.5px] border-foreground/30" />
        <span className="absolute left-0 top-[20.4%] h-[59.2%] w-[15.7%] border-[1.5px] border-l-0 border-foreground/30" />
        <span className="absolute right-0 top-[20.4%] h-[59.2%] w-[15.7%] border-[1.5px] border-r-0 border-foreground/30" />
        {f?.players.filter((p) => p.on_pitch !== false).map((p) => (
          <span key={p.player_id} style={at(p.x, p.y)}
            className={cn('absolute -ml-[6px] -mt-[6px] size-3 rounded-full border-[1.5px] border-foreground transition-[left,top] duration-100 ease-linear', p.player_id.startsWith('home') ? 'bg-foreground' : 'bg-[#0C172A]')} />
        ))}
        {f && <span style={at(f.ball.x, f.ball.y)} className="absolute -ml-1 -mt-1 size-2 rounded-full bg-primary shadow-[0_0_0_3px_rgba(198,244,50,.25)] transition-[left,top] duration-100 ease-linear" />}
        <span className="absolute left-2.5 top-2.5 rounded-[5px] bg-[rgba(12,23,42,.85)] px-[7px] py-1 font-mono text-[10px] font-semibold uppercase tracking-[.06em]">Tracking · frame {f?.frame_index ?? 0}</span>
      </div>
    </div>
  )
}

function StageCard({ s, open, onClick }: { s: Stage; open: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-expanded={open}
      className={cn('flex min-w-[124px] flex-1 basis-0 flex-col gap-2 rounded-xl border p-3 text-left transition-colors duration-150 hover:border-primary/60', open ? 'border-primary/70 bg-[#15233A]' : 'border-foreground/15 bg-[#0F192B]')}>
      <span className="font-heading text-[15px] font-semibold">{s.name}</span>
      <span className="text-pretty text-[12px] leading-[1.4] text-muted-foreground">{s.line}</span>
      <span className="flex flex-wrap gap-[5px]">{s.chips.map((c) => <AgentChip key={c[1]} c={c} />)}</span>
      <span className="mt-auto border-t border-foreground/10 pt-2 font-mono text-[10.5px] leading-[1.4] text-dim">{s.tech}</span>
    </button>
  )
}

const Arrow = ({ check }: { check?: boolean }) => (
  <span className="relative flex flex-[0_0_52px] items-center justify-center">
    <span className="absolute left-1 right-1.5 top-1/2 h-[1.5px] bg-foreground/35" />
    <span className="absolute right-0.5 top-1/2 -mt-[4.5px] border-y-[5px] border-l-[6px] border-y-transparent border-l-foreground/50" />
    {check && <><span className="relative"><Check /></span><span className="absolute inset-x-0 top-[calc(50%+14px)] text-center font-mono text-[10px] font-medium leading-[1.15] text-foreground/80">code<br />checks</span></>}
  </span>
)

const You = ({ what }: { what: string }) => (
  <span className="flex flex-[0_0_76px] flex-col items-center justify-center gap-1.5">
    <span className="font-mono text-[10px] font-medium uppercase tracking-[.06em] text-dim">You</span>
    <span className="rounded-full bg-foreground px-[13px] py-[9px] font-heading text-[13px] font-semibold text-background">{what}</span>
  </span>
)

const AZ_BOX = 'absolute box-border flex flex-col justify-center gap-[3px] rounded-[10px] border bg-[#0F192B] px-3 py-2.5'

export function Architecture() {
  const [cards, setCards] = useState<ModelCard[]>([])
  const [demo, setDemo] = useState<string | null>(null)
  const [fact, setFact] = useState<number | null>(null)
  const [range, setRange] = useState<number | null>(null)
  const [model, setModel] = useState<ModelId | null>(null)
  const [stage, setStage] = useState<string | null>(null)
  useEffect(() => { getModels().then((r) => setCards(r.models)).catch(() => {}) }, [])
  useEffect(() => {
    listMatches().then((ms) => setDemo((ms.find((m) => m.featured) ?? ms[0])?.match_id ?? null)).catch(() => {})
  }, [])
  const toggle = <T,>(set: (f: (v: T | null) => T | null) => void, v: T) => set((cur) => (cur === v ? null : v))
  const det = [...FLOW, ASK].find((s) => s.id === stage)

  return (
    <section className="mx-auto flex w-full max-w-[1180px] flex-col gap-[52px] px-7 pb-20 pt-8 tabular-nums">
      <div className="rise flex flex-col gap-2.5">
        <span className="font-mono text-[11px] font-semibold uppercase tracking-[.08em] text-primary">Architecture</span>
        <h1 className="text-[36px] font-semibold leading-[1.08] tracking-[-0.025em]">How tacticAI works</h1>
      </div>

      <Section n="01" title="The engine" lead="Every match is played by our adaptation of an open-source 3D football engine. The 22 players decide, the ball follows physics, and one run gives both a video and the tracking a real feed would give.">
        {demo && <EngineDemo matchId={demo} />}
        <div className="flex flex-wrap items-baseline justify-between gap-x-5 gap-y-2">
          <Note>Video and tracking come from the same simulation, so every number can be checked against the picture. 10 frames per second.</Note>
          <span className="font-mono text-[11px] font-medium text-dim">filled: home · outline: away · lime: ball</span>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] border-y border-foreground/10">
          {FACTS.map(([k, v], i) => (
            <button key={k} type="button" onClick={() => toggle(setFact, i)} aria-expanded={fact === i} className="flex flex-col gap-1.5 py-3.5 pr-4 text-left hover:text-primary">
              <span className="flex items-baseline justify-between gap-2.5"><span className="font-heading text-[14.5px] font-semibold">{k}</span><Glyph open={fact === i} /></span>
              {fact === i && <span className="text-pretty text-[12.5px] leading-normal text-muted-foreground">{v}</span>}
            </button>
          ))}
        </div>
        <Panel className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-5 gap-y-2 pb-1.5">
            <span className="font-heading text-base font-semibold">How far from the real game</span>
            <span className="flex items-center gap-4 text-[11.5px] font-medium text-muted-foreground">
              <span className="flex items-center gap-1.5"><span className="h-2.5 w-[22px] rounded-[2px] border border-foreground/55 bg-foreground/20" />Premier League, public range</span>
              <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-primary" />Our engine</span>
            </span>
          </div>
          {RANGES.map((r, i) => (
            <button key={r.name} type="button" onClick={() => toggle(setRange, i)} aria-expanded={range === i}
              className="grid grid-cols-[minmax(150px,230px)_minmax(0,1fr)_16px] items-center gap-x-[22px] gap-y-2 border-t border-foreground/[.08] pb-[18px] pt-3.5 text-left">
              <span className="flex flex-col gap-[3px]"><span className="text-[13.5px] font-semibold leading-[1.35]">{r.name}</span>
                <span className="font-mono text-[11.5px] font-medium text-muted-foreground">League {r.leagueL} · <span className="text-primary">Engine {r.engL}</span></span></span>
              <span className="relative h-[30px]">
                <span className="absolute inset-x-0 top-3.5 h-0.5 bg-foreground/10" />
                <span style={{ left: pct(r.lo, r.min, r.max), width: pct(r.hi - r.lo + r.min, r.min, r.max) }} className="absolute top-1.5 box-border h-[18px] min-w-2 rounded-[3px] border border-foreground/55 bg-foreground/20" />
                <span style={{ left: pct(r.eng, r.min, r.max) }} className="absolute top-2 -ml-[7px] size-3.5 rounded-full bg-primary shadow-[0_0_0_3px_var(--color-panel)]" />
                <span className="absolute left-0 top-[30px] font-mono text-[10.5px] font-medium text-dim">{r.minL}</span>
                <span className="absolute right-0 top-[30px] font-mono text-[10.5px] font-medium text-dim">{r.maxL}</span>
              </span>
              <Glyph open={range === i} />
              {range === i && <span className="col-span-full pt-1.5 text-[12.5px] leading-normal text-muted-foreground">{r.note}</span>}
            </button>
          ))}
        </Panel>
        <Note>Competition rules allow only synthetic data, so the engine is our data source. We measure it against public league averages to know how far it is from the real game.</Note>
      </Section>

      <Section n="02" title="Our models" lead="Trained on our own engine. Each one is compared with a simple model that only looks at the obvious.">
        <Panel className="flex flex-col">
          <div className="grid grid-cols-[minmax(150px,230px)_minmax(0,1fr)_16px] gap-x-[22px] pb-2.5 pt-4">
            <span className="flex flex-wrap items-center gap-3.5 text-[11.5px] font-medium text-muted-foreground">
              <span className="flex items-center gap-1.5"><span className="box-border size-2.5 rounded-full border-2 border-foreground" />Simple model</span>
              <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-primary" />Our model</span>
            </span>
            <span className="relative h-4 font-mono text-[10.5px] font-medium text-dim">
              <span className="absolute left-0">50 %</span><span className="absolute left-[40%] -translate-x-1/2">70 %</span><span className="absolute left-[80%] -translate-x-1/2">90 %</span>
              <span className="absolute -top-[15px] left-0 text-muted-foreground">coin flip</span>
            </span>
            <span />
          </div>
          {MODELS.map((m) => {
            const c = cards.find((x) => x.id === m.id)
            if (!c?.test || !c.baseline) return null
            const ours = Math.round(c.test.auc * 100)
            const base = Math.round(c.baseline.auc * 100)
            const open = model === m.id
            const card = modelText(c, m.id)
            return (
              <button key={m.id} type="button" onClick={() => toggle(setModel, m.id)} aria-expanded={open}
                className="grid grid-cols-[minmax(150px,230px)_minmax(0,1fr)_16px] items-stretch gap-x-[22px] border-t border-foreground/[.08] text-left">
                <span className="flex flex-col gap-[3px] py-3.5"><span className="font-heading text-[14.5px] font-semibold">{m.name}</span>
                  <span className="text-[12.5px] leading-[1.4] text-muted-foreground">{m.line}</span>
                  <span className="font-mono text-[11px] font-medium text-dim">Trained on {c.n_train?.toLocaleString('en-US')} {m.noun}</span></span>
                <span className="relative min-h-[78px]">
                  <span className="absolute inset-y-0 left-0 border-l-[1.5px] border-dashed border-foreground/35" />
                  {[40, 80, 100].map((x) => <span key={x} style={{ left: `${x}%` }} className="absolute inset-y-0 border-l border-foreground/[.06]" />)}
                  <span style={{ left: pct(base, 50, 100), width: `${(ours - base) * 2}%` }} className="absolute top-[38px] h-0.5 bg-primary/55" />
                  <span style={{ left: pct(base, 50, 100) }} className="absolute top-8 -ml-[7px] box-border size-3.5 rounded-full border-2 border-foreground bg-panel" />
                  <span style={{ left: pct(ours, 50, 100) }} className="absolute top-[31px] -ml-2 size-4 rounded-full bg-primary" />
                  <span style={{ left: pct(base, 50, 100) }} className="absolute top-3 -translate-x-1/2 font-mono text-[12px] font-semibold text-foreground/80">{base} %</span>
                  <span style={{ left: pct(ours, 50, 100) }} className="absolute top-3 -translate-x-1/2 font-mono text-[12px] font-bold text-primary">{ours} %</span>
                  <span style={{ left: pct(base, 50, 100) }} className="absolute top-[52px] -ml-[7px] whitespace-nowrap text-[11px] text-dim">{m.baseL}</span>
                </span>
                <span className="pt-3.5"><Glyph open={open} /></span>
                {open && (
                  <span className="col-span-full mb-3.5 flex flex-col gap-[5px] rounded-[10px] border border-foreground/15 bg-[#0F192B] px-3.5 py-3">
                    <span className="flex justify-between gap-2.5"><span className="text-[13px] font-semibold">Model card · {m.name}</span><span className="font-mono text-[11px] font-medium text-muted-foreground">{m.id}</span></span>
                    <span className="text-[12.5px] leading-normal text-foreground/80">{card.what}</span>
                    <span className="text-[12.5px] leading-normal text-muted-foreground">{card.trained} {card.score}</span>
                    <span className="text-[11.5px] leading-normal text-dim">Measured on engine matches the model never saw. Not calibrated to real football.</span>
                  </span>
                )}
              </button>
            )
          })}
        </Panel>
        <Note>The percentage is how often the model ranks a positive case above a negative one (AUC), measured on matches it never saw. Trained on our engine, so these numbers are not calibrated to real football.</Note>
      </Section>

      <Section n="03" title="From a request to a match you can watch" lead="You do two things: create a match and watch it. Everything in between runs on its own. Agents run on Microsoft Foundry, and code checks everything they write.">
        <Panel className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-x-[22px] gap-y-2.5 text-[12px] text-muted-foreground">
            <span className="flex items-center gap-2"><AgentChip c={['a', 'Agent']} />writes</span>
            <span className="flex items-center gap-2"><AgentChip c={['c', 'Code']} />runs and checks</span>
            <span className="flex items-center gap-2"><Check /><span><span className="font-semibold text-foreground">Code checks</span> · anything rejected falls back to a template or rules</span></span>
          </div>
          <div className="overflow-x-auto pb-1">
            <div className="flex min-w-[1040px] items-stretch">
              <You what="Create" />
              <Arrow />
              {FLOW.map((s) => (
                <span key={s.id} className="contents">
                  <StageCard s={s} open={stage === s.id} onClick={() => toggle(setStage, s.id)} />
                  <Arrow check />
                </span>
              ))}
              <You what="Watch" />
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-x-3.5 gap-y-2.5">
            <span className="font-mono text-[10.5px] font-medium uppercase tracking-[.06em] text-dim">↳ Branch off Watch</span>
            <div className="flex w-[min(300px,100%)]"><StageCard s={ASK} open={stage === ASK.id} onClick={() => toggle(setStage, ASK.id)} /></div>
          </div>
          {det ? (
            <div className="grid grid-cols-[minmax(120px,180px)_minmax(0,1fr)] gap-x-[22px] gap-y-2 border-t border-foreground/10 pt-3.5">
              <span className="font-heading text-base font-semibold">{det.name}</span>
              <div className="flex flex-col gap-1.5">
                {det.text.map((x) => <span key={x} className="text-pretty text-[13.5px] leading-[1.55] text-foreground/80">{x}</span>)}
                {det.tools && <span className="break-words font-mono text-[11.5px] leading-[1.65] text-muted-foreground">{det.tools}</span>}
                <span className="text-[12px] font-medium text-dim">{det.techLong}</span>
              </div>
            </div>
          ) : <span className="text-[12px] text-dim">Select a stage to see what each agent receives and returns.</span>}
        </Panel>
      </Section>

      <Section n="04" title="Azure">
        <Panel className="overflow-x-auto">
          <div className="relative aspect-[1000/520] min-w-[760px]">
            <svg viewBox="0 0 1000 520" className="absolute inset-0 size-full" aria-hidden="true">
              <defs><marker id="arA" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="rgba(240,240,240,.6)" /></marker></defs>
              <g fill="none" stroke="rgba(240,240,240,.45)" strokeWidth="1.5">
                <path d="M230 220 H270 V75 H328" markerEnd="url(#arA)" />
                <path d="M270 220 V365 H328" markerEnd="url(#arA)" />
                <path d="M330 104 H300 V340 H328" markerEnd="url(#arA)" stroke="#C6F432" />
                <path d="M480 122 V173" markerStart="url(#arA)" markerEnd="url(#arA)" />
                <path d="M480 267 V318" markerStart="url(#arA)" markerEnd="url(#arA)" />
                <path d="M632 75 H875 V173" markerEnd="url(#arA)" />
                <path d="M632 365 H875 V267" markerEnd="url(#arA)" />
                <path d="M20 432 H980" strokeDasharray="4 5" stroke="rgba(240,240,240,.2)" />
              </g>
              <g fontFamily="Geist Mono, monospace" fontSize="11" fill="#A3A8B0">
                <text x="236" y="210">images</text>
                <text x="292" y="300" transform="rotate(-90 292 300)" fill="#C6F432">start Job</text>
                <text x="490" y="152">read / write</text>
                <text x="490" y="297">read / write</text>
                <text x="660" y="66">agent models</text>
                <text x="660" y="356">agent models</text>
                <text x="20" y="446" fill="#7D838D">ACROSS ALL RESOURCES</text>
              </g>
            </svg>
            {([
              ['left-[2%] top-[33.65%] w-[21%] h-[17.31%]', 'Azure Container Registry', 'The images', false],
              ['left-[33%] top-[5.77%] w-[30%] h-[17.31%]', 'Azure Container Apps', 'The always-on API with the built UI', false],
              ['left-[33%] top-[33.65%] w-[30%] h-[17.31%]', 'Azure Files', 'The shared data folder both read and write', false],
              ['left-[33%] top-[61.54%] w-[30%] h-[17.31%]', 'Container Apps Job', 'The engine and the pipeline, one run per match', false],
              ['left-[77%] top-[33.65%] w-[21%] h-[17.31%]', 'Microsoft Foundry', 'The models behind the agents', true],
              ['left-[2%] top-[87.69%] w-[47%] h-[10.77%]', 'Log Analytics · Application Insights', 'Logs and telemetry', false],
              ['left-[51%] top-[87.69%] w-[47%] h-[10.77%]', 'Cost Management budget', 'Spend alerts', false],
            ] as const).map(([pos, name, what, lime]) => (
              <div key={name} className={cn(AZ_BOX, pos, lime ? 'border-primary/55' : 'border-foreground/20')}>
                <span className="font-heading text-[13.5px] font-semibold">{name}</span>
                <span className="text-[12px] leading-[1.4] text-muted-foreground">{what}</span>
              </div>
            ))}
          </div>
        </Panel>
        <Note>Defined as code with Bicep and the Azure Developer CLI.</Note>
      </Section>

      <Section n="05" title="In production" lead="Not part of this submission: competition rules forbid real Premier League data.">
        <Panel className="overflow-x-auto">
          <div className="grid min-w-[500px] grid-cols-[minmax(0,1fr)_28px_minmax(0,1fr)_28px_minmax(0,1.25fr)] grid-rows-[auto_auto] items-center gap-y-3">
            <div className="flex flex-col gap-[3px] rounded-[10px] border border-primary px-3.5 py-3"><span className="font-heading text-[14px] font-semibold">Our engine</span>
              <span className="font-mono text-[10.5px] font-medium uppercase tracking-[.05em] text-primary">This submission</span></div>
            <span className="text-center text-base font-medium text-muted-foreground">→</span>
            <div className="rounded-[10px] border border-foreground/20 px-3.5 py-3 font-heading text-[14px] font-semibold">Tracking format</div>
            <span className="text-center text-base font-medium text-muted-foreground">→</span>
            <div className="col-start-5 row-span-2 row-start-1 flex flex-col justify-center gap-1.5 self-stretch rounded-xl border border-foreground/30 bg-[#0F192B] px-4 py-3.5">
              <span className="font-mono text-[10.5px] font-medium uppercase tracking-[.05em] text-dim">Same pipeline</span>
              <span className="font-heading text-base font-semibold leading-[1.35]">Interpret, Explain, Personalize, Render</span>
            </div>
            <div className="flex flex-col gap-[3px] rounded-[10px] border border-dashed border-foreground/40 px-3.5 py-3"><span className="font-heading text-[14px] font-semibold">Licensed tracking</span>
              <span className="font-mono text-[10.5px] font-medium uppercase tracking-[.05em] text-dim">In production</span></div>
            <span className="text-center text-base font-medium text-muted-foreground">→</span>
            <div className="rounded-[10px] border border-dashed border-foreground/40 px-3.5 py-3 font-heading text-[14px] font-semibold">Same format</div>
            <span className="text-center text-base font-medium text-muted-foreground">→</span>
          </div>
        </Panel>
        <Note>Only the source changes.</Note>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-3">
          {[['Imitation learning (ghosting)', 'Trained on real tracking, the engine learns what each player does given where the other 21 are, so it can play like a real team or player.'],
            ['Team blocks from league data', 'The defensive and pressing block of a team, tuned with its tracking, so a simulated side presses, defends and builds up like the real one.']].map(([t, x]) => (
            <Panel key={t} className="flex flex-col gap-1.5"><span className="font-heading text-[15px] font-semibold">{t}</span><span className="text-pretty text-[13px] leading-[1.55] text-muted-foreground">{x}</span></Panel>
          ))}
        </div>
      </Section>
    </section>
  )
}
