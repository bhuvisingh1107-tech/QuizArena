import type { ReactNode } from 'react'

import { ConnectionBanner } from '@/components/participant/ConnectionBanner'
import { cn } from '@/lib/utils'
import type { WsConnectionStatus } from '@/hooks/participantLiveReducer'

interface ParticipantShellProps {
  children: ReactNode
  connectionStatus?: WsConnectionStatus
  /** When false, hide the connection banner (join / pre-session screens). */
  showConnectionBanner?: boolean
  isOffline?: boolean
  lastError?: string | null
  onRetryConnection?: () => void
  subtitle?: string
  footer?: ReactNode
  className?: string
  /**
   * Wider content rail for layouts that need side panels (e.g. quiz + leaderboard).
   * Defaults to the compact phone-first `max-w-lg` shell.
   */
  wide?: boolean
}

export function ParticipantShell({
  children,
  connectionStatus = 'disconnected',
  showConnectionBanner = true,
  isOffline = false,
  lastError = null,
  onRetryConnection,
  subtitle,
  footer,
  className,
  wide = false,
}: ParticipantShellProps) {
  const rail = wide ? 'max-w-6xl' : 'max-w-lg'

  return (
    <div className="relative flex min-h-svh flex-col">
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-20 top-0 h-64 w-64 rounded-full bg-[var(--primary)]/10 blur-3xl" />
        <div className="absolute -right-16 bottom-24 h-72 w-72 rounded-full bg-[var(--accent)]/8 blur-3xl" />
      </div>

      <header className="relative z-10 border-b border-[var(--border)]/60 bg-[var(--background)]/80 px-4 py-4 backdrop-blur">
        <div className={cn('mx-auto flex items-center justify-between gap-3', rail)}>
          <div>
            <p className="font-display text-2xl font-extrabold tracking-tight text-[var(--heading)]">
              Quiz<span className="text-[var(--primary)]">Arena</span>
            </p>
            {subtitle ? (
              <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">{subtitle}</p>
            ) : null}
          </div>
        </div>
      </header>

      {showConnectionBanner ? (
        <ConnectionBanner
          connectionStatus={connectionStatus}
          isOffline={isOffline}
          errorMessage={lastError}
          onRetry={onRetryConnection}
        />
      ) : null}

      <main
        className={cn(
          'relative z-10 mx-auto flex w-full flex-1 flex-col px-4 py-6',
          rail,
          className,
        )}
      >
        {children}
      </main>

      {footer ? (
        <footer className="relative z-10 border-t border-[var(--border)]/60 bg-[var(--background)]/90 px-4 py-4 pb-[calc(1rem+env(safe-area-inset-bottom))] backdrop-blur">
          <div className={cn('mx-auto', rail)}>{footer}</div>
        </footer>
      ) : null}
    </div>
  )
}
