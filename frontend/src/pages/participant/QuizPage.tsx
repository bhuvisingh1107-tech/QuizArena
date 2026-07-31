import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

import { LiveLeaderboardCard } from '@/components/participant/LiveLeaderboardCard'
import { OptionList } from '@/components/participant/OptionList'
import { ParticipantShell } from '@/components/participant/ParticipantShell'
import { QuestionCard } from '@/components/participant/QuestionCard'
import { SubmitBar } from '@/components/participant/SubmitBar'
import { EmptyState } from '@/components/shared/EmptyState'
import { useParticipantSession } from '@/hooks/queries/useParticipantSession'
import { useParticipantWebSocket } from '@/hooks/useParticipantWebSocket'

export function QuizPage() {
  const navigate = useNavigate()
  const { session } = useParticipantSession()
  const live = useParticipantWebSocket({ enabled: Boolean(session?.sessionToken) })

  useEffect(() => {
    if (!live.suggestedRoute || live.suggestedRoute === '/quiz') return
    navigate(live.suggestedRoute, { replace: true })
  }, [live.suggestedRoute, navigate])

  const question = live.question
  const questionClosed =
    question?.state === 'Closed' ||
    question?.state === 'Revealed' ||
    question?.state === 'Scored'
  const showCorrectness =
    question?.state === 'Revealed' || question?.state === 'Scored'

  return (
    <ParticipantShell
      connectionStatus={live.connectionStatus}
      isOffline={live.isOffline}
      subtitle={live.room?.quizTitle || session?.quizTitle}
      footer={
        question ? (
          <SubmitBar
            submissionStatus={live.submissionStatus}
            submissionError={live.submissionError}
            canSubmit={live.selectedOptionIds.length > 0}
            disabled={questionClosed || live.isOffline}
            onSubmit={() => live.sendAnswer(live.selectedOptionIds)}
          />
        ) : null
      }
    >
      <div className="space-y-5 pb-4">
        <LiveLeaderboardCard
          yourRank={live.yourRank}
          yourScore={live.yourScore || live.self?.totalScore || 0}
          leaderboard={live.leaderboard}
        />

        {!question ? (
          <EmptyState
            title="Waiting for the next question"
            description="The host will open a question shortly. Stay on this screen."
          />
        ) : (
          <>
            <QuestionCard question={question} />
            <OptionList
              options={live.options.length ? live.options : question.options}
              selectedOptionIds={live.selectedOptionIds}
              allowMultiple={Boolean(question.allowMultipleCorrect)}
              disabled={questionClosed}
              showCorrectness={showCorrectness}
              submissionStatus={live.submissionStatus}
              onChange={live.selectOptions}
            />
          </>
        )}

        {live.lastError ? (
          <p className="text-center text-sm text-[var(--destructive)]" role="alert">
            {live.lastError}
          </p>
        ) : null}
      </div>
    </ParticipantShell>
  )
}
