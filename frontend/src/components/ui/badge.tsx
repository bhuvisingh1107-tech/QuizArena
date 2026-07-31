import { cva, type VariantProps } from 'class-variance-authority'
import * as React from 'react'

import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-[var(--primary)]/15 text-[var(--primary)]',
        secondary: 'border-transparent bg-[var(--secondary)] text-[var(--muted-foreground)]',
        outline: 'border-[var(--border)] text-[var(--foreground)]',
        success: 'border-transparent bg-[var(--color-success)]/15 text-[var(--color-success)]',
        warning: 'border-transparent bg-[var(--warning)]/15 text-[var(--warning)]',
        danger: 'border-transparent bg-[var(--destructive)]/15 text-[var(--destructive)]',
        accent: 'border-transparent bg-[var(--accent)]/15 text-[var(--accent)]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { badgeVariants }
