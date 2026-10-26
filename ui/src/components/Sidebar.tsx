import { ChevronsLeft, ChevronsRight, Plus } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Props {
  route: string // first path segment: '', jobs, matches, arch
  min: boolean
  onToggle: () => void
  matchesCount: number
  /** Title of the job running while the user is on another screen; the New match screen (batch C) sets it. */
  busyLabel?: string
}

export function Sidebar({ route, min, onToggle, matchesCount, busyLabel }: Props) {
  const isNew = route === '' || route === 'jobs'
  const row = 'flex h-[42px] items-center gap-2.5 whitespace-nowrap rounded-[10px] px-3 text-sm font-semibold transition-colors'
  const justify = min ? 'justify-center' : 'justify-start'
  return (
    <aside
      className="sticky top-0 z-40 flex h-screen flex-none flex-col gap-4 overflow-hidden border-r border-foreground/10 bg-sidebar px-3 pb-3.5 pt-[18px] transition-[width] duration-300 ease-out motion-reduce:transition-none"
      style={{ width: min ? 64 : 232 }}
    >
      <div className="flex min-h-8 items-center justify-between gap-1.5">
        {!min && <a href="#/" aria-label="tacticAI"><img src="/tacticai-logo-dark-bg.png" alt="tacticAI" className="ml-2 h-6 w-auto" /></a>}
        <button
          type="button" onClick={onToggle} aria-label={min ? 'Expand sidebar' : 'Collapse sidebar'} title={min ? 'Expand sidebar' : 'Collapse sidebar'}
          className="mx-auto grid size-8 flex-none place-items-center rounded-lg border border-foreground/15 text-muted-foreground hover:border-foreground/35 hover:text-foreground"
        >
          {min ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
        </button>
      </div>
      <a
        href="#/" aria-label="New match" title="New match (N)" aria-current={isNew ? 'page' : undefined}
        className={cn(row, justify, 'bg-foreground text-background hover:bg-white active:scale-[.98]', isNew && 'ring-2 ring-primary')}
      >
        <Plus className="size-[18px]" />
        {!min && <><span className="flex-1">New match</span><span className="font-mono text-[11px] font-semibold text-[#3a4456]">N</span></>}
      </a>
      <a
        href="#/matches" aria-label="Matches" title="Matches" aria-current={route === 'matches' ? 'page' : undefined}
        className={cn(row, justify, 'border text-foreground hover:bg-[#121d31]', route === 'matches' ? 'border-foreground/25 bg-panel' : 'border-transparent')}
      >
        <span className="grid grid-cols-[repeat(2,6px)] gap-0.5" aria-hidden>
          {[0, 1, 2, 3].map((i) => <span key={i} className="size-1.5 rounded-[1.5px] bg-muted-foreground" />)}
        </span>
        {!min && <><span className="flex-1">Matches</span><span className="font-mono text-[11.5px] font-medium text-dim">{matchesCount}</span></>}
      </a>
      {busyLabel && !min && (
        <a href="#/" className="flex items-center gap-2 px-3 text-xs font-medium text-muted-foreground hover:text-foreground">
          <span className="tai-pulse size-[7px] rounded-full bg-primary" />{busyLabel}
        </a>
      )}
      <div className="flex-1" />
      <a
        href="#/arch" aria-label="Architecture: built on Microsoft Foundry, Agent Framework, Azure Container Apps"
        title="Built on Microsoft Foundry · Agent Framework · Azure Container Apps"
        className={cn(
          'rounded-[10px] border text-muted-foreground hover:border-foreground/30 hover:text-foreground',
          route === 'arch' ? 'border-primary/50' : 'border-foreground/10',
          min ? 'grid h-9 place-items-center font-mono text-[10px] font-semibold' : 'flex items-end gap-2 px-3 py-2.5 text-[11.5px] font-medium leading-normal',
        )}
      >
        {min ? 'MS' : <><span className="flex-1">Built on Microsoft Foundry · Agent Framework · Azure Container Apps</span><span className="text-primary">→</span></>}
      </a>
    </aside>
  )
}
