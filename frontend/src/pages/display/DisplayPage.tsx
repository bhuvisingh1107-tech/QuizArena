import type { ReactNode } from 'react'

import { DisplayShell } from '@/components/display/DisplayShell'
import { LiveLeaderboardPanel } from '@/components/display/LiveLeaderboardPanel'
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

const SIDE_PANEL_MODES = new Set(['question', 'time_up', 'reveal', 'section_break'])

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
  const showSidePanel = SIDE_PANEL_MODES.has(live.viewMode)

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
    case 'leaderboard':
      // Mid-quiz full-screen leaderboard is retired; keep reveal + side panel.
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
      onRetryConnection={() => live.reconnect()}
    >
      {live.lastError && !live.authFailed ? (
        <div
          role="status"
          aria-live="polite"
          className="mb-4 flex flex-wrap items-center justify-center gap-3 rounded-lg border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/10 px-4 py-3 text-center text-sm text-[var(--color-warning)]"
        >
          <span>{live.lastError}</span>
          <button
            type="button"
            className="underline underline-offset-2 hover:opacity-90"
            onClick={() => live.reconnect()}
          >
            Retry connection
          </button>
        </div>
      ) : null}
      {paused ? (
        <div
          role="status"
          className="mb-4 rounded-lg border border-[var(--accent)]/40 bg-[var(--accent)]/15 px-4 py-3 text-center font-display text-lg font-semibold text-[var(--accent)] lg:text-2xl"
        >
          Quiz Paused
        </div>
      ) : null}
      <div
        className={
          showSidePanel
            ? 'flex min-h-0 flex-1 flex-col gap-5 lg:flex-row lg:gap-6'
            : 'flex min-h-0 flex-1 flex-col'
        }
      >
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">{body}</div>
        {showSidePanel ? (
          <div className="h-[min(42vh,22rem)] shrink-0 lg:h-auto lg:w-[min(28vw,26rem)] xl:w-[28rem]">
            <LiveLeaderboardPanel
              leaderboard={live.leaderboard}
              previousRanks={live.previousRanks}
            />
          </div>
        ) : null}
      </div>
    </DisplayShell>
  )
}

export default DisplayPage
