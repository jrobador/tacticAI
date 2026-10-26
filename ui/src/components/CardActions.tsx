import { useState } from 'react'
import { Download, ImageDown } from 'lucide-react'
import { clipUrl } from '@/api/client'
import type { ClipManifest, Insight, MatchBundle, Overlay } from '@/api/types'
import { Button } from '@/components/ui/button'
import { downloadCard } from '@/lib/card'
import { minute } from '@/lib/format'

/** Export the moment as a 9:16 image (built in the browser) and, when the insight is in the clip manifest, download its clip. */
export function CardActions({ matchId, overlay, insight, bundle, manifest }: {
  matchId: string; overlay: Overlay; insight: Insight | undefined; bundle: MatchBundle; manifest: ClipManifest | null
}) {
  const [error, setError] = useState<string | null>(null)
  const hasClip = manifest?.clips.some((c) => c.insight_id === overlay.insight_id)
  const main = insight?.players[insight.players.length - 1]
  const p = main ? bundle.roster.players.find((r) => r.player_id === main) : undefined
  const rating = main ? (bundle.players.find((r) => r.player_id === main)?.rating.value ?? null) : null
  const make = () => {
    setError(null)
    downloadCard({
      filename: `tacticai-${matchId}-${overlay.insight_id}`,
      kicker: `${insight ? `Minute ${minute(insight.clock_s)} · ` : ''}${insight ? bundle.meta.teams[insight.team].name : ''}`,
      title: overlay.title, text: overlay.text,
      player: p ? `#${p.number} ${p.name}` : null, rating,
    }).catch((e: Error) => setError(e.message))
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button size="sm" variant="outline" onClick={make}><ImageDown /> 9:16 card</Button>
      {hasClip && (
        <Button size="sm" variant="outline" asChild>
          <a href={clipUrl(matchId, overlay.insight_id)} download={`${overlay.insight_id}.mp4`}><Download /> Download clip</a>
        </Button>
      )}
      {error && <span role="alert" className="text-xs text-muted-foreground">{error}</span>}
    </div>
  )
}
