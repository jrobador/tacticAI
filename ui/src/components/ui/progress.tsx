import * as ProgressPrimitive from '@radix-ui/react-progress'
import { cn } from '@/lib/utils'

/** value 0..100, or null for an indeterminate bar. */
export function Progress({ value, className, label }: { value: number | null; className?: string; label: string }) {
  return (
    <ProgressPrimitive.Root className={cn('relative h-3 w-full overflow-hidden rounded-full bg-muted', className)} value={value} aria-label={label}>
      <ProgressPrimitive.Indicator
        className={cn('h-full bg-primary transition-all duration-300', value === null && 'w-1/3 animate-pulse')}
        style={value === null ? undefined : { width: `${value}%` }}
      />
    </ProgressPrimitive.Root>
  )
}
