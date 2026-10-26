import { useEffect, useRef, useState } from 'react'
import { ApiError, activeJobId, createJob, MOCK } from '@/api/client'
import type { Catalog, LibraryEntry } from '@/api/types'
import { GenCard } from '@/components/GenCard'
import { useToast } from '@/components/Toast'
import { isRunning, type NewMatchState } from '@/lib/useNewMatch'
import { chipsOf, titleOf, type Chip, type Msg, type Teams } from '@/lib/newMatch'
import { go, matchesPreset } from '@/lib/nav'
import { CardButton, type Card } from '@/screens/Matches'
import { cn } from '@/lib/utils'

interface Props {
  nm: NewMatchState
  catalog: Catalog | null
  catalogError: string | null
  retryCatalog: () => void
  teams: Teams
  /** True when the teams come from a real match; otherwise the example prompts carry no team names. */
  namedTeams: boolean
  entries: LibraryEntry[]
}

const mono = 'font-mono'
const AgentBadge = () => <span className="grid size-7 flex-none place-items-center rounded-lg border-[1.5px] border-primary font-mono text-[10px] font-semibold text-primary">SA</span>

export function NewMatch({ nm, catalog, catalogError, retryCatalog, teams, namedTeams, entries }: Props) {
  const toast = useToast()
  const [prompt, setPrompt] = useState('')
  const [menu, setMenu] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  const { msgs, gen } = nm
  const started = msgs.length > 0
  const direct = started && msgs.every((m) => m.kind === 'gen')
  const writing = msgs.some((m) => m.kind === 'writing')
  const latestSetup = [...msgs].reverse().find((m) => m.kind === 'setup')?.id
  const h = namedTeams ? teams.home.name : null
  const a = namedTeams ? teams.away.name : null
  const examples = [
    `A ${a ? `${a} ` : ''}counter-attack that ends in a goal`,
    `${h ? `${h} attack` : 'An attack'} down the right, ends in a shot`,
    `A ${h ? `${h} ` : ''}build-up that ends in a goal`,
  ]
  const refine = ['More pressure', 'Make it end in a goal', a ? `${a} in a 5-3-2` : 'Switch to a 5-3-2']

  useEffect(() => { end.current?.scrollIntoView({ block: 'end', behavior: 'smooth' }) }, [msgs.length, gen?.status?.state])
  useEffect(() => {
    if (!menu) return
    const close = () => setMenu(null)
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && close()
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc) }
  }, [menu])

  const send = (text: string) => { if (!text.trim() || writing) return; nm.send(text); setPrompt('') ; setMenu(null) }
  const onKey = (e: React.KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(prompt) } }
  const sendBtn = (size: number) => (
    <button type="button" onClick={() => send(prompt)} aria-label="Send to the Scenario Agent" disabled={!prompt.trim() || writing}
      className={cn('grid flex-none place-items-center rounded-full font-bold transition-[background,transform] active:scale-95', prompt.trim() && !writing ? 'bg-primary text-primary-foreground' : 'bg-[#2a3650] text-dim')}
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
  const tplCards: Card[] = [...entries.filter((e) => e.match_id).slice(0, 5), ...entries.filter((e) => !e.match_id).slice(0, 3)].map((e) => ({
    key: e.entry_id, title: e.title, home: e.home.formation, away: e.away.formation, tag: e.wanted[0]?.startsWith('goal') ? 'GOAL' : 'SHOT',
    video: !!e.match_id, generated: false, open: () => void openTemplate(e),
  }))

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
      <section className="mx-auto flex w-full max-w-[1120px] flex-col gap-16 px-8 py-[72px]">
        <div className="mx-auto flex w-full max-w-[780px] flex-col gap-[22px]">
          {banner}
          <div className="flex flex-col items-center gap-2.5 text-center">
            <h1 className="text-[40px] font-semibold leading-[1.08] tracking-[-0.03em]">Start a match</h1>
            <p className="text-base text-muted-foreground">Bring in a tracking feed, or ask the engine for the play you need.</p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <span className={cn(mono, 'mr-1 text-[11px] font-medium uppercase tracking-[.06em] text-dim')}>Source</span>
            <button type="button" aria-pressed="true" className="flex items-center gap-[7px] rounded-full border border-primary bg-primary px-3 py-[7px] text-[13px] font-semibold text-primary-foreground">
              <span className="size-[7px] rounded-full bg-primary-foreground" />Synthetic engine
            </button>
            <button type="button" disabled title="Available in production" className="flex cursor-not-allowed items-center gap-2 rounded-full border border-dashed border-foreground/25 px-3 py-[7px] text-[13px] font-semibold text-dim">
              Broadcast tracking<span className={cn(mono, 'rounded border border-foreground/25 px-[5px] py-px text-[10px] font-semibold tracking-[.04em] text-muted-foreground')}>PRODUCTION</span>
            </button>
          </div>
          <div className="flex items-end gap-3 rounded-[18px] border border-foreground/15 bg-panel py-4 pl-[18px] pr-3.5 pb-3 focus-within:border-primary">
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} onKeyDown={onKey} rows={3} aria-label="Describe the play you want"
              placeholder={`Describe the play you want: ${examples[0].replace(/^A /, 'a ')}`}
              className="flex-1 resize-none bg-transparent py-0.5 text-[17px] leading-normal outline-none placeholder:text-dim" />
            {sendBtn(44)}
          </div>
          <div className="flex flex-wrap justify-center gap-1.5">
            {examples.map((x) => (
              <button key={x} type="button" onClick={() => send(x)} className="rounded-full border border-foreground/15 px-[11px] py-1.5 text-[12.5px] font-medium text-muted-foreground hover:border-foreground/40 hover:text-foreground">{x}</button>
            ))}
          </div>
        </div>
        {tplCards.length > 0 && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div className="flex flex-col gap-1">
                <span className="font-heading text-xl font-semibold tracking-[-0.015em]">From template</span>
                <span className="text-[13px] text-muted-foreground">Already recorded and analysed. Open one to watch it now.</span>
              </div>
              <button type="button" onClick={() => go('/matches')} className="py-1 text-[13px] font-semibold text-primary hover:text-foreground">All {entries.length} in Matches →</button>
            </div>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
              {tplCards.map((c, i) => <CardButton key={c.key} c={c} i={i} disabled={busy} />)}
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
                <button key={x} type="button" onClick={() => send(x)} className="rounded-full border border-foreground/15 bg-background px-2.5 py-[5px] text-xs font-medium text-muted-foreground hover:border-foreground/40 hover:text-foreground">{x}</button>
              ))}
            </div>
            <div className="flex items-end gap-2.5 rounded-2xl border border-foreground/15 bg-panel py-2.5 pl-4 pr-2.5 shadow-[0_-8px_30px_rgba(0,0,0,.25)]">
              <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} onKeyDown={onKey} rows={1} aria-label="Refine the setup"
                placeholder="Refine the setup, or ask for another play" className="flex-1 resize-none bg-transparent py-1.5 text-[15px] leading-normal outline-none placeholder:text-dim" />
              {sendBtn(38)}
            </div>
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
          <span className="text-[14.5px] leading-normal">{m.note}</span>
          <div className="flex flex-col gap-3 rounded-[14px] border border-foreground/15 bg-panel px-4 py-3.5">
            <div className="flex flex-wrap items-baseline justify-between gap-2.5">
              <span className={cn(mono, 'text-[10.5px] font-medium uppercase tracking-[.06em] text-dim')}>Tactical setup</span>
              <span className="font-heading text-sm font-semibold">{titleOf(m.recipe, teams)}</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {chips.map((c) => <ChipButton key={c.key} c={c} id={`${m.id}:${c.key}`} enabled={open} menu={menu} setMenu={setMenu} pick={(v) => { nm.setChip(m.id, c.key, v); setMenu(null) }} />)}
            </div>
            {m.issues.length > 0 && (
              <ul className="list-disc pl-4 text-xs text-muted-foreground">{m.issues.map((i, k) => <li key={k}><code>{i.path}</code>: {i.message}</li>)}</ul>
            )}
            <div className="flex items-center justify-end gap-3 border-t border-foreground/[.08] pt-3">
              <span className="flex-1 text-xs text-dim">Nothing runs until you press Generate.</span>
              <button type="button" disabled={!open || nm.starting !== null} onClick={() => void nm.generate(m.id)}
                className={cn('rounded-[10px] border px-[18px] py-2.5 font-heading text-[14.5px] font-semibold transition-[background,transform] active:scale-[.97]', open ? 'border-primary bg-primary text-primary-foreground' : 'border-foreground/15 text-dim')}>
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
              {m.code && <button type="button" onClick={() => go('/arch')} className="text-[12.5px] font-semibold text-primary hover:text-foreground">About {m.code} →</button>}
            </div>
          </div>
        </div>
      </div>
    )
  }
  if (!nm.gen || nm.gen.jobId !== m.jobId) return <span className={cn(mono, 'pl-[38px] text-xs font-medium text-dim')}>Earlier generation</span>
  return <GenCard jobId={m.jobId} title={nm.gen.title} status={nm.gen.status} error={nm.gen.error} />
}

