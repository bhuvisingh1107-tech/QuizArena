import { Button } from '@/components/ui/button'
import type { WsConnectionStatus } from '@/hooks/displayLiveReducer'
import { cn } from '@/lib/utils'

interface DisplayConnectionBadgeProps {
  status: WsConnectionStatus
  onRetry?: () => void
  className?: string
}

const LABELS: Record<WsConnectionStatus, string> = {
  connecting: 'Connecting',
  connected: 'Live',
  disconnected: 'Reconnecting',
  error: 'Connection issue',
}

export function DisplayConnectionBadge({
  status,
  onRetry,
  className,
}: DisplayConnectionBadgeProps) {
  const showRetry =
    Boolean(onRetry) && (status === 'disconnected' || status === 'error')

  return (
    <span
      role="status"
      aria-live="polite"
      className={cn(
        'inline-flex items-center gap-2 rounded-md border px-3 py-1.5 font-sans text-sm font-medium tracking-wide',
        status === 'connected' &&
          'border-[var(--color-success)]/40 bg-[var(--color-success)]/15 text-[var(--color-success)]',
        status === 'connecting' &&
          'border-[var(--accent)]/40 bg-[var(--accent)]/15 text-[var(--accent)]',
        (status === 'disconnected' || status === 'error') &&
          'border-[var(--color-warning)]/40 bg-[var(--color-warning)]/15 text-[var(--color-warning)]',
        className,
      )}
    >
      <span
        aria-hidden
        className={cn(
          'h-2 w-2 rounded-full',
          status === 'connected' && 'bg-[var(--color-success)]',
          status === 'connecting' && 'animate-pulse bg-[var(--accent)]',
          (status === 'disconnected' || status === 'error') &&
            'animate-pulse bg-[var(--color-warning)]',
        )}
      />
      {LABELS[status]}
      {showRetry ? (
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-6 px-2 text-xs text-inherit hover:bg-transparent hover:underline"
          onClick={onRetry}
        >
          Retry
        </Button>
      ) : null}
    </span>
  )
}
