// Fan mode views of personalize/fan/<lang>_<club>.json: the moment card on the video and the story of the match in the side panel.
// The texts come from the Supporter agent (judged) or a fallback line of data; the page only places them in time and colours them by
// what the reader feels (the moment's stance, decided by code for the reader's club).
import { useState } from 'react'
import type { EnrichedEvent, MatchMeta } from '@/api/types'
import { CREST } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { FanAward, FanMoment, FanStance, FanView } from './data'

const ICON: Record<FanMoment['kind'], string> = { goal: '⚽', miss: '😱', save: '🧤', mistake: '⚠️', pinned: '🔒', turn: '🔄', move: '🎶', pass: '🎯', carry: '🏃', tackle: '🛡️', sprint: '⚡' }
const AWARD_ICON: Record<FanAward['award'], string> = { engine: '🔋', fastest: '⚡', sprinter: '🏃', playmaker: '🎩', rocket: '🚀' }

/** Good news, bad news or neither, for the reader. */
type Tone = 'up' | 'down' | 'even'
const TONE: Record<FanStance, Tone> = {
  celebrate: 'up', relief: 'up', gloat: 'up', taunt: 'up', dominate: 'up', uplift: 'up', show_off: 'up', admire: 'up', enjoy: 'up', roar: 'up',
  suffer: 'down', anguish: 'down', frustration: 'down', blame_ours: 'down', scare: 'down', under_siege: 'down', worry: 'down', humiliation: 'down', fear: 'down',
  wary: 'down', dismay: 'down',
  thrill: 'even',
}
const CARD: Record<Tone, string> = {
  up: 'border-primary bg-[rgba(12,23,42,.94)]',
  down: 'border-red-500/70 bg-[rgba(38,12,18,.95)]',
  even: 'border-foreground/15 bg-[rgba(12,23,42,.94)]',
}

/** The moment on screen, if any; `card_s` (from the view) is how long a card stays after its moment. */
export function currentMoment(view: FanView | null, time: number): FanMoment | undefined {
  return view?.moments.filter((x) => x.tier === 'moment' && x.t_s <= time && time - x.t_s < view.card_s).at(-1)
}

/** Every fan notification on the video, stacked at the bottom left: the live feed, then the moment card. */
export function FanOverlay({ view, time, player }: { view: FanView | null; time: number; player: string | null }) {
  return (
    <div className="pointer-events-none absolute bottom-4 left-4 z-[4] flex w-[min(460px,52%)] flex-col gap-1.5">
      <FanFeed view={view} time={time} player={player} />
      <FanCard view={view} time={time} player={player} />
    </div>
  )
}

/** The live feed: the reactions of the last `card_s` seconds, at most three, the newest at the bottom (next to the card), like a chat. */
function FanFeed({ view, time, player }: { view: FanView | null; time: number; player: string | null }) {
  if (!view) return null
  const live = view.moments.filter((x) => x.tier === 'reaction' && x.t_s <= time && time - x.t_s < view.card_s).slice(-3)
  if (!live.length) return null
  return (
    <div className="flex flex-col gap-1.5">
      {live.map((m, i) => {
        const tone = TONE[m.stance]
        const line = (player && view.player_lines[player]?.[m.fact_id]) || m.text
        return (
          <div key={m.fact_id} className={cn('fade-in flex w-[min(380px,85%)] items-start gap-2 rounded-xl border px-3 py-2 backdrop-blur-sm', CARD[tone], i < live.length - 1 && 'opacity-70')}>
            <img src={CREST[m.team]} alt="" className="mt-0.5 size-4 shrink-0 object-contain" />
            <span className="flex min-w-0 flex-col">
              <span className="text-[13px] font-semibold leading-snug">{ICON[m.kind]} {m.title}</span>
              <span className="text-[12.5px] leading-snug text-foreground/85">{line}</span>
            </span>
          </div>
        )
      })}
    </div>
  )
}

