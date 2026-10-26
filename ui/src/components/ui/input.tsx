import * as React from 'react'
import { cn } from '@/lib/utils'

const field =
  'w-full rounded-lg border bg-background px-3 text-sm placeholder:text-muted-foreground focus-visible:border-primary disabled:opacity-50'
export const Input = ({ className, ...p }: React.InputHTMLAttributes<HTMLInputElement>) => (
  <input className={cn(field, 'h-9', className)} {...p} />
)
export const Textarea = ({ className, ...p }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <textarea className={cn(field, 'min-h-20 py-2', className)} {...p} />
)
