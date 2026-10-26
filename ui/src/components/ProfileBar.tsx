import { useEffect, useRef } from 'react'
import type { Brand, Club, Lang, Lens, Metric, OverlayQuery, RosterPlayer } from '@/api/types'
import { cn } from '@/lib/utils'

export interface Profile { lens: Lens; lang: Lang; club: Club; player: string | null; metric: Metric; brand: Brand }
export const DEFAULT_PROFILE: Profile = { lens: 'fan', lang: 'en', club: 'neutral', player: null, metric: 'pressure', brand: 'tacticai' }

/** The /overlays query of a profile: metric only with one_metric, brand only with broadcast. */
export const queryOf = (p: Profile): OverlayQuery => ({
  lens: p.lens, lang: p.lang, club: p.club, player: p.player,
  metric: p.lens === 'one_metric' ? p.metric : null, brand: p.lens === 'broadcast' ? p.brand : null,
})

export const LENS_LABEL: Record<Lens, string> = { analyst: 'Analyst', fan: 'Fan', first_match: 'First match', broadcast: 'Broadcast', one_metric: 'One metric' }
const LENSES = (Object.keys(LENS_LABEL) as Lens[]).map((value) => ({ value, label: LENS_LABEL[value] }))
const LANGS: { value: Lang; label: string }[] = [{ value: 'en', label: 'EN' }, { value: 'es', label: 'ES' }]
const METRICS: { value: Metric; label: string }[] = [
  { value: 'pressure', label: 'Pressure' }, { value: 'xg', label: 'xG' }, { value: 'possession', label: 'Possession' }, { value: 'goals_added', label: 'Goals added' },
]
const BRANDS: { value: Brand; label: string }[] = [{ value: 'tacticai', label: 'tacticAI' }, { value: 'bka-tv', label: 'BKA TV' }]

export function Segmented<T extends string>({ name, value, options, onChange, ring, groupRef }: {
  name: string; value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; ring?: boolean; groupRef?: React.Ref<HTMLDivElement>
}) {
  return (
    <div ref={groupRef} role="radiogroup" aria-label={name} tabIndex={-1} className={cn('inline-flex rounded-lg border p-0.5', ring && 'ring-2 ring-primary')}>
      {options.map((o) => (
        <button
          key={o.value} type="button" role="radio" aria-checked={o.value === value} onClick={() => onChange(o.value)}
          className={cn('h-8 rounded-md px-3 text-sm font-medium transition-colors', o.value === value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export const ClubSegmented = ({ value, onChange, clubs }: { value: Club; onChange: (c: Club) => void; clubs: Record<'home' | 'away', string> }) => (
  <Segmented
    name="My club" value={value} onChange={onChange}
    options={[{ value: 'neutral', label: 'Neutral' }, { value: 'home', label: clubs.home }, { value: 'away', label: clubs.away }]}
  />
)

/** Lens, language, My Club, Player Focus, the metric (one_metric) and the brand (broadcast). Each change refetches /overlays (done by the parent). */
export function ProfileBar({ profile, onChange, clubs, teamNames, roster, spotlightLens }: {
  profile: Profile; onChange: (p: Profile) => void; clubs: Record<'home' | 'away', string>
  teamNames: Record<'home' | 'away', string>; roster: RosterPlayer[]; spotlightLens: boolean
}) {
  const lensRef = useRef<HTMLDivElement>(null)
  useEffect(() => { if (spotlightLens) lensRef.current?.focus() }, [spotlightLens])
  const set = <K extends keyof Profile>(k: K) => (v: Profile[K]) => onChange({ ...profile, [k]: v })
  const field = 'flex items-center gap-2 text-xs text-muted-foreground'
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2" aria-label="Viewer profile">
      <div className={field}>Lens <Segmented name="Lens" value={profile.lens} options={LENSES} onChange={set('lens')} ring={spotlightLens} groupRef={lensRef} /></div>
      {profile.lens === 'one_metric' && (
        <div className={field}>Metric <Segmented name="Metric" value={profile.metric} options={METRICS} onChange={set('metric')} /></div>
      )}
      {profile.lens === 'broadcast' && (
        <div className={field}>Brand <Segmented name="Brand" value={profile.brand} options={BRANDS} onChange={set('brand')} /></div>
      )}
      <div className={field}>Language <Segmented name="Language" value={profile.lang} options={LANGS} onChange={set('lang')} /></div>
      <div className={field}>My club <ClubSegmented value={profile.club} onChange={set('club')} clubs={clubs} /></div>
      <label className={field}>
        Player focus
        <select
          aria-label="Player focus" value={profile.player ?? ''} onChange={(e) => set('player')(e.target.value || null)}
          className="h-9 rounded-lg border bg-background px-2 text-sm text-foreground"
        >
          <option value="">None</option>
          {(['home', 'away'] as const).map((side) => (
            <optgroup key={side} label={teamNames[side]}>
              {roster.filter((p) => p.team === side).map((p) => <option key={p.player_id} value={p.player_id}>#{p.number} {p.name} ({p.role})</option>)}
            </optgroup>
          ))}
        </select>
      </label>
    </div>
  )
}
