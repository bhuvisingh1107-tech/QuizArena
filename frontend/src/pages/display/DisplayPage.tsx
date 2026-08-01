import type { ReactNode } from 'react'

import { DisplayShell } from '@/components/display/DisplayShell'
import { LeaderboardScreen } from '@/components/display/LeaderboardScreen'
import { PodiumScreen } from '@/components/display/PodiumScreen'
import { QuestionScreen } from '@/components/display/QuestionScreen'
import { RevealScreen } from '@/components/display/RevealScreen'
import { SectionBreakScreen } from '@/components/display/SectionBreakScreen'
import { TimeUpScreen } from '@/components/display/TimeUpScreen'
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
  const token = secretToken.trim()
  const paused = live.room?.state === 'Paused'

  let body: ReactNode
  switch (live.viewMode) {
    case 'question':
      body = live.question ? (
        <QuestionScreen
          question={live.question}
          secretToken={token}
          submittedCount={live.submittedCount}
          participantCount={live.participantCount}
          questionOpenedAt={live.questionOpenedAt}
          paused={paused}
        />
      ) : (
        <WaitingScreen
          quizTitle={quizTitle}
          roomCode={roomCode}
          participantCount={live.participantCount}
          connectionStatus={live.connectionStatus}
        />
      )
      break
    case 'time_up':
      body = <TimeUpScreen />
      break
    case 'reveal':
      body = live.question ? (
        <RevealScreen
          question={live.question}
          secretToken={token}
          optionDistribution={live.optionDistribution}
          explanation={live.explanation}
          accuracyPercent={live.accuracyPercent}
          answeredCount={live.answeredCount}
        />
      ) : (
        <WaitingScreen
          quizTitle={quizTitle}
          roomCode={roomCode}
          participantCount={live.participantCount}
          connectionStatus={live.connectionStatus}
        />
      )
      break
    case 'section_break':
      body = (
        <SectionBreakScreen
          section={live.section}
          top3={live.top3}
          sectionStats={live.sectionStats}
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
          sessionHighlights={live.sessionHighlights}
        />
      )
      break
    case 'waiting':
    default:
      body = (
        <WaitingScreen
          quizTitle={quizTitle}
          roomCode={roomCode}
          participantCount={live.participantCount}
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
      {live.lastError && !live.authFailed ? (
        <div
          role="status"
          aria-live="polite"
          className="mb-4 rounded-lg border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/10 px-4 py-3 text-center text-sm text-[var(--color-warning)]"
        >
          {live.lastError}
        </div>
      ) : null}
      {paused ? (
        <div
          role="status"
          className="mb-4 rounded-lg border border-[var(--accent)]/40 bg-[var(--accent)]/15 px-4 py-3 text-center font-display text-lg font-semibold text-[var(--accent)] lg:text-2xl"
        >
          Quiz paused
        </div>
      ) : null}
      {body}
    </DisplayShell>
  )
}

export default DisplayPage
