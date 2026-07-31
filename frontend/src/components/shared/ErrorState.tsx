import { AlertTriangle } from 'lucide-react'
import type { ReactNode } from 'react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ErrorStateProps {
  title?: string
  message?: string
  onRetry?: () => void
  action?: ReactNode
  className?: string
}

export function ErrorState({
  title = 'Something went wrong',
  message = 'An unexpected error occurred. Please try again.',
  onRetry,
  action,
  className,
}: ErrorStateProps) {
  return (
    <Alert variant="destructive" className={cn('max-w-xl', className)}>
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="mt-2 space-y-3">
        <p>{message}</p>
        {onRetry || action ? (
          <div className="flex gap-2">
            {onRetry ? (
              <Button type="button" size="sm" variant="outline" onClick={onRetry}>
                Try again
              </Button>
            ) : null}
            {action}
          </div>
        ) : null}
      </AlertDescription>
    </Alert>
  )
}
