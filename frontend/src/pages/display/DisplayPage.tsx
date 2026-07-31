import type { ReactNode } from 'react'

import { DisplayShell } from '@/components/display/DisplayShell'
import { LeaderboardScreen } from '@/components/display/LeaderboardScreen'
import { PodiumScreen } from '@/components/display/PodiumScreen'
import { QuestionScreen } from '@/components/display/QuestionScreen'
import { RevealScreen } from '@/components/display/RevealScreen'
import { SectionBreakScreen } from '@/components/display/SectionBreakScreen'
import { WaitingScreen } from '@/components/display/WaitingScreen'
import { ErrorState } from '@/components/shared/ErrorState'
import { useDisplayWebSocket } from '@/hooks/useDisplayWebSocket'

interface DisplayPageProps {
  secretToken: string | undefined
}

export function DisplayPage({ secretToken }: DisplayPageProps) {
  const live = useDisplayWebSocket({
    secretToken,
    enabled: Boolean(secretToken?.trim()),
  })

  if (!secretToken?.trim() || live.authFailed) {
    return (
      <DisplayShell connectionStatus={live.connectionStatus}>
        <div className="flex flex-1 items-center justify-center">
          <ErrorState
            title="Display unavailable"
            message={
              live.lastError ??
              (!secretToken?.trim()
                ? 'This presentation link is missing a token.'
                : 'Invalid or closed room token. Ask the host for a new display link.')
            }
          />
        </div>
      </DisplayShell>
    )
  }

  const quizTitle = live.room?.quizTitle
  const roomCode = live.room?.roomCode

  let body: ReactNode
  switch (live.viewMode) {
    case 'question':
      body = live.question ? (
        <QuestionScreen question={live.question} />
      ) : (
        <WaitingScreen
          quizTitle={quizTitle}
          roomCode={roomCode}
          connectionStatus={live.connectionStatus}
        />
      )
      break
    case 'reveal':
      body = live.question ? (
        <RevealScreen question={live.question} leaderboard={live.leaderboard} />
      ) : (
        <WaitingScreen
          quizTitle={quizTitle}
          roomCode={roomCode}
          connectionStatus={live.connectionStatus}
        />
      )
      break
    case 'section_break':
      body = (
        <SectionBreakScreen
          section={live.section}
          leaderboard={live.leaderboard}
          previousRanks={live.previousRanks}
        />
      )
      break
    case 'leaderboard':
      body = (
        <LeaderboardScreen
          leaderboard={live.leaderboard}
          previousRanks={live.previousRanks}
        />
      )
      break
    case 'podium':
    case 'completed':
      body = (
        <PodiumScreen
          podium={live.podium}
          leaderboard={live.leaderboard}
          quizTitle={quizTitle}
        />
      )
      break
    case 'waiting':
    default:
      body = (
        <WaitingScreen
          quizTitle={quizTitle}
          roomCode={roomCode}
          connectionStatus={live.connectionStatus}
        />
      )
  }

  return (
    <DisplayShell
      quizTitle={quizTitle}
      roomCode={roomCode}
      connectionStatus={live.connectionStatus}
    >
      {body}
    </DisplayShell>
  )
}

export default DisplayPage
