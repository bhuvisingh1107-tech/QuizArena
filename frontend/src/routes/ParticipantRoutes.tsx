import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'

import { LoadingState } from '@/components/shared/LoadingState'
import { ParticipantLiveProvider } from '@/contexts/ParticipantLiveContext'
import { ParticipantSessionProvider } from '@/contexts/ParticipantSessionContext'
import { useParticipantSession } from '@/hooks/queries/useParticipantSession'
import { JoinPage } from '@/pages/participant/JoinPage'
import { JoinRoomPage } from '@/pages/participant/JoinRoomPage'
import { LobbyPage } from '@/pages/participant/LobbyPage'
import { QuizPage } from '@/pages/participant/QuizPage'
import { ResultsPage } from '@/pages/participant/ResultsPage'

function ParticipantProtected() {
  const { hasSession, isLoading } = useParticipantSession()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <LoadingState label="Restoring session…" />
      </div>
    )
  }

  if (!hasSession) {
    return <Navigate to="/join" replace state={{ from: location.pathname }} />
  }

  return (
    <ParticipantLiveProvider>
      <Outlet />
    </ParticipantLiveProvider>
  )
}

export function ParticipantRoutes() {
  return (
    <ParticipantSessionProvider>
      <Routes>
        <Route path="join" element={<JoinPage />} />
        <Route path="join/:roomCode/lobby" element={<Navigate to="/lobby" replace />} />
        <Route path="join/:roomCode/play" element={<Navigate to="/quiz" replace />} />
        <Route path="join/:roomCode/results" element={<Navigate to="/results" replace />} />
        <Route path="join/:roomCode" element={<JoinRoomPage />} />

        <Route element={<ParticipantProtected />}>
          <Route path="lobby" element={<LobbyPage />} />
          <Route path="quiz" element={<QuizPage />} />
          <Route path="results" element={<ResultsPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/join" replace />} />
      </Routes>
    </ParticipantSessionProvider>
  )
}
