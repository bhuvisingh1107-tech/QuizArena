import { WifiOff } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { WsConnectionStatus } from '@/hooks/participantLiveReducer'
import { cn } from '@/lib/utils'

interface ConnectionBannerProps {
  connectionStatus: WsConnectionStatus
  isOffline?: boolean
  onRetry?: () => void
  errorMessage?: string | null
}

export function ConnectionBanner({
  connectionStatus,
  isOffline = false,
  onRetry,
  errorMessage,
}: ConnectionBannerProps) {
  if (isOffline) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="relative z-20 flex items-center justify-center gap-2 bg-[var(--destructive)]/90 px-4 py-2 text-sm text-white"
      >
        <WifiOff className="h-4 w-4" aria-hidden />
        You are offline. Reconnect to submit answers.
      </div>
    )
  }

  if (connectionStatus === 'connected' && !errorMessage) return null

  if (connectionStatus === 'connected' && errorMessage) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="relative z-20 flex flex-wrap items-center justify-center gap-2 bg-[var(--color-warning)]/15 px-4 py-2 text-sm text-[var(--color-warning)]"
      >
        <span>{errorMessage}</span>
        {onRetry ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 border-[var(--color-warning)]/40 text-[var(--color-warning)]"
            onClick={onRetry}
          >
            Retry
          </Button>
        ) : null}
      </div>
    )
  }

  const message =
    connectionStatus === 'connecting'
      ? 'Connecting…'
      : connectionStatus === 'error'
        ? errorMessage
          ? `${errorMessage}`
          : 'Connection error'
        : 'Disconnected'

  const showRetry =
    Boolean(onRetry) &&
    (connectionStatus === 'error' || connectionStatus === 'disconnected')

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'relative z-20 flex flex-wrap items-center justify-center gap-2 px-4 py-2 text-center text-sm',
        connectionStatus === 'connecting'
          ? 'bg-[var(--accent)]/20 text-[var(--accent)]'
          : 'bg-[var(--color-warning)]/15 text-[var(--color-warning)]',
      )}
    >
      <span>
        {message}
        {connectionStatus === 'connecting' || !showRetry ? null : ' — tap Retry to reconnect'}
      </span>
      {showRetry ? (
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 border-[var(--color-warning)]/40 text-[var(--color-warning)]"
          onClick={onRetry}
        >
          Retry
        </Button>
      ) : null}
    </div>
  )
}
