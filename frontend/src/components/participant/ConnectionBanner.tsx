import { WifiOff } from 'lucide-react'

import type { WsConnectionStatus } from '@/hooks/participantLiveReducer'
import { cn } from '@/lib/utils'

interface ConnectionBannerProps {
  connectionStatus: WsConnectionStatus
  isOffline?: boolean
}

export function ConnectionBanner({
  connectionStatus,
  isOffline = false,
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

  if (connectionStatus === 'connected') return null

  const message =
    connectionStatus === 'connecting'
      ? 'Connecting…'
      : connectionStatus === 'error'
        ? 'Connection error — retrying…'
        : 'Disconnected — reconnecting…'

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'relative z-20 px-4 py-2 text-center text-sm',
        connectionStatus === 'connecting'
          ? 'bg-[var(--accent)]/20 text-[var(--accent)]'
          : 'bg-[var(--color-warning)]/15 text-[var(--color-warning)]',
      )}
    >
      {message}
    </div>
  )
}
