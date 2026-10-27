import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ChevronDown, Mic, MicOff, TriangleAlert } from 'lucide-react'
import { ApiError, activeJobId, createJob, MOCK } from '@/api/client'
import type { Catalog, LibraryEntry } from '@/api/types'
import { GenCard } from '@/components/GenCard'
import { useToast } from '@/components/Toast'
import { isRunning, type NewMatchState } from '@/lib/useNewMatch'
import { HeroVideo } from '@/components/HeroVideo'
import { chipsOf, titleOf, type Chip, type Msg, type Teams } from '@/lib/newMatch'
import { go, matchesPreset } from '@/lib/nav'
import { CardButton, entryCard } from '@/screens/Matches'
import { cn } from '@/lib/utils'
import { useSpeech } from '@/lib/useSpeech'
import { CREST } from '@/lib/format'

interface Props {
  nm: NewMatchState
  catalog: Catalog | null
  catalogError: string | null
  retryCatalog: () => void
  teams: Teams
  /** True when the teams come from a real match; otherwise the example prompts carry no team names. */
  namedTeams: boolean
  entries: LibraryEntry[]
  /** A rendered match whose video plays behind the hero; null: plain navy. */
  heroMatchId: string | null
}

const mono = 'font-mono'
const AgentBadge = () => <span className="grid size-7 flex-none place-items-center rounded-lg border-[1.5px] border-primary font-mono text-[10px] font-semibold text-primary">SA</span>

