import { useState } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { go } from '@/lib/nav'

const KEY = 'tacticai.guide.dismissed'
const read = () => { try { return localStorage.getItem(KEY) === '1' } catch { return false } }
const write = () => { try { localStorage.setItem(KEY, '1') } catch { /* private mode: the hint just comes back next visit */ } }

/** Step the guide is on: 1 open an overlay's evidence, 2 switch the lens, 3 try the three lenses. */
export function guideStep(openedEvidence: boolean, switchedLens: boolean): 1 | 2 | 3 {
  return !openedEvidence ? 1 : !switchedLens ? 2 : 3
}

/** Small, dismissable 3-step hint anchored to the real controls. The dismissal is remembered in localStorage. */
export function GuideHint({ step, onShowOverlay }: { step: 1 | 2 | 3; onShowOverlay: () => void }) {
  const [gone, setGone] = useState(read)
  if (gone) return null
  const dismiss = () => { write(); setGone(true) }
  return (
    <aside aria-label="Quick guide" className="fade-in flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-primary/50 bg-card px-4 py-2 text-sm">
      <ol className="flex items-center gap-1.5" aria-label={`Step ${step} of 3`}>
        {[1, 2, 3].map((n) => <li key={n} className={`size-2 rounded-full ${n === step ? 'bg-primary' : n < step ? 'bg-primary/40' : 'bg-muted'}`} />)}
      </ol>
      {step === 1 && <><span>1 of 3 · Click an overlay on the video to open its evidence.</span><Button size="sm" variant="outline" onClick={onShowOverlay}>Jump to the first overlay</Button></>}
      {step === 2 && <span>2 of 3 · Switch the lens above and watch the same moment change its voice.</span>}
      {step === 3 && <><span>3 of 3 · See Analyst, Fan and Broadcast side by side.</span><Button size="sm" onClick={() => go('/lenses')}>Open Three lenses</Button></>}
      <button type="button" onClick={dismiss} aria-label="Dismiss the guide" className="ml-auto rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"><X className="size-4" /></button>
    </aside>
  )
}
