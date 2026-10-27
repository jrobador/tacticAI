import type { Lang, RosterPlayer } from '@/api/types'
import { CREST } from '@/lib/format'
import { cn } from '@/lib/utils'
import { MODES, modeOf, profileFor, type Mode, type Profile } from './model'

const label = 'font-mono text-[11px] font-medium uppercase tracking-[.06em] text-dim'
const seg = (on: boolean) => cn('flex items-center gap-1.5 rounded-md px-[9px] py-[5px] text-[12.5px] font-semibold', on ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground')

interface Props {
  profile: Profile
  onChange: (p: Profile) => void
  short: Record<'home' | 'away', string>
  roster: RosterPlayer[]
  /** Broadcast's feed: Plus airs the tacticAI graphics, Clean hides them. */
  feed?: Feed
  onFeed?: (f: Feed) => void
}
export type Feed = 'plus' | 'clean'

/** The three modes and the settings of the selected mode: Fan has Language, My club and My player; Broadcast has Language and Feed; Analyst has none. */
export function AudienceBar({ profile, onChange, short, roster, feed, onFeed }: Props) {
  const mode = modeOf(profile.lens)
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => onChange({ ...profile, [k]: v })
  const pick = (m: Mode) => onChange(profileFor(m, profile))

  return (
    <>
      <div className="flex flex-wrap items-center gap-x-3.5 gap-y-2">
        <div className="flex gap-0.5 rounded-[10px] border border-foreground/10 bg-[#152034] p-[3px]" role="radiogroup" aria-label="Mode">
          {MODES.map((m) => (
            <button
              key={m.id} type="button" role="radio" aria-checked={mode === m.id} onClick={() => pick(m.id)} title={m.who}
              className={cn('rounded-[7px] px-3.5 py-1.5 text-[13.5px] font-semibold transition-colors duration-150', mode === m.id ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground')}
            >
              {m.name}
            </button>
          ))}
        </div>
        <span className="text-[12.5px] text-muted-foreground">{MODES.find((m) => m.id === mode)?.who}</span>
      </div>

      {mode !== 'analyst' && (
        <div className="flex flex-wrap items-center gap-x-[18px] gap-y-2 rounded-[10px] border border-foreground/10 bg-[#0f192b] px-2.5 py-1.5">
          <Group name="Language">
            {(['en', 'es'] as Lang[]).map((l) => <button key={l} type="button" onClick={() => set('lang', l)} aria-pressed={profile.lang === l} className={seg(profile.lang === l)}>{l.toUpperCase()}</button>)}
          </Group>
          {mode === 'broadcast' && feed && onFeed && (
            <div className="flex items-center gap-2">
              <span className={label}>Feed</span>
              <div className="flex gap-1">
                {([['clean', 'Clean feed'], ['plus', 'Plus feed']] as const).map(([k, l]) => (
                  <button key={k} type="button" onClick={() => onFeed(k)} aria-pressed={feed === k}
                    className={cn('rounded-md border px-2.5 py-[4px] text-[12.5px] font-semibold', feed === k ? 'border-primary bg-primary/[.12] text-primary' : 'border-foreground/15 text-muted-foreground hover:text-foreground')}>{l}</button>
                ))}
              </div>
              <span className="text-xs text-dim">{feed === 'clean' ? 'Engine graphics only.' : 'Engine graphics plus tacticAI graphics.'}</span>
            </div>
          )}
          {mode === 'fan' && (
            <>
              <Group name="My club">
                {([['neutral', 'None'], ['home', short.home], ['away', short.away]] as const).map(([k, l]) => (
                  <button key={k} type="button" onClick={() => set('club', k)} aria-pressed={profile.club === k} className={seg(profile.club === k)}>
                    {k !== 'neutral' && <img src={CREST[k]} alt="" className="size-4 object-contain" />}{l}
                  </button>
                ))}
              </Group>
              <div className="flex items-center gap-2">
                <span className={label}>My player</span>
                <select
                  aria-label="My player" value={profile.player ?? ''} onChange={(e) => set('player', e.target.value || null)}
                  className={cn('rounded-lg border bg-[#152034] px-2 py-[5px] text-[12.5px] font-medium text-foreground', profile.player ? 'border-primary' : 'border-foreground/10')}
                >
                  <option value="">None</option>
                  {roster.filter((p) => p.role !== 'GK').map((p) => <option key={p.player_id} value={p.player_id}>{p.name} · {short[p.team]} #{p.number}</option>)}
                </select>
              </div>
            </>
          )}
        </div>
      )}
    </>
  )
}

function Group({ name, children }: { name: string; children: React.ReactNode }) {
  return <div className="flex items-center gap-2"><span className={label}>{name}</span><div className="flex gap-0.5">{children}</div></div>
}

