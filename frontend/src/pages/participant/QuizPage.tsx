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
  return (
    <ParticipantShell
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
      <div className="space-y-5 pb-4">
        {live.room?.state === 'Paused' ? (
          <div
            role="status"
            className="rounded-xl border border-[var(--accent)]/40 bg-[var(--accent)]/15 px-4 py-3 text-center text-sm font-medium text-[var(--accent)]"
          >
            Quiz Paused
          </div>
        ) : null}

        {phase !== 'leaderboard' ? (
          <LiveLeaderboardCard
            yourRank={live.yourRank}
            yourScore={totalScore}
            leaderboard={live.leaderboard}
            previousRanks={live.previousLeaderboardRanks}
            selfParticipantId={selfId}
            compact={phase === 'feedback'}
          />
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

        {phase === 'feedback' && question ? (
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
              feedback={live.lastFeedback}
              totalScore={totalScore}
            />
          </>
        ) : null}

        {phase === 'scoring' && question ? (
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
            <AnswerFeedbackCard
              question={question}
              options={options}
              feedback={null}
              totalScore={totalScore}
            />
          </>
        ) : null}

        {phase === 'leaderboard' ? (
          <div className="space-y-4">
            <div className="text-center">
              <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
                Round complete
              </p>
              <h2 className="mt-2 font-display text-2xl font-bold text-[#f0f4fa]">
                Leaderboard
              </h2>
            </div>
            <LiveLeaderboardCard
              yourRank={live.yourRank}
              yourScore={totalScore}
              leaderboard={live.leaderboard}
              previousRanks={live.previousLeaderboardRanks}
              selfParticipantId={selfId}
              topN={10}
              title="Your rank"
            />
            <p className="text-center text-sm text-[var(--muted-foreground)]">
              Waiting for the next question…
            </p>
          </div>
        ) : null}
      </div>
    </ParticipantShell>
  )
}
