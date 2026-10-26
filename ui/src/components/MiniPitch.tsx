import type { ReactNode } from 'react'
import type { PitchPlayer, Side } from '@/api/types'
import { cn } from '@/lib/utils'

export interface PitchData {
  home: PitchPlayer[]
  away: PitchPlayer[]
  ball: { x: number; y: number } | null // null: the engine places it, nothing to draw
}

const L = 108.8
const W = 70.2

/** Absolute contract coordinates (metres): home attacks +x, +y is the right touchline seen from the home goal (screen down). */
export function MiniPitch({ data, className, owner, children }: { data: PitchData | null; className?: string; owner?: Side | null; children?: ReactNode }) {
  const line = { stroke: 'var(--offwhite)', strokeOpacity: 0.35, strokeWidth: 0.4, fill: 'none' } as const
  const box = (sign: 1 | -1, depth: number, half: number) => (
    <rect x={sign > 0 ? L / 2 - depth : -L / 2} y={-half} width={depth} height={half * 2} {...line} />
  )
  return (
    <svg viewBox={`${-L / 2 - 2} ${-W / 2 - 2} ${L + 4} ${W + 4}`} className={cn('w-full rounded-md bg-muted', className)} role="img"
      aria-label={owner ? `Starting positions, ${owner === 'home' ? 'home' : 'away'} team attacking` : 'Starting positions'}>
      {children}
      <rect x={-L / 2} y={-W / 2} width={L} height={W} {...line} />
      <line x1={0} y1={-W / 2} x2={0} y2={W / 2} {...line} />
      <circle cx={0} cy={0} r={9.15} {...line} />
      {box(1, 16.5, 20.16)}
      {box(-1, 16.5, 20.16)}
      {box(1, 5.5, 9.16)}
      {box(-1, 5.5, 9.16)}
      {data && (
        <>
          {data.home.map((p, i) => (
            <circle key={`h${i}`} cx={p.x} cy={p.y} r={p.role === 'GK' ? 2.1 : 1.8} fill="var(--lime)" stroke="var(--navy)" strokeWidth={0.4}>
              <title>{`Home ${p.role}`}</title>
            </circle>
          ))}
          {data.away.map((p, i) => (
            <circle key={`a${i}`} cx={p.x} cy={p.y} r={p.role === 'GK' ? 2.1 : 1.8} fill="var(--offwhite)" stroke="var(--navy)" strokeWidth={0.4}>
              <title>{`Away ${p.role}`}</title>
            </circle>
          ))}
          {data.ball && (
            <circle cx={data.ball.x} cy={data.ball.y} r={1.3} fill="var(--navy)" stroke="var(--offwhite)" strokeWidth={0.7}>
              <title>Ball</title>
            </circle>
          )}
        </>
      )}
    </svg>
  )
}

/**
 * Engine-unit custom positions (x in -1..1, y in -0.42..0.42) to contract metres, for recipes without a template.
 * Positions are team-relative: the away team is the point reflection of the home one (both axes), as in recipe_config.py.
 * A missing ball follows the backend: 1 m in front of the owner's most advanced outfield player; with no owner it stays
 * unset (the engine decides), so nothing is drawn.
 */
export function fromEngine(positions: Record<Side, [number, number, string][]>, ball: [number, number] | null, owner: Side | null): PitchData {
  const conv = (ps: [number, number, string][], sign: 1 | -1) => ps.map(([x, y, role]) => ({ x: sign * x * 54.4, y: sign * y * 83.6, role }))
  let b = ball
  if (!b && owner) {
    const out = positions[owner].filter((p) => p[2] !== 'GK')
    if (out.length) {
      const [x, y] = out.reduce((m, p) => (p[0] > m[0] ? p : m))
      const sign = owner === 'home' ? 1 : -1
      b = [sign * (x + 1 / 54.4), sign * y]
    }
  }
  return { home: conv(positions.home, 1), away: conv(positions.away, -1), ball: b ? { x: b[0] * 54.4, y: b[1] * 83.6 } : null }
}
