import { Copy, Loader2, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ParticipantShell } from '@/components/participant/ParticipantShell'
import { Button } from '@/components/ui/button'
import { useParticipantLive } from '@/contexts/ParticipantLiveContext'
import { useParticipantLeaveMutation, useParticipantSession } from '@/hooks/queries/useParticipantSession'

export function LobbyPage() {
  const navigate = useNavigate()
  const { session } = useParticipantSession()
  const leaveMutation = useParticipantLeaveMutation()
  const live = useParticipantLive()
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!live.suggestedRoute || live.suggestedRoute === '/lobby') return
    navigate(live.suggestedRoute, { replace: true })
  }, [live.suggestedRoute, navigate])

  useEffect(() => {
    if (!copied) return
    const id = window.setTimeout(() => setCopied(false), 2000)
    return () => window.clearTimeout(id)
  }, [copied])

  const quizTitle = live.room?.quizTitle || session?.quizTitle || 'Live quiz'
  const hostName = live.room?.hostName || 'Host'
  const roomCode = session?.roomCode || live.room?.roomCode || ''
  const participantCount = live.participantCount

  const onLeave = async () => {
    await leaveMutation.mutateAsync()
    navigate('/join', { replace: true })
  }

  const onCopyCode = async () => {
    if (!roomCode) return
    try {
      await navigator.clipboard.writeText(roomCode)
      setCopied(true)
    } catch {
      // clipboard unavailable
    }
  }

  return (
    <ParticipantShell
      connectionStatus={live.connectionStatus}
      isOffline={live.isOffline}
      subtitle={roomCode ? `Room ${roomCode}` : undefined}
    >
      <div className="flex flex-1 flex-col items-center justify-center text-center">
        <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
          Waiting lobby
        </p>
        <h1 className="mt-3 font-display text-3xl font-bold text-[#f0f4fa] sm:text-4xl">
          {quizTitle}
        </h1>
        <p className="mt-2 text-sm text-[var(--muted-foreground)]">
          Hosted by <span className="text-[var(--primary)]">{hostName}</span>
        </p>

        <div className="mt-10 w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)]/80 p-6">
          <div className="relative mx-auto mb-4 flex h-16 w-16 items-center justify-center">
            <span
              className="absolute inset-0 animate-ping rounded-full bg-[var(--primary)]/20"
              aria-hidden
            />
            <span
              className="absolute inset-2 animate-pulse rounded-full bg-[var(--primary)]/10"
              aria-hidden
            />
            <div className="relative flex h-14 w-14 items-center justify-center rounded-full bg-[var(--primary)]/15 text-[var(--primary)]">
              <Loader2 className="h-6 w-6 animate-spin" aria-hidden />
            </div>
          </div>

          <p className="font-display text-lg font-semibold text-[#f0f4fa]">
            Waiting for host to start…
          </p>
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">
            Keep this screen open. You&apos;ll move into the quiz automatically.
          </p>

          {roomCode ? (
            <button
              type="button"
              onClick={() => void onCopyCode()}
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[var(--secondary)]/70 px-4 py-2 font-display text-sm tracking-[0.25em] text-[#f0f4fa] uppercase transition-colors hover:bg-[var(--secondary)]"
            >
              {roomCode}
              <Copy className="h-3.5 w-3.5 text-[var(--muted-foreground)]" aria-hidden />
              <span className="sr-only">{copied ? 'Copied' : 'Copy room code'}</span>
            </button>
          ) : null}
          {copied ? (
            <p className="mt-1 text-xs text-[var(--color-success)]">Copied!</p>
          ) : null}

          {participantCount != null ? (
            <p className="mt-4 inline-flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
              <Users className="h-4 w-4" aria-hidden />
              {participantCount} {participantCount === 1 ? 'player' : 'players'} joined
            </p>
          ) : (
            <p className="mt-4 text-sm text-[var(--muted-foreground)]">Counting players…</p>
          )}
        </div>

        <Button
          type="button"
          variant="ghost"
          className="mt-8 h-12"
          onClick={() => void onLeave()}
          disabled={leaveMutation.isPending}
        >
          Leave room
        </Button>
      </div>
    </ParticipantShell>
  )
}