export function NewMatch({ nm, catalog, catalogError, retryCatalog, teams, namedTeams, entries, heroMatchId }: Props) {
  const toast = useToast()
  const [prompt, setPrompt] = useState('')
  const [menu, setMenu] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [tplOpen, setTplOpen] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  const { msgs, gen } = nm
  const started = msgs.length > 0
  const direct = started && msgs.every((m) => m.kind === 'gen')
  const writing = msgs.some((m) => m.kind === 'writing')
  const latestSetup = [...msgs].reverse().find((m) => m.kind === 'setup')?.id
  const h = namedTeams ? teams.home.short : null
  const a = namedTeams ? teams.away.short : null
  // Real roster: the home number 9 (else the highest number) as the scorer.
  const home = catalog?.players.filter((p) => p.team === 'home') ?? []
  const scorer = (home.find((p) => p.number === 9) ?? [...home].sort((x, y) => y.number - x.number)[0])?.name
  // side = the team that attacks in the suggestion (drives its crest).
  const examples: { text: string; side: 'home' | 'away' }[] = [
    { side: 'away', text: `${a ?? 'Away'} counter, ends in a goal` },
    { side: 'home', text: `${h ?? 'Home'} down the right, ends in a shot` },
    { side: 'home', text: `${h ?? 'Home'} build-up${scorer ? `, goal by ${scorer}` : ', ends in a goal'}` },
  ]
  const refine = ['More pressure', 'End in a goal', `${a ?? 'Away'} in a 5-3-2`]

  useEffect(() => { end.current?.scrollIntoView({ block: 'end', behavior: 'smooth' }) }, [msgs.length, gen?.status?.state])
  useEffect(() => {
    if (!menu) return
    const close = () => setMenu(null)
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && close()
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc) }
  }, [menu])

  // No new messages while the agent writes or a match is being generated.
  const locked = writing || isRunning(gen)
  const send = (text: string) => { if (!text.trim() || locked) return; nm.send(text); setPrompt('') ; setMenu(null) }
  const onKey = (e: React.KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(prompt) } }
  // The spoken text lands in the box; the user reads it and sends it (Enter or the send button).
  const speech = useSpeech(setPrompt, setPrompt)
  const micBtn = (size: number) => (
    <button type="button" onClick={() => void speech.toggle()} disabled={locked && !speech.listening} aria-label={speech.listening ? 'Stop' : 'Speak your match'} aria-pressed={speech.listening}
      className={cn('grid flex-none place-items-center rounded-full border border-foreground/20 text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-40', speech.listening && 'tai-pulse border-primary bg-primary text-primary-foreground hover:text-primary-foreground')}
      style={{ width: size, height: size }}>{speech.listening ? <MicOff aria-hidden className="size-1/2" /> : <Mic aria-hidden className="size-1/2" />}</button>
  )
  const speechError = speech.error && <p role="alert" className="text-[12.5px] text-muted-foreground">{speech.error}</p>
  const sendBtn = (size: number) => (
    <button type="button" onClick={() => send(prompt)} aria-label="Send to the Scenario Agent" disabled={!prompt.trim() || locked}
      className={cn('grid flex-none place-items-center rounded-full font-bold transition-[background,transform] active:scale-95', prompt.trim() && !locked ? 'bg-primary text-primary-foreground' : 'bg-[#2a3650] text-dim')}
      style={{ width: size, height: size }}>↑</button>
  )

  async function openTemplate(e: LibraryEntry) {
    if (e.match_id) return go(`/matches/${e.match_id}`)
    if (busy) return
    setBusy(true)
    try {
      const r = await createJob({ library_id: e.entry_id })
      go(r.kind === 'existing' ? `/matches/${r.match_id}` : `/jobs/${r.job_id}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast('A match is already being generated')
        const id = activeJobId(err)
        if (id) go(`/jobs/${id}`)
      } else toast(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }
  const tplCards = [...entries.filter((e) => e.match_id).slice(0, 5), ...entries.filter((e) => !e.match_id).slice(0, 3)].map((e) => entryCard(e, teams, catalog, () => void openTemplate(e)))

  const banner = (
    <>
      {MOCK && <span className="mb-3 inline-block self-center rounded-full border border-primary px-2 py-0.5 text-xs text-primary">Mock data</span>}
      {catalogError && (
        <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-foreground/20 bg-panel px-4 py-3 text-sm">
          <span>Could not load the catalog: {catalogError}</span>
          <button type="button" onClick={retryCatalog} className="rounded-lg border border-foreground/25 px-3 py-1.5 text-[12.5px] font-semibold hover:border-primary hover:text-primary">Retry</button>
        </div>
      )}
    </>
  )

  if (!started) {
    return (
      <section className="flex w-full flex-col pb-16">
        <div className="relative isolate flex min-h-[calc(100dvh-96px)] items-center px-8 py-[72px]">
          <HeroVideo matchId={heroMatchId} />
          <div role="group" aria-label={`Every match: ${teams.home.name} vs ${teams.away.name}. Two fictional clubs, every match is between them.`} className="absolute inset-x-8 top-9 flex flex-col items-center gap-2 [text-shadow:0_2px_14px_rgba(0,0,0,.7)]">
            <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-[17px] font-semibold">
              <img src={CREST.home} alt="" className="size-8 object-contain" />
              <span title={teams.home.short}>{teams.home.name}</span>
              <span aria-hidden className="font-mono text-xs font-normal text-muted-foreground">vs</span>
              <span title={teams.away.short}>{teams.away.name}</span>
              <img src={CREST.away} alt="" className="size-8 object-contain" />
            </div>
            <span className="text-center font-mono text-[11px] uppercase tracking-[.08em] text-muted-foreground">Two fictional clubs · every match is between them</span>
          </div>
          <div className="mx-auto flex w-full max-w-[960px] flex-col gap-6">
            {banner}
            <h1 className="text-balance text-center text-[44px] font-semibold leading-[1.08] tracking-[-0.03em] [text-shadow:0_2px_18px_rgba(0,0,0,.6)]">Generate synthetic match data</h1>
            <p className="mx-auto -mt-2 max-w-[640px] text-pretty text-center text-[17px] leading-relaxed text-muted-foreground [text-shadow:0_1px_10px_rgba(0,0,0,.7)]">Prompt a play, check the setup, and the engine records the video, tracking and events. The agents explain each moment.</p>
            <div className="flex items-end gap-3 rounded-[20px] border border-foreground/20 bg-panel py-5 pl-6 pr-4 shadow-[0_18px_50px_rgba(0,0,0,.35)] focus-within:border-primary">
              <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} onKeyDown={onKey} rows={3} aria-label="Describe the play you want"
                placeholder={speech.listening ? 'Listening…' : `Describe a play, e.g. ${examples[0].text}`}
                className="flex-1 resize-none bg-transparent py-0.5 text-[20px] leading-normal outline-none placeholder:text-dim" />
              {micBtn(52)}
              {sendBtn(52)}
            </div>
            {speechError}
            <div className="flex flex-wrap justify-center gap-2 [text-shadow:0_1px_8px_rgba(0,0,0,.6)]">
              {examples.map((x) => (
                <button key={x.text} type="button" onClick={() => send(x.text)} className="flex items-center gap-2 whitespace-nowrap rounded-full border border-foreground/20 bg-background/60 py-1.5 pl-2 pr-3 text-[13px] font-medium text-muted-foreground hover:border-foreground/45 hover:text-foreground">
                  <img src={CREST[x.side]} alt="" className="size-[18px] object-contain" />{x.text}
                </button>
              ))}
            </div>
          </div>
        </div>
        {tplCards.length > 0 && (
          <div className="mx-auto mt-4 flex w-full max-w-[1600px] flex-col px-8">
            <div className="flex items-center justify-between gap-4">
              <button type="button" aria-expanded={tplOpen} aria-controls="tpl-grid" onClick={() => setTplOpen((o) => !o)}
                className="flex items-center gap-2 py-1 font-heading text-xl font-semibold tracking-[-0.015em] hover:text-primary">
                Templates
                <ChevronDown aria-hidden className={cn('size-5 transition-transform duration-300 motion-reduce:transition-none', tplOpen && 'rotate-180')} />
              </button>
              <button type="button" onClick={() => go('/matches')} className="py-1 text-[13px] font-semibold text-primary hover:text-foreground">View all</button>
            </div>
            <div id="tpl-grid" className={cn('grid transition-[grid-template-rows,opacity] duration-300 motion-reduce:transition-none', tplOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0')} inert={!tplOpen}>
              <div className="overflow-hidden">
                <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-3 pt-4">
                  {tplCards.map((c, i) => <CardButton key={c.key} c={c} i={i} disabled={busy} />)}
                </div>
              </div>
            </div>
          </div>
        )}
      </section>
    )
  }

  return (
    <section className="mx-auto flex w-full max-w-[1120px] flex-1 flex-col gap-[18px] px-7 pt-7">
      <div className="flex items-center justify-between gap-3 border-b border-foreground/[.06] pb-1.5">
        <span className="font-heading text-[15px] font-semibold">New match</span>
        <span className="flex items-center gap-[7px] text-xs font-medium text-muted-foreground">
          {!isRunning(gen) && !writing && <button type="button" onClick={nm.reset} className="mr-3 text-dim hover:text-foreground">Start over</button>}
          <span className="size-[7px] rounded-full bg-primary" />Synthetic engine
        </span>
      </div>
      {banner}
      {msgs.map((m) => (
        <div key={m.id} className="rise flex flex-col">
          <Message m={m} nm={nm} catalog={catalog} teams={teams} live={m.id === latestSetup} menu={menu} setMenu={setMenu} />
        </div>
      ))}
      <div className="min-h-6 flex-1" />
      {!direct && (
        <div className="sticky bottom-0 z-20 bg-gradient-to-t from-background from-70% to-transparent pb-[18px] pt-3">
          <div className="mx-auto flex w-full max-w-[780px] flex-col gap-2">
            <div className="flex flex-wrap gap-1.5">
              {refine.map((x) => (
                <button key={x} type="button" onClick={() => send(x)} disabled={locked} className="rounded-full border border-foreground/15 bg-background px-2.5 py-[5px] text-xs font-medium text-muted-foreground hover:border-foreground/40 hover:text-foreground disabled:pointer-events-none disabled:opacity-40">{x}</button>
              ))}
            </div>
            <div className={cn('flex items-end gap-2.5 rounded-2xl border border-foreground/15 bg-panel py-2.5 pl-4 pr-2.5 shadow-[0_-8px_30px_rgba(0,0,0,.25)]', locked && 'opacity-60')}>
              <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} onKeyDown={onKey} rows={1} aria-label="Refine the setup" disabled={locked}
                placeholder={speech.listening ? 'Listening…' : isRunning(gen) ? 'Generating the match. You can write again when it is done.' : 'Refine the setup, or ask for another play'} className="flex-1 resize-none bg-transparent py-1.5 text-[15px] leading-normal outline-none placeholder:text-dim disabled:cursor-not-allowed" />
              {micBtn(38)}
              {sendBtn(38)}
            </div>
            {speechError}
          </div>
        </div>
      )}
      <div ref={end} />
    </section>
  )
}

function Message({ m, nm, catalog, teams, live, menu, setMenu }: { m: Msg; nm: NewMatchState; catalog: Catalog | null; teams: Teams; live: boolean; menu: string | null; setMenu: (k: string | null) => void }) {
  if (m.kind === 'user') {
    return <div className="max-w-[min(640px,80%)] self-end rounded-[16px_16px_4px_16px] border border-foreground/10 bg-[#1a2740] px-[15px] py-[11px] text-[15px] leading-normal">{m.text}</div>
  }
  if (m.kind === 'writing') {
    return (
      <div className="flex w-full max-w-[780px] items-center gap-2.5">
        <AgentBadge />
        <span className="text-sm font-medium text-muted-foreground">Scenario Agent is writing the tactical setup</span>
        <span className="flex gap-1">{[0, 0.2, 0.4].map((d) => <span key={d} className="tai-pulse size-[5px] rounded-full bg-primary" style={{ animationDelay: `${d}s` }} />)}</span>
      </div>
    )
  }
  if (m.kind === 'setup') {
    const open = live && !m.used
    const chips = catalog ? chipsOf(m.recipe, catalog, teams) : []
    return (
      <div className="grid w-full max-w-[780px] grid-cols-[28px_minmax(0,1fr)] gap-2.5">
        <AgentBadge />
        <div className="flex min-w-0 flex-col gap-2.5">
          <span className="text-[12.5px] font-semibold text-muted-foreground">Scenario Agent</span>
          <span className="text-base leading-normal">{m.note}</span>
          <div className="flex flex-col gap-6 rounded-[14px] border border-foreground/15 bg-panel p-4 min-[520px]:p-6">
            <div className="flex flex-col gap-1.5">
              <span className={cn(mono, 'text-xs font-medium uppercase tracking-[.06em] text-dim')}>Tactical setup</span>
              <h3 className="font-heading text-xl font-semibold leading-snug">{titleOf(m.recipe, teams)}</h3>
            </div>
            {(() => {
              const chip = (c: Chip, full = false) => <ChipButton key={c.key} c={c} id={`${m.id}:${c.key}`} full={full} enabled={open} menu={menu} setMenu={setMenu} pick={(v) => { nm.setChip(m.id, c.key, v); setMenu(null) }} />
              const g = (x: Chip['group']) => chips.filter((c) => c.group === x)
              const play = g('play')
              const lines: Chip[][] = []
              for (const c of play) {
                if (c.key.startsWith('want') && /want\d+$/.test(c.key)) lines.push([c])
                else if (c.key.startsWith('want')) lines[lines.length - 1].push(c)
                else if (c.key === 'sit') lines.unshift([c])
                else lines[0].push(c)
              }
              const mode = g('mode')[0]
              const label = (x: string) => <span className={cn(mono, 'text-xs font-medium uppercase tracking-[.06em] text-dim')}>{x}</span>
              const rowLabel: Record<string, string> = { f: 'Formation', s: 'Style', l: 'Level' }
              return (
                <>
                  {play.length > 0 && (
                    <div className="flex flex-col gap-3">
                      {label('The play')}
                      {lines.map((l, i) => (
                        <div key={i} className="flex flex-wrap items-center gap-x-3 gap-y-3 text-base text-muted-foreground">
                          {l.map((c) => <Fragment key={c.key}>{c.pre && <span>{c.pre}</span>}{chip(c)}</Fragment>)}
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="grid grid-cols-1 items-stretch gap-3 min-[640px]:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
                    {(['home', 'away'] as const).map((s, i) => (
                      <Fragment key={s}>
                        {i === 1 && <span className={cn(mono, 'grid size-8 place-items-center place-self-center rounded-full border border-foreground/15 bg-[#152034] text-[11px] text-dim')}>vs</span>}
                        <div className="flex min-w-0 flex-col gap-4 rounded-xl bg-[#1a2740]/60 p-4">
                          <div className="flex items-center gap-2.5">
                            <img src={CREST[s]} alt="" className="size-7 object-contain" />
                            <span title={teams[s].name} className="font-heading text-base font-semibold">{teams[s].short}</span>
                            <span className="min-w-0 truncate text-[13px] text-muted-foreground">{teams[s].name}</span>
                          </div>
                          <div className="grid grid-cols-[88px_minmax(0,1fr)] items-center gap-x-3 gap-y-3">
                            {g(s).map((c) => (
                              <Fragment key={c.key}>
                                {label(rowLabel[c.key.slice(-1)] ?? c.k)}
                                {chip(c, true)}
                              </Fragment>
                            ))}
                          </div>
                        </div>
                      </Fragment>
                    ))}
                  </div>
                  {mode && (<>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
                      <span className="w-[88px]">{label('Mode')}</span>
                      <div role="group" aria-label="Mode" className="flex rounded-lg border border-foreground/15 bg-[#152034] p-0.5">
                        {mode.opts.map((o) => (
                          <button key={o.value} type="button" aria-pressed={o.value === mode.cur} disabled={!open} onClick={() => { nm.setChip(m.id, mode.key, o.value); setMenu(null) }}
                            className={cn('h-9 rounded-md px-4 text-base font-medium transition-colors', o.value === mode.cur ? 'bg-[#22304a] text-foreground' : 'text-muted-foreground', open && o.value !== mode.cur && 'hover:text-foreground')}>{o.label}</button>
                        ))}
                      </div>
                    </div>
                    {mode.cur === 'full_match' && (
                      <p role="status" className="-mt-3 flex items-center gap-2 text-base text-muted-foreground"><TriangleAlert aria-hidden className="size-4 shrink-0 text-foreground" />A full match can take up to 20 minutes to generate.</p>
                    )}
                  </>)}
                </>
              )
            })()}
            {m.issues.length > 0 && (
              <ul className="list-disc pl-4 text-xs text-muted-foreground">{m.issues.map((i, k) => <li key={k}><code>{i.path}</code>: {i.message}</li>)}</ul>
            )}
            <div className="flex flex-wrap items-center justify-end gap-x-4 gap-y-3 border-t border-foreground/[.08] pt-4">
              <span className="flex-1 text-[13px] text-dim">Nothing runs until Generate.</span>
              <button type="button" disabled={!open || nm.starting !== null} onClick={() => void nm.generate(m.id)}
                className={cn('h-11 rounded-[10px] border px-6 font-heading text-[15px] font-semibold transition-[background,transform] active:scale-[.97]', open ? 'border-primary bg-primary text-primary-foreground' : 'border-foreground/15 text-dim')}>
                {m.used ? 'Generated' : open ? (nm.starting === m.id ? 'Starting…' : 'Generate') : 'Replaced by a newer setup'}
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }
  if (m.kind === 'error') {
    return (
      <div className="grid w-full max-w-[780px] grid-cols-[28px_minmax(0,1fr)] gap-2.5">
        <AgentBadge />
        <div role="alert" className="grid grid-cols-[30px_minmax(0,1fr)] items-start gap-3 rounded-xl border-[1.5px] border-foreground bg-[#141f33] px-4 py-3.5">
          <span className="grid size-[30px] place-items-center rounded-md bg-foreground text-[15px] font-bold leading-none text-background">✕</span>
          <div className="flex flex-col gap-[5px]">
            <span className={cn(mono, 'text-[11px] font-semibold uppercase tracking-[.06em]')}>Error{m.code ? ` · ${m.code}` : ''}</span>
            <span className="font-heading text-base font-semibold">{m.msg}</span>
            <span className="text-[13px] leading-normal text-muted-foreground">{m.todo}</span>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-2">
              {m.toMatches && (
                <button type="button" onClick={() => { matchesPreset.value = 'templates'; go('/matches') }} className="rounded-lg border border-foreground/30 px-3 py-[7px] text-[12.5px] font-semibold hover:border-primary hover:text-primary">Watch a template meanwhile</button>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }
  if (!nm.gen || nm.gen.jobId !== m.jobId) return <span className={cn(mono, 'pl-[38px] text-xs font-medium text-dim')}>Earlier generation</span>
  return <GenCard jobId={m.jobId} title={nm.gen.title} status={nm.gen.status} error={nm.gen.error} />
}

function ChipButton({ c, id, full, enabled, menu, setMenu, pick }: { c: Chip; id: string; full?: boolean; enabled: boolean; menu: string | null; setMenu: (k: string | null) => void; pick: (v: string) => void }) {
  const open = enabled && menu === id
  const wrap = useRef<HTMLDivElement>(null)
  const list = useRef<HTMLDivElement>(null)
  const [up, setUp] = useState(false)
  const players = c.key.endsWith('p') && c.key.startsWith('want')
  // Flip upward when the menu does not fit below the trigger and there is more room above.
  useLayoutEffect(() => {
    if (!open || !wrap.current || !list.current) return
    const r = wrap.current.getBoundingClientRect()
    const need = list.current.offsetHeight + 12
    setUp(window.innerHeight - r.bottom < need && r.top > window.innerHeight - r.bottom)
  }, [open])
  return (
    <div ref={wrap} className={cn('relative', full && 'w-full')} onMouseDown={(e) => e.stopPropagation()}>
      <button type="button" aria-label={c.k} aria-expanded={open} aria-haspopup="menu" disabled={!enabled} onClick={() => setMenu(open ? null : id)}
        className={cn('flex h-10 items-center gap-2 rounded-lg border bg-[#1a2740] px-3 text-base font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60', full && 'w-full', open ? 'border-primary' : 'border-foreground/[.18]', enabled ? 'cursor-pointer hover:border-primary hover:bg-[#213152]' : 'cursor-default text-muted-foreground')}>
        {c.crest && <img src={CREST[c.crest]} alt="" className="size-5 object-contain" />}<span className="flex-1 truncate text-left">{c.v}</span>{enabled && <ChevronDown aria-hidden className="size-4 shrink-0 text-muted-foreground" />}
      </button>
      {open && (
        <div ref={list} role="menu" className={cn('absolute left-0 z-30 w-max min-w-[max(100%,240px)] max-w-[min(420px,90vw)] overflow-x-hidden rounded-[10px] border border-foreground/15 bg-[#18243a] p-1 shadow-[0_14px_34px_rgba(0,0,0,.4)]', up ? 'bottom-[calc(100%+6px)]' : 'top-[calc(100%+6px)]', players ? 'grid max-h-[70vh] grid-cols-2 overflow-y-auto' : 'flex flex-col')}>
          {c.opts.map((o) => (
            <button key={o.value} type="button" role="menuitem" onClick={() => pick(o.value)} className="grid min-h-11 grid-cols-[16px_minmax(0,1fr)] items-center gap-2 rounded-[7px] px-2 py-2 text-left text-base font-medium hover:bg-[#22304a]">
              <span className="text-xs font-bold text-primary">{o.value === c.cur ? '✓' : ''}</span>
              <span className="flex items-center gap-2">{c.crest && (o.value === 'home' || o.value === 'away') && <img src={CREST[o.value]} alt="" className="size-5 object-contain" />}<span className="flex flex-col"><span>{o.label}</span>{o.sub && <span className="text-[13px] font-normal text-dim">{o.sub}</span>}</span></span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
