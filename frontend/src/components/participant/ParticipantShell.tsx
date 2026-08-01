import type { ReactNode } from 'react'

import { ConnectionBanner } from '@/components/participant/ConnectionBanner'
import { cn } from '@/lib/utils'
import type { WsConnectionStatus } from '@/hooks/participantLiveReducer'

interface ParticipantShellProps {
  children: ReactNode
  connectionStatus?: WsConnectionStatus
  isOffline?: boolean
  subtitle?: string
  footer?: ReactNode
  className?: string
}

export function ParticipantShell({
  children,
  connectionStatus = 'disconnected',
  isOffline = false,
  subtitle,
  footer,
  className,
}: ParticipantShellProps) {
  return (
    <div className="relative flex min-h-svh flex-col">
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-20 top-0 h-64 w-64 rounded-full bg-[var(--primary)]/10 blur-3xl" />
        <div className="absolute -right-16 bottom-24 h-72 w-72 rounded-full bg-[var(--accent)]/8 blur-3xl" />
      </div>

      <header className="relative z-10 border-b border-[var(--border)]/60 bg-[var(--background)]/80 px-4 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-lg items-center justify-between gap-3">
          <div>
            <p className="font-display text-2xl font-extrabold tracking-tight text-[#f0f4fa]">
              Quiz<span className="text-[var(--primary)]">Arena</span>
            </p>
            {subtitle ? (
              <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">{subtitle}</p>
            ) : null}
          </div>
        </div>
      </header>

      <ConnectionBanner connectionStatus={connectionStatus} isOffline={isOffline} />

      <main
        className={cn(
          'relative z-10 mx-auto flex w-full max-w-lg flex-1 flex-col px-4 py-6',
          className,
        )}
      >
        {children}
      </main>

      {footer ? (
        <footer className="relative z-10 border-t border-[var(--border)]/60 bg-[var(--background)]/90 px-4 py-4 pb-[calc(1rem+env(safe-area-inset-bottom))] backdrop-blur">
          <div className="mx-auto max-w-lg">{footer}</div>
        </footer>
      ) : null}
    </div>
  )
}
