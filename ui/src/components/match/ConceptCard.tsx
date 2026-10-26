import { useEffect } from 'react'
import { CONCEPTS, conceptHere, type Env } from './concepts'
import { MODEL_NOTE, modelText } from './modelInfo'
import type { ConceptKey } from './model'

const W = 344

/** Where the card sits: under the term when there is room, else above it; kept inside the window (prototype openConcept). */
export interface ConceptPos { key: ConceptKey; x: number; top: number | null; bottom: number | null; maxH: number }
export function placeConcept(key: ConceptKey, el: HTMLElement | null): ConceptPos {
  const r = el?.getBoundingClientRect() ?? { left: 24, top: 24, bottom: 24 }
  const H = window.innerHeight
  const below = H - r.bottom - 20 >= r.top - 20
  const room = below ? H - r.bottom - 20 : r.top - 20
  return {
    key, x: Math.max(12, Math.min(window.innerWidth - W - 12, r.left - 8)),
    top: below ? r.bottom + 8 : null, bottom: below ? null : H - r.top + 8, maxH: Math.max(160, Math.min(540, room)),
  }
}

const label = 'font-mono text-[10px] font-medium uppercase tracking-[.06em]'

export function ConceptCard({ pos, env, onClose }: { pos: ConceptPos; env: Env; onClose: () => void }) {
  useEffect(() => {
    const on = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [onClose])
  const c = CONCEPTS[pos.key]
  const here = conceptHere(pos.key, env)
  const m = c.model ? modelText(env.models.find((x) => x.id === c.model), c.model) : null
  return (
    <>
      <div className="fixed inset-0 z-[94]" onClick={onClose} />
      <div
        role="dialog" aria-label={c.term}
        className="fade-in fixed z-[95] flex w-[min(344px,calc(100vw-24px))] flex-col gap-3 overflow-auto rounded-xl border border-foreground/20 bg-[#18243a] px-[15px] py-3.5 shadow-[0_18px_40px_rgba(0,0,0,.45)]"
        style={{ left: pos.x, top: pos.top ?? 'auto', bottom: pos.bottom ?? 'auto', maxHeight: pos.maxH }}
      >
        <div className="flex items-baseline justify-between gap-2.5">
          <span className="font-heading text-base font-semibold">{c.term}</span>
          <button type="button" aria-label="Close" onClick={onClose} className="text-[13px] font-semibold text-muted-foreground hover:text-foreground">✕</button>
        </div>
        <div className="flex flex-col gap-1">
          <span className={`${label} text-dim`}>What it is</span>
          <span className="text-[13.5px] font-medium leading-[1.45] [text-wrap:pretty]">{c.what(env)}</span>
        </div>
        <div className="flex flex-col gap-[5px]">
          <span className={`${label} text-dim`}>How we compute it</span>
          {c.how(env).map((h, i) => <span key={i} className="text-[12.5px] leading-normal text-[#c9cdd3] [text-wrap:pretty]">{h}</span>)}
        </div>
        <div className="flex flex-col gap-1.5 border-t border-foreground/10 pt-2.5">
          <span className={`${label} text-primary`}>Here</span>
          {here.rows.map((r, i) => (
            <div key={i} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-2.5">
              <span className="text-xs font-medium text-muted-foreground">{r.l}</span>
              <span className="max-w-[190px] text-right font-heading text-[13px] font-semibold">{r.v}</span>
            </div>
          ))}
          {here.note && <span className="text-[11.5px] leading-normal text-dim">{here.note}</span>}
          {m && (
            <div className="flex flex-col gap-[3px] rounded-[9px] border border-foreground/15 bg-[#122036] px-2.5 py-[9px]">
              <span className="flex justify-between gap-2"><span className="text-xs font-semibold">Model card · {m.name}</span><span className="font-mono text-[11px] text-muted-foreground">{m.id}</span></span>
              {(m.trained || m.score) && <span className="text-[11.5px] leading-[1.45] text-muted-foreground">{m.trained} {m.score}</span>}
              <span className="text-[11px] leading-[1.45] text-dim">{MODEL_NOTE}</span>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
