import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { listMatches } from '@/api/client'
import type { MatchSummary } from '@/api/types'
import { go } from '@/lib/nav'
import { Lenses } from '@/screens/Lenses'
import { Watch } from '@/screens/Watch'

/** The match the app opens on: the featured one, else the most recent (ids start with a timestamp). */
const pickMatch = (ms: MatchSummary[]) =>
  ms.find((m) => m.featured) ?? [...ms].sort((a, b) => b.match_id.localeCompare(a.match_id))[0]

/** Opens Watch (or Three lenses) on the featured match; with no matches at all it goes to Ask for a play. */
export function WatchEntry({ screen }: { screen: 'watch' | 'lenses' }) {
  const [id, setId] = useState<string | null>(null)
  useEffect(() => {
    listMatches()
      .then((ms) => { const m = pickMatch(ms); if (m) setId(m.match_id); else go('/ask') })
      .catch(() => go('/ask'))
  }, [])
  if (!id) return <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Opening the match...</p>
  return screen === 'lenses' ? <Lenses key={id} matchId={id} /> : <Watch key={id} matchId={id} />
}
