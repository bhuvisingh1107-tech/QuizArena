import { Maximize, Minimize } from 'lucide-react'
import type { ReactNode } from 'react'
import { useCallback, useEffect, useState } from 'react'

import { DisplayConnectionBadge } from '@/components/display/DisplayConnectionBadge'
import type { WsConnectionStatus } from '@/hooks/displayLiveReducer'
import { cn } from '@/lib/utils'

interface DisplayShellProps {
  children: ReactNode
  quizTitle?: string
  roomCode?: string
  connectionStatus?: WsConnectionStatus
  footer?: ReactNode
  className?: string
}

export function DisplayShell({
  children,
  quizTitle,
  roomCode,
  connectionStatus = 'disconnected',
  footer,
  className,
}: DisplayShellProps) {
  const [isFullscreen, setIsFullscreen] = useState(false)

  useEffect(() => {
    const onChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement))
    }
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  const toggleFullscreen = useCallback(async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen()
      } else {
        await document.documentElement.requestFullscreen()
      }
    } catch {
      // Browser may block without user gesture or policy
    }
  }, [])

  return (
    <div className="relative flex min-h-svh w-full flex-col overflow-hidden bg-[var(--background)]">
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-32 top-0 h-[28rem] w-[28rem] rounded-full bg-[var(--primary)]/12 blur-3xl" />
        <div className="absolute -right-24 bottom-0 h-[32rem] w-[32rem] rounded-full bg-[var(--accent)]/10 blur-3xl" />
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage:
              'linear-gradient(rgba(36,48,73,0.9) 1px, transparent 1px), linear-gradient(90deg, rgba(36,48,73,0.9) 1px, transparent 1px)',
            backgroundSize: '64px 64px',
          }}
        />
      </div>

      <header className="relative z-10 border-b border-[var(--border)]/70 bg-[var(--background)]/85 px-6 py-4 backdrop-blur-md lg:px-10 lg:py-5">
        <div className="mx-auto flex w-full max-w-[1600px] items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p
              className="font-display font-extrabold tracking-tight text-[#f0f4fa]"
              style={{ fontSize: 'clamp(1.25rem, 2.5vw, 1.875rem)' }}
            >
              Quiz<span className="text-[var(--primary)]">Arena</span>
            </p>
            {quizTitle ? (
              <p className="mt-1 truncate font-sans text-base text-[var(--muted-foreground)] lg:text-lg">
                {quizTitle}
              </p>
            ) : null}
          </div>

          <div className="flex shrink-0 items-center gap-3 lg:gap-5">
            {roomCode ? (
              <div className="text-right">
                <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
                  Room
                </p>
                <p
                  className="font-display font-bold tracking-[0.18em] text-[var(--accent)]"
                  style={{ fontSize: 'clamp(1.25rem, 2.5vw, 1.875rem)' }}
                >
                  {roomCode}
                </p>
              </div>
            ) : null}
            <button
              type="button"
              onClick={() => void toggleFullscreen()}
              className="flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--card)]/80 text-[var(--muted-foreground)] transition-colors hover:border-[var(--primary)]/50 hover:text-[#f0f4fa]"
              aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
              data-testid="fullscreen-toggle"
            >
              {isFullscreen ? (
                <Minimize className="h-5 w-5" aria-hidden />
              ) : (
                <Maximize className="h-5 w-5" aria-hidden />
              )}
            </button>
            <DisplayConnectionBadge status={connectionStatus} />
          </div>
        </div>
      </header>

      <main
        className={cn(
          'relative z-10 mx-auto flex w-full max-w-[1600px] flex-1 flex-col overflow-y-auto px-6 py-6 lg:px-10 lg:py-8',
          'min-h-0',
          className,
        )}
      >
        <div className="display-screen-enter flex min-h-0 flex-1 flex-col">{children}</div>
      </main>

      <footer className="relative z-10 border-t border-[var(--border)]/50 bg-[var(--background)]/80 px-6 py-3 text-center backdrop-blur-sm lg:px-10">
        {footer ?? (
          <p className="font-sans text-xs tracking-wide text-[var(--muted-foreground)] lg:text-sm">
            Presentation display · answers sync live from the host
          </p>
        )}
      </footer>

      <style>{`
        @keyframes display-fade-slide {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .display-screen-enter {
          animation: display-fade-slide 420ms ease-out both;
        }
      `}</style>
    </div>
  )
}
