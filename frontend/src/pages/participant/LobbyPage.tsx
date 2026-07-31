import { Loader2, Users } from 'lucide-react'
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

import { ParticipantShell } from '@/components/participant/ParticipantShell'
import { Button } from '@/components/ui/button'
import { useParticipantLeaveMutation, useParticipantSession } from '@/hooks/queries/useParticipantSession'
import { useParticipantWebSocket } from '@/hooks/useParticipantWebSocket'

export function LobbyPage() {
  const navigate = useNavigate()
  const { session } = useParticipantSession()
  const leaveMutation = useParticipantLeaveMutation()
  const live = useParticipantWebSocket({ enabled: Boolean(session?.sessionToken) })

  useEffect(() => {
    if (!live.suggestedRoute || live.suggestedRoute === '/lobby') return
    navigate(live.suggestedRoute, { replace: true })
  }, [live.suggestedRoute, navigate])

  const quizTitle = live.room?.quizTitle || session?.quizTitle || 'Live quiz'
  const displayName = live.self?.displayName || session?.displayName || 'Player'

  const onLeave = async () => {
    await leaveMutation.mutateAsync()
    navigate('/join', { replace: true })
  }

  return (
    <ParticipantShell
      connectionStatus={live.connectionStatus}
      isOffline={live.isOffline}
      subtitle={session?.roomCode ? `Room ${session.roomCode}` : undefined}
    >
      <div className="flex flex-1 flex-col items-center justify-center text-center">
        <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
          Waiting lobby
        </p>
        <h1 className="mt-3 font-display text-3xl font-bold text-[#f0f4fa] sm:text-4xl">
          {quizTitle}
        </h1>
        <p className="mt-3 text-base text-[var(--muted-foreground)]">
          You&apos;re in as <span className="text-[var(--primary)]">{displayName}</span>
        </p>

        <div className="mt-10 w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)]/80 p-6">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--primary)]/15 text-[var(--primary)]">
            <Loader2 className="h-6 w-6 animate-spin" aria-hidden />
          </div>
          <p className="font-display text-lg font-semibold text-[#f0f4fa]">
            Waiting for the host to start
          </p>
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">
            Keep this screen open. You&apos;ll move into the quiz automatically.
          </p>

          {live.participantCount != null ? (
            <p className="mt-4 inline-flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
              <Users className="h-4 w-4" aria-hidden />
              {live.participantCount} joined
            </p>
          ) : null}

          <p className="mt-4 text-xs text-[var(--muted-foreground)]">
            Connection:{' '}
            <span className="text-[var(--foreground)]">{live.connectionStatus}</span>
          </p>
        </div>

        <Button
          type="button"
          variant="ghost"
          className="mt-8"
          onClick={() => void onLeave()}
          disabled={leaveMutation.isPending}
        >
          Leave room
        </Button>
      </div>
    </ParticipantShell>
  )
}
