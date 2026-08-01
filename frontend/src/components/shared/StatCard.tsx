import type { ReactNode } from 'react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface StatCardProps {
  label: string
  value: ReactNode
  description?: string
  icon?: ReactNode
  loading?: boolean
  className?: string
  valueClassName?: string
}

export function StatCard({
  label,
  value,
  description,
  icon,
  loading,
  className,
  valueClassName,
}: StatCardProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader className="pb-2">
        <CardDescription className="flex items-center gap-1.5">
          {icon}
          {label}
        </CardDescription>
        {loading ? (
          <Skeleton className="mt-1 h-9 w-20" />
        ) : (
          <CardTitle className={cn('text-3xl', valueClassName)}>{value}</CardTitle>
        )}
      </CardHeader>
      {description ? (
        <CardContent className="text-xs text-[var(--muted-foreground)]">{description}</CardContent>
      ) : null}
    </Card>
  )
}