function ChipButton({ c, id, enabled, menu, setMenu, pick }: { c: Chip; id: string; enabled: boolean; menu: string | null; setMenu: (k: string | null) => void; pick: (v: string) => void }) {
  const open = enabled && menu === id
  return (
    <div className="relative" onMouseDown={(e) => e.stopPropagation()}>
      <button type="button" aria-expanded={open} aria-haspopup="menu" disabled={!enabled} onClick={() => setMenu(open ? null : id)}
        className={cn('flex items-center gap-1.5 rounded-lg border bg-[#152034] px-2.5 py-1.5 text-[12.5px] font-medium transition-colors', open ? 'border-primary' : 'border-foreground/15', enabled ? 'cursor-pointer' : 'cursor-default text-muted-foreground')}>
        <span className={cn(mono, 'text-[10.5px] font-semibold text-dim')}>{c.k}</span>{c.v}<span className="text-[9px] text-dim">▾</span>
      </button>
      {open && (
        <div role="menu" className="absolute left-0 top-[calc(100%+6px)] z-30 flex max-h-[300px] min-w-[200px] flex-col overflow-auto rounded-[10px] border border-foreground/15 bg-[#18243a] p-1 shadow-[0_14px_34px_rgba(0,0,0,.4)]">
          {c.opts.map((o) => (
            <button key={o.value} type="button" role="menuitem" onClick={() => pick(o.value)} className="grid grid-cols-[16px_minmax(0,1fr)] items-center gap-2 rounded-[7px] px-2 py-[7px] text-left text-[13px] font-medium hover:bg-[#22304a]">
              <span className="text-xs font-bold text-primary">{o.value === c.cur ? '✓' : ''}</span>
              <span className="flex flex-col"><span>{o.label}</span>{o.sub && <span className="text-[11px] font-normal text-dim">{o.sub}</span>}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
