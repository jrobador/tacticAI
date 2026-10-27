import { useState } from 'react'
import { matchFileUrl, MOCK, videoUrl } from '@/api/client'

const still = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

/** Looping engine video behind the New match hero, darkened and blurred so the text stays readable. Remove this component to drop it. */
export function HeroVideo({ matchId }: { matchId: string | null }) {
  const [bad, setBad] = useState(false)
  const src = matchId && !MOCK ? videoUrl(matchId) : null
  return (
    <div aria-hidden className="absolute inset-y-0 right-0 left-[calc(-1*var(--nav-w,0px))] -z-10 overflow-hidden bg-background transition-[left] duration-300 ease-out motion-reduce:transition-none">
      {src && !bad && (still
        ? <img src={matchFileUrl(matchId!, 'render/thumb.jpg')} alt="" onError={() => setBad(true)} className="size-full scale-110 object-cover blur-[5px]" />
        : <video src={src} autoPlay muted loop playsInline preload="auto" onError={() => setBad(true)} className="size-full scale-110 object-cover blur-[5px]" />)}
      <div className="absolute inset-0 bg-background/50" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_50%_50%,color-mix(in_oklab,var(--background)_55%,transparent),transparent)]" />
      <div className="absolute inset-x-0 bottom-0 h-56 bg-gradient-to-t from-background via-background/70 to-transparent" />
    </div>
  )
}
