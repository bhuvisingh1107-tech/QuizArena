import type { WsConnectionStatus } from '@/hooks/displayLiveReducer'
import { cn } from '@/lib/utils'

interface WaitingScreenProps {
  quizTitle?: string
  roomCode?: string
  connectionStatus?: WsConnectionStatus
  className?: string
}

export function WaitingScreen({
  quizTitle = 'QuizArena',
  roomCode,
  connectionStatus = 'connecting',
  className,
}: WaitingScreenProps) {
  const statusLabel =
    connectionStatus === 'connected'
      ? 'Connected — waiting for host'
      : connectionStatus === 'connecting'
        ? 'Connecting to session…'
        : connectionStatus === 'error'
          ? 'Connection issue — retrying…'
          : 'Reconnecting…'

  return (
    <section
      className={cn(
        'flex flex-1 flex-col items-center justify-center gap-8 text-center',
        className,
      )}
      aria-label="Waiting for host"
    >
      <p className="text-sm uppercase tracking-[0.35em] text-[var(--primary)] lg:text-base">
        Live session
      </p>
      <h1 className="max-w-5xl font-display text-4xl font-extrabold leading-tight text-[#f0f4fa] sm:text-5xl lg:text-7xl">
        {quizTitle}
      </h1>

      {roomCode ? (
        <div className="mt-2 rounded-2xl border border-[var(--border)] bg-[var(--card)]/70 px-10 py-8 lg:px-16 lg:py-10">
          <p className="mb-3 text-sm uppercase tracking-[0.3em] text-[var(--muted-foreground)]">
            Room code
          </p>
          <p
            className="font-display text-5xl font-bold tracking-[0.28em] text-[var(--accent)] sm:text-6xl lg:text-8xl"
            data-testid="display-room-code"
          >
            {roomCode}
          </p>
        </div>
      ) : null}

      <div className="space-y-2">
        <p className="font-display text-2xl font-semibold text-[#f0f4fa] lg:text-3xl">
          Waiting for host
        </p>
        <p className="text-base text-[var(--muted-foreground)] lg:text-lg" role="status">
          {statusLabel}
        </p>
      </div>
    </section>
  )
}
