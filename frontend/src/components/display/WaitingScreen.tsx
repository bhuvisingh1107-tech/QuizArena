import { QRCodeSVG } from 'qrcode.react'

import { AnimatedCounter } from '@/components/display/AnimatedCounter'
import type { WsConnectionStatus } from '@/hooks/displayLiveReducer'
import { getJoinPageUrl } from '@/lib/app-url'
import { cn } from '@/lib/utils'

interface WaitingScreenProps {
  quizTitle?: string
  roomCode?: string
  participantCount?: number
  connectionStatus?: WsConnectionStatus
  className?: string
}

export function WaitingScreen({
  quizTitle = 'QuizArena',
  roomCode,
  participantCount = 0,
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

  const joinUrl = roomCode?.trim()
    ? getJoinPageUrl(roomCode)
    : null

  return (
    <section
      className={cn(
        'relative flex flex-1 flex-col items-center justify-center gap-8 text-center',
        className,
      )}
      aria-label="Waiting for host"
    >
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="display-wait-orb display-wait-orb-a absolute left-1/4 top-1/4 h-64 w-64 rounded-full bg-[var(--primary)]/15 blur-3xl" />
        <div className="display-wait-orb display-wait-orb-b absolute bottom-1/4 right-1/4 h-72 w-72 rounded-full bg-[var(--accent)]/12 blur-3xl" />
      </div>

      <p className="relative text-sm uppercase tracking-[0.35em] text-[var(--primary)] lg:text-base">
        Quiz<span className="text-[var(--accent)]">Arena</span> · Live session
      </p>
      <h1
        className="relative max-w-5xl font-display font-extrabold leading-tight text-[#f0f4fa]"
        style={{ fontSize: 'clamp(2rem, 5vw, 4.5rem)' }}
      >
        {quizTitle}
      </h1>

      {roomCode ? (
        <div className="relative mt-2 flex flex-col items-center gap-8 rounded-2xl border border-[var(--border)] bg-[var(--card)]/70 px-8 py-8 lg:flex-row lg:gap-12 lg:px-16 lg:py-10">
          <div>
            <p className="mb-3 text-sm uppercase tracking-[0.3em] text-[var(--muted-foreground)]">
              Room code
            </p>
            <p
              className="font-display font-bold tracking-[0.28em] text-[var(--accent)]"
              style={{ fontSize: 'clamp(2.5rem, 8vw, 5.5rem)' }}
              data-testid="display-room-code"
            >
              {roomCode}
            </p>
          </div>

          {joinUrl ? (
            <div className="rounded-xl bg-white p-4 shadow-lg">
              <QRCodeSVG
                value={joinUrl}
                size={280}
                level="M"
                data-testid="join-qr-code"
                className="mx-auto h-40 w-40 lg:h-[280px] lg:w-[280px]"
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {joinUrl ? (
        <p
          className="relative max-w-2xl truncate font-mono text-sm text-[var(--muted-foreground)] lg:text-base"
          data-testid="join-url"
        >
          {joinUrl}
        </p>
      ) : null}

      <div className="relative space-y-3">
        <p
          className="font-display font-semibold text-[#f0f4fa]"
          style={{ fontSize: 'clamp(1.25rem, 3vw, 2rem)' }}
        >
          Waiting for host
        </p>
        <p className="text-base text-[var(--muted-foreground)] lg:text-lg" role="status">
          {statusLabel}
        </p>
        {participantCount > 0 || connectionStatus === 'connected' ? (
          <p
            className="font-display text-xl text-[var(--primary)] lg:text-2xl"
            data-testid="participant-count"
          >
            <AnimatedCounter value={participantCount} /> player
            {participantCount === 1 ? '' : 's'} joined
          </p>
        ) : null}
      </div>

      <style>{`
        @keyframes display-wait-drift-a {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(30px, -20px) scale(1.08); }
        }
        @keyframes display-wait-drift-b {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(-24px, 16px) scale(1.05); }
        }
        .display-wait-orb-a { animation: display-wait-drift-a 8s ease-in-out infinite; }
        .display-wait-orb-b { animation: display-wait-drift-b 10s ease-in-out infinite; }
      `}</style>
    </section>
  )
}
