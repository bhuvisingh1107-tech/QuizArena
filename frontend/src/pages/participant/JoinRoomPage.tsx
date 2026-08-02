import { Link, useParams } from 'react-router-dom'

import { JoinForm } from '@/components/participant/JoinForm'
import { ParticipantShell } from '@/components/participant/ParticipantShell'

export function JoinRoomPage() {
  const { roomCode: roomCodeParam = '' } = useParams()

  return (
    <ParticipantShell
      subtitle={`Room ${roomCodeParam.toUpperCase() || '—'}`}
      showConnectionBanner={false}
    >
      <div className="flex flex-1 flex-col justify-center">
        <div className="mb-8 text-center">
          <h1 className="font-display text-3xl font-bold text-[#f0f4fa]">Join the lobby</h1>
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">
            Confirm your name and room code to enter.
          </p>
        </div>

        <JoinForm
          initialRoomCode={roomCodeParam}
          roomCodeReadOnly
          backLink={
            <Link
              to="/join"
              className="text-sm text-[var(--primary)] underline-offset-2 hover:underline"
            >
              Different room code?
            </Link>
          }
        />
      </div>
    </ParticipantShell>
  )
}
