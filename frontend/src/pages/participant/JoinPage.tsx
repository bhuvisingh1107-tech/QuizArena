import { useEffect, useRef, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'

import { JoinForm } from '@/components/participant/JoinForm'
import { ParticipantShell } from '@/components/participant/ParticipantShell'
import { LoadingState } from '@/components/shared/LoadingState'
import { getParticipantRouteForRoomState } from '@/hooks/participantLiveReducer'
import { useParticipantSession } from '@/hooks/queries/useParticipantSession'
import { getParticipantSession } from '@/lib/participant-session'

export function JoinPage() {
  const { hasSession, isLoading, refreshSession } = useParticipantSession()
  const [redirectTo, setRedirectTo] = useState<string | null>(null)
  // Distinguish cold restore from a fresh join so we don't unmount JoinForm
  // (and race navigate) when persistJoin flips hasSession mid-submit.
  const hadSessionOnMount = useRef(Boolean(getParticipantSession()))

  useEffect(() => {
    if (!hadSessionOnMount.current) return
    if (!hasSession || isLoading) return

    let cancelled = false

    void (async () => {
      const me = await refreshSession()
      if (cancelled) return
      if (!me) {
        // refreshSession already cleared invalid sessions; stay on join form.
        return
      }
      const route = getParticipantRouteForRoomState(me.room.state) ?? '/lobby'
      setRedirectTo(route)
    })()

    return () => {
      cancelled = true
    }
  }, [hasSession, isLoading, refreshSession])

  if (isLoading) {
    return (
      <ParticipantShell subtitle="Join a live quiz" showConnectionBanner={false}>
        <div className="flex flex-1 items-center justify-center">
          <LoadingState label="Restoring session…" />
        </div>
      </ParticipantShell>
    )
  }

  if (hadSessionOnMount.current && hasSession && !redirectTo) {
    return (
      <ParticipantShell subtitle="Join a live quiz" showConnectionBanner={false}>
        <div className="flex flex-1 items-center justify-center">
          <LoadingState label="Restoring session…" />
        </div>
      </ParticipantShell>
    )
  }

  if (hasSession && redirectTo) {
    return <Navigate to={redirectTo} replace />
  }

  return (
    <ParticipantShell subtitle="Join a live quiz" showConnectionBanner={false}>
      <div className="flex flex-1 flex-col justify-center">
        <div className="mb-8 text-center">
          <h1 className="font-display text-3xl font-bold text-[#f0f4fa]">Join a quiz</h1>
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">
            Enter your name and the 6-character room code from your host.
          </p>
        </div>

        <JoinForm />

        <p className="mt-8 text-center text-xs text-[var(--muted-foreground)]">
          Hosting instead?{' '}
          <Link
            to="/admin/login"
            className="text-[var(--primary)] underline-offset-2 hover:underline"
          >
            Admin sign in
          </Link>
        </p>
      </div>
    </ParticipantShell>
  )
}
