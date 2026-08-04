import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

import { AnswerFeedbackCard } from '@/components/participant/AnswerFeedbackCard'
import { LiveLeaderboardCard } from '@/components/participant/LiveLeaderboardCard'
import { OptionList } from '@/components/participant/OptionList'
import { ParticipantShell } from '@/components/participant/ParticipantShell'
import { QuestionCard } from '@/components/participant/QuestionCard'
import { SubmitBar } from '@/components/participant/SubmitBar'
import { EmptyState } from '@/components/shared/EmptyState'
import { useParticipantLive } from '@/contexts/ParticipantLiveContext'
import { deriveQuizPhase } from '@/hooks/participantLiveReducer'
import { useParticipantSession } from '@/hooks/queries/useParticipantSession'

export function QuizPage() {
  const navigate = useNavigate()
  const { session } = useParticipantSession()
  const live = useParticipantLive()

  useEffect(() => {
    if (live.resultsReady || live.room?.state === 'Completed' || live.room?.state === 'Closed') {
      navigate('/results', { replace: true })
      return
    }
    if (!live.suggestedRoute || live.suggestedRoute === '/quiz') return
    navigate(live.suggestedRoute, { replace: true })
  }, [live.suggestedRoute, live.resultsReady, live.room?.state, navigate])

  const question = live.question
  const phase = deriveQuizPhase(live)
  const options = live.options.length ? live.options : (question?.options ?? [])

  const questionClosed =
    question?.state === 'Closed' ||
    question?.state === 'Revealed' ||
    question?.state === 'Scored'
  const showCorrectness =
    question?.state === 'Revealed' || question?.state === 'Scored' || phase === 'feedback'

  const totalScore = live.yourScore || live.self?.totalScore || 0
  const selfId = live.self?.id ?? session?.participantId ?? null

  if (phase === 'completed') {
    return (
      <ParticipantShell
        connectionStatus={live.connectionStatus}
        isOffline={live.isOffline}
        lastError={live.lastError}
        onRetryConnection={() => live.reconnect()}
        subtitle={live.room?.quizTitle || session?.quizTitle}
      >
        <EmptyState
          title="Quiz complete"
          description="Loading final results…"
        />
      </ParticipantShell>
    )
  }

  const leaderboardPanel = (
    <LiveLeaderboardCard
      yourRank={live.yourRank}
      yourScore={totalScore}
      leaderboard={live.leaderboard}
      previousRanks={live.previousLeaderboardRanks}
      selfParticipantId={selfId}
      topN={10}
      title="Live leaderboard"
      className="h-full max-h-[min(70vh,36rem)]"
    />
  )

  return (
    <ParticipantShell
      wide
      connectionStatus={live.connectionStatus}
      isOffline={live.isOffline}
      lastError={live.lastError}
      onRetryConnection={() => live.reconnect()}
      subtitle={live.room?.quizTitle || session?.quizTitle}
      footer={
        phase === 'answering' && question ? (
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
      <div className="flex flex-col gap-5 pb-4 md:min-h-[28rem] md:flex-row md:items-stretch md:gap-5 lg:gap-6">
        <div className="min-w-0 flex-1 space-y-5 md:min-w-0">
          {live.room?.state === 'Paused' ? (
            <div
              role="status"
              className="rounded-xl border border-[var(--accent)]/40 bg-[var(--accent)]/15 px-4 py-3 text-center text-sm font-medium text-[var(--accent)]"
            >
              Quiz Paused
            </div>
          ) : null}

          {phase === 'waiting' ? (
            <EmptyState
              title="Waiting for the next question"
              description="The host will open a question shortly. Stay on this screen."
            />
          ) : null}

          {phase === 'answering' && question ? (
            <>
              <QuestionCard
                question={question}
                sessionToken={session?.sessionToken}
                openedAt={live.questionOpenedAt}
                paused={live.room?.state === 'Paused'}
              />
              <OptionList
                options={options}
                selectedOptionIds={live.selectedOptionIds}
                allowMultiple={Boolean(question.allowMultipleCorrect)}
                disabled={questionClosed}
                showCorrectness={false}
                submissionStatus={live.submissionStatus}
                onChange={live.selectOptions}
              />
            </>
          ) : null}

          {phase === 'closed' && question ? (
            <>
              <QuestionCard
                question={question}
                sessionToken={session?.sessionToken}
                openedAt={live.questionOpenedAt}
                paused={live.room?.state === 'Paused'}
              />
              <OptionList
                options={options}
                selectedOptionIds={live.selectedOptionIds}
                allowMultiple={Boolean(question.allowMultipleCorrect)}
                disabled
                showCorrectness={false}
                submissionStatus={live.submissionStatus}
                onChange={live.selectOptions}
              />
              <EmptyState
                title="Time's up"
                description="Answers are locked. Waiting for the host to reveal results…"
              />
            </>
          ) : null}

          {(phase === 'feedback' || phase === 'scoring') && question ? (
            <>
              <QuestionCard
                question={question}
                sessionToken={session?.sessionToken}
                openedAt={live.questionOpenedAt}
                paused={live.room?.state === 'Paused'}
              />
              <OptionList
                options={options}
                selectedOptionIds={live.selectedOptionIds}
                allowMultiple={Boolean(question.allowMultipleCorrect)}
                disabled
                showCorrectness={showCorrectness}
                submissionStatus={live.submissionStatus}
                onChange={live.selectOptions}
              />
              <AnswerFeedbackCard
                question={question}
                options={options}
                feedback={phase === 'feedback' ? live.lastFeedback : null}
                totalScore={totalScore}
              />
            </>
          ) : null}
        </div>

        <aside className="w-full shrink-0 md:w-64 md:max-w-[38%] lg:w-[22rem] lg:max-w-[22rem] xl:w-[24rem] xl:max-w-[24rem]">
          {leaderboardPanel}
        </aside>
      </div>
    </ParticipantShell>
  )
}
