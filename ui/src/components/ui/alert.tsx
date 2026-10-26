import * as React from 'react'
import { cn } from '@/lib/utils'

/** Palette-only alert: state is carried by an icon, a heavier border and text, not by a new hue. */
export function Alert({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div role="alert" className={cn('flex gap-3 rounded-lg border-2 border-foreground/50 bg-muted p-3 text-sm', className)} {...p} />
}
