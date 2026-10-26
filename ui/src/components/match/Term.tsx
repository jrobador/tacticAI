import { createContext, useContext, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import type { ConceptKey, OnConcept } from './model'

/** The match page hands `onConcept` down through this context; the default does nothing until the concept card exists. */
export const ConceptContext = createContext<OnConcept>(() => {})
export const useConcept = () => useContext(ConceptContext)

/** A term underlined with dots that opens its concept card. */
export function Term({ k, children, className }: { k: ConceptKey; children: ReactNode; className?: string }) {
  const onConcept = useConcept()
  return (
    <button
      type="button" onClick={(e) => { e.stopPropagation(); onConcept(k, e) }}
      className={cn('cursor-help border-0 bg-transparent p-0 text-left underline decoration-dotted decoration-foreground/45 underline-offset-[3px] hover:text-foreground', className)}
    >
      {children}
    </button>
  )
}

/** The lime tick with "Checked": every number on screen was written by code. */
export function CheckedBadge({ size = 14, className, dark }: { size?: number; className?: string; dark?: boolean }) {
  return (
    <Term k="checked" className={cn('flex items-center gap-[5px] text-[11.5px] font-semibold no-underline', dark ? 'text-background' : 'text-primary', className)}>
      <span
        className={cn('grid place-items-center rounded-full text-[9px] font-bold', dark ? 'bg-background text-primary' : 'bg-primary text-primary-foreground')}
        style={{ width: size, height: size }}
      >✓</span>
      <span className="underline decoration-dotted underline-offset-[3px]">Checked</span>
    </Term>
  )
}
