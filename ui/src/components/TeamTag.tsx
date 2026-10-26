import type { Side } from '@/api/types'
import { CREST, DEFAULT_TEAMS } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Crest + name: the only place club identity shows up. */
export function TeamTag({ side, name, short, className }: { side: Side; name?: string; short?: boolean; className?: string }) {
  const n = name ?? (short ? DEFAULT_TEAMS[side].short : DEFAULT_TEAMS[side].name)
  return (
    <span className={cn('inline-flex items-center gap-1.5', className)}>
      <img src={CREST[side]} alt="" className="size-5 object-contain" />
      <span>{n}</span>
    </span>
  )
}
