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

