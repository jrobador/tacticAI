import { useEffect, useRef, useState } from 'react'
import type { Lang, Lens, Metric, RosterPlayer } from '@/api/types'
import { cn } from '@/lib/utils'
import { AUDIENCE_NAME, AUDIENCE_RULE, CLUB_BONUS, MORE_AUDIENCES, PLAYER_BONUS, PRIMARY_AUDIENCES, SPOTLIGHT_METRICS, type Profile } from './model'
import { Term } from './Term'

const label = 'font-mono text-[11px] font-medium uppercase tracking-[.06em] text-dim'
const seg = (on: boolean) => cn('rounded-md px-[9px] py-[5px] text-[12.5px] font-semibold', on ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground')

interface Props {
  profile: Profile
  onChange: (p: Profile) => void
  sbs: boolean
  onSbs: (v: boolean) => void
  short: Record<'home' | 'away', string>
  roster: RosterPlayer[]
}

/** Audience switch (with More), Side by side, the audience line and the profile bar. */
export function AudienceBar({ profile, onChange, sbs, onSbs, short, roster }: Props) {
  const [more, setMore] = useState(false)
  const menu = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!more) return
    const close = (e: MouseEvent) => { if (!menu.current?.contains(e.target as Node)) setMore(false) }
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setMore(false)
    document.addEventListener('mousedown', close)
    window.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', close); window.removeEventListener('keydown', esc) }
  }, [more])

  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => onChange({ ...profile, [k]: v })
  const inMore = MORE_AUDIENCES.find((a) => a.id === profile.lens)
  const player = roster.find((p) => p.player_id === profile.player)
  const adj = [profile.club !== 'neutral' ? `${short[profile.club]} moments +${CLUB_BONUS}` : '', player ? `${player.name} +${PLAYER_BONUS}` : ''].filter(Boolean).join(' · ')
  const pick = (lens: Lens) => { set('lens', lens); setMore(false) }

  return (
    <>
      <div className="flex flex-wrap items-center gap-x-3.5 gap-y-2">
        <div className="flex items-center gap-2">
          <span className={label}><Term k="audience">Audience</Term></span>
          <div className="relative flex gap-0.5 rounded-[10px] border border-foreground/10 bg-[#152034] p-[3px]" role="radiogroup" aria-label="Audience">
            {PRIMARY_AUDIENCES.map((a) => (
              <button
                key={a.id} type="button" role="radio" aria-checked={profile.lens === a.id} onClick={() => pick(a.id)}
                className={cn('rounded-[7px] px-3 py-1.5 text-[13px] font-semibold transition-colors duration-150', profile.lens === a.id ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground')}
              >
                {a.name}
              </button>
            ))}
            <div ref={menu} className="relative">
              <button
                type="button" aria-expanded={more} aria-haspopup="menu" onClick={() => setMore((v) => !v)}
                className={cn('rounded-[7px] px-2.5 py-1.5 text-[13px] font-semibold', inMore ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground')}
              >
                {inMore ? inMore.name : 'More'} ▾
              </button>
              {more && (
                <div role="menu" className="absolute right-0 top-[calc(100%+6px)] z-30 flex min-w-[180px] flex-col rounded-[10px] border border-foreground/15 bg-[#18243a] p-1 shadow-[0_14px_34px_rgba(0,0,0,.4)]">
                  {MORE_AUDIENCES.map((a) => (
                    <button
                      key={a.id} type="button" role="menuitem" onClick={() => pick(a.id)}
                      className="grid grid-cols-[16px_1fr] gap-2 rounded-[7px] p-2 text-left text-[13px] font-medium hover:bg-[#22304a]"
                    >
                      <span className="font-bold text-primary">{profile.lens === a.id ? '✓' : ''}</span>{a.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
        <button type="button" role="switch" aria-checked={sbs} onClick={() => onSbs(!sbs)} className="ml-auto flex items-center gap-[9px] py-1 text-[13px] font-semibold">
          <span className={cn('relative h-5 w-9 rounded-full transition-colors duration-200', sbs ? 'bg-primary' : 'bg-[#2a3650]')}>
            <span className="absolute top-0.5 size-4 rounded-full bg-background transition-[left] duration-200 ease-[cubic-bezier(.2,.7,.2,1)]" style={{ left: sbs ? 18 : 2 }} />
          </span>
          Side by side
        </button>
      </div>

      <span className="text-[12.5px] leading-normal text-muted-foreground [text-wrap:pretty]">
        <Term k="audience" className="text-[12.5px] font-semibold leading-normal text-foreground">{AUDIENCE_NAME[profile.lens]}</Term>: {AUDIENCE_RULE[profile.lens].line}
        {adj && <span className="text-primary"> {adj}</span>}
      </span>

      <div className="flex flex-wrap items-center gap-x-[18px] gap-y-2 rounded-[10px] border border-foreground/10 bg-[#0f192b] px-2.5 py-1.5">
        <Group name="Language">
          {(['en', 'es'] as Lang[]).map((l) => <button key={l} type="button" onClick={() => set('lang', l)} aria-pressed={profile.lang === l} className={seg(profile.lang === l)}>{l.toUpperCase()}</button>)}
        </Group>
        <Group name="Side">
          {([['neutral', 'Neutral'], ['home', short.home], ['away', short.away]] as const).map(([k, l]) => (
            <button key={k} type="button" onClick={() => set('club', k)} aria-pressed={profile.club === k} className={seg(profile.club === k)}>{l}</button>
          ))}
        </Group>
        <div className="flex items-center gap-2">
          <span className={label}>Player focus</span>
          <select
            aria-label="Player focus" value={profile.player ?? ''} onChange={(e) => set('player', e.target.value || null)}
            className={cn('rounded-lg border bg-[#152034] px-2 py-[5px] text-[12.5px] font-medium text-foreground', profile.player ? 'border-primary' : 'border-foreground/10')}
          >
            <option value="">None</option>
            {roster.filter((p) => p.role !== 'GK').map((p) => <option key={p.player_id} value={p.player_id}>{p.name} · {short[p.team]} #{p.number}</option>)}
          </select>
        </div>
        {profile.lens === 'one_metric' && (
          <Group name="Spotlight metric">
            {SPOTLIGHT_METRICS.map((m) => <button key={m.id} type="button" onClick={() => set('metric', m.id as Metric)} aria-pressed={profile.metric === m.id} className={seg(profile.metric === m.id)}>{m.label}</button>)}
          </Group>
        )}
      </div>
    </>
  )
}

function Group({ name, children }: { name: string; children: React.ReactNode }) {
  return <div className="flex items-center gap-2"><span className={label}>{name}</span><div className="flex gap-0.5">{children}</div></div>
}