function FanCard({ view, time, player }: { view: FanView | null; time: number; player: string | null }) {
  const m = currentMoment(view, time)
  if (!m || !view) return null
  // A big goal for the reader takes the whole lime card; their goal against us is the dark red one.
  const tone = TONE[m.stance]
  const party = m.kind === 'goal' && tone === 'up'
  const mine = player ? view.player_lines[player]?.[m.fact_id] : undefined
  return (
    <div key={m.fact_id} className={cn('fade-in flex flex-col gap-1.5 rounded-2xl border px-4 py-3 backdrop-blur-sm',
      party ? 'border-primary bg-primary text-primary-foreground' : CARD[tone])}>
      <span className="flex items-center gap-2">
        {mine ? <img src={`/players/${player}.png`} alt="" className="size-9 rounded-md object-cover object-top" /> : <img src={CREST[m.team]} alt="" className="size-6 object-contain" />}
        <span className={cn('font-mono text-[12px] font-semibold', party ? 'text-primary-foreground/70' : tone === 'down' ? 'text-red-300' : 'text-primary')}>{m.minute}'</span>
      </span>
      <span className={cn('font-heading font-bold leading-tight', m.kind === 'goal' ? 'text-[26px]' : 'text-[20px]')}>{ICON[m.kind]} {m.title}</span>
      <span className={cn('text-[15px] font-medium leading-snug', party ? 'text-primary-foreground/85' : 'text-foreground/90')}>{mine ?? m.text}</span>
    </div>
  )
}

interface StoryProps { view: FanView | null; events: EnrichedEvent[]; teams: MatchMeta['teams']; time: number; final: boolean; player: string | null; playerName: string | null }

/** The score so far is plain counting; the verdict, awards and ratings are the agent's, shown at full time like a post-match show. */
export function FanStory({ view, events, teams, time, final, player, playerName }: StoryProps) {
  const [all, setAll] = useState(false)
  const es = view?.lang === 'es'
  if (!view) return <span className="text-[13px] text-dim">{es ? 'Este partido todavía no tiene la vista de hincha.' : 'This match has no fan view yet: regenerate it to get one.'}</span>
  const goals = (s: 'home' | 'away') => events.filter((e) => e.type === 'goal' && e.team === s && e.t_s <= time).length
  const seen = view.moments.filter((m) => m.t_s <= time).reverse()
  const ratings = all ? view.ratings : view.ratings.slice(0, 5)
  const mine = player ? view.player_lines[player] ?? {} : {}
  const myLines = seen.filter((m) => mine[m.fact_id])
  const myRating = player ? view.ratings.find((r) => r.player_id === player) : undefined
  const myAwards = player ? view.awards.filter((a) => a.player_id === player) : []
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5 rounded-xl border border-primary/40 bg-[#0f192b] px-3.5 py-3">
        <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[.06em] text-primary">{final ? (es ? 'Final del partido' : 'Full time') : (es ? 'Hasta ahora' : 'So far')}</span>
        {final ? (
          <>
            <span className="font-heading text-[18px] font-semibold leading-tight">{view.verdict.headline}</span>
            <span className="text-[14px] leading-snug">{view.verdict.text}</span>
          </>
        ) : (
          <span className="flex items-center gap-2 font-heading text-[18px] font-semibold">
            <img src={CREST.home} alt="" className="size-5 object-contain" />{teams.home.short} {goals('home')}–{goals('away')} {teams.away.short}<img src={CREST.away} alt="" className="size-5 object-contain" />
          </span>
        )}
      </div>

      {player && (
        <div className="flex flex-col gap-1.5 rounded-xl border border-foreground/20 bg-[#142036] px-3.5 py-3">
          <span className="flex items-center gap-2.5">
            <img src={`/players/${player}.png`} alt="" className="size-10 flex-none rounded-md object-cover object-top" />
            <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[.06em] text-primary">{es ? 'Tu jugador' : 'Your player'} · {playerName}</span>
          </span>
          {myLines.length === 0 && <span className="text-[13px] text-dim">{es ? 'Todavía no apareció en una jugada clave.' : 'Not in a key moment yet.'}</span>}
          {myLines.map((m) => (
            <span key={m.fact_id} className="text-[13.5px] leading-snug"><span className="font-mono text-[12px] font-semibold text-primary">{m.minute}'</span> {ICON[m.kind]} {mine[m.fact_id]}</span>
          ))}
          {final && myRating && <span className="text-[13px] leading-snug text-muted-foreground"><span className="font-semibold text-foreground">{myRating.label}</span> · {myRating.line}</span>}
          {final && myAwards.map((a) => <span key={a.award} className="text-[13px] font-semibold text-primary">{AWARD_ICON[a.award]} {a.title} · {a.stat}</span>)}
        </div>
      )}

      {/* At full time the moments are behind us: the panel is the verdict, the awards and the ratings. */}
      {!final && seen.length === 0 && <span className="text-[13px] text-dim">{es ? 'Todavía no pasó nada. Acá va a aparecer la historia del partido.' : 'Nothing yet. The story of the match shows up here as it happens.'}</span>}
      {!final && seen.map((m, i) => {
        const tone = TONE[m.stance]
        return (
          <div key={m.fact_id} className={cn('flex flex-col gap-1 rounded-xl border px-3.5 py-2.5',
            tone === 'down' ? 'border-red-500/40 bg-[#1d121a]' : i === 0 ? 'border-foreground/25 bg-[#142036]' : 'border-foreground/10 bg-[#0f192b]',
            player && !m.players.includes(player) && 'opacity-55')}>
            <span className="flex items-center gap-2 text-[12px]">
              <img src={CREST[m.team]} alt="" className="size-4 object-contain" />
              <span className={cn('font-mono font-semibold', tone === 'down' ? 'text-red-300' : 'text-primary')}>{m.minute}'</span>
            </span>
            <span className="text-[15px] font-semibold leading-snug">{ICON[m.kind]} {m.title}</span>
            <span className="text-[13.5px] leading-snug text-foreground/85">{m.text}</span>
          </div>
        )
      })}

      {final && view.awards.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-semibold">{es ? 'Los premios de la tribuna' : 'Terrace awards'}</span>
          <div className="grid grid-cols-2 gap-1.5">
            {view.awards.map((a) => (
              <div key={a.award} className={cn('flex flex-col gap-0.5 rounded-xl border bg-[#0f192b] px-3 py-2', a.player_id === player ? 'border-primary' : 'border-foreground/10')}>
                <span className="text-[11.5px] font-semibold uppercase tracking-[.04em] text-primary">{AWARD_ICON[a.award]} {a.title}</span>
                <span className="flex items-center gap-1.5 text-[14px] font-semibold"><img src={CREST[a.team]} alt="" className="size-4 object-contain" />{a.name}</span>
                <span className="font-heading text-[15px] font-bold text-primary">{a.stat}</span>
                {a.line && <span className="text-[12px] leading-snug text-muted-foreground">{a.line}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {final && view.ratings.length > 0 && (
        <div className="flex flex-col">
          <span className="pb-1 text-sm font-semibold">{es ? 'Uno por uno' : 'Player ratings'}</span>
          {ratings.map((r) => (
            <div key={r.player_id} className="grid grid-cols-[18px_minmax(0,1fr)_auto] items-baseline gap-x-2 border-t border-foreground/[.06] py-1.5" title={teams[r.team].name}>
              <img src={CREST[r.team]} alt="" className="size-4 self-center object-contain" />
              <span className="flex min-w-0 flex-col">
                <span className="text-[13.5px] font-semibold">{r.name}</span>
                <span className="text-[12px] leading-snug text-muted-foreground">{r.line}</span>
              </span>
              <span className={cn('text-[12.5px] font-semibold', r.band >= 2 ? 'text-primary' : r.band === 1 ? 'text-foreground' : 'text-muted-foreground')}>{r.label}</span>
            </div>
          ))}
          {view.ratings.length > 5 && (
            <button type="button" onClick={() => setAll((v) => !v)} className="self-start pt-1 text-[12.5px] font-semibold text-primary hover:text-foreground">{all ? (es ? 'Ver menos' : 'Show fewer') : (es ? `Ver los ${view.ratings.length}` : `Show all ${view.ratings.length}`)}</button>
          )}
        </div>
      )}
    </div>
  )
}
