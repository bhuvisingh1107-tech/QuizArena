import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

import { LiveLeaderboardCard } from '@/components/participant/LiveLeaderboardCard'
import { ParticipantShell } from '@/components/participant/ParticipantShell'
import { PodiumView } from '@/components/participant/PodiumView'
import { ResultsSummary } from '@/components/participant/ResultsSummary'
import { EmptyState } from '@/components/shared/EmptyState'
import { LoadingState } from '@/components/shared/LoadingState'
import { Button } from '@/components/ui/button'
import { useParticipantLive } from '@/contexts/ParticipantLiveContext'
import {
  useParticipantLeaveMutation,
  useParticipantMeQuery,
  useParticipantSession,
} from '@/hooks/queries/useParticipantSession'

export function ResultsPage() {
  const navigate = useNavigate()
  const { session } = useParticipantSession()
  const meQuery = useParticipantMeQuery(Boolean(session?.sessionToken))
  const leaveMutation = useParticipantLeaveMutation()
  const live = useParticipantLive()

  useEffect(() => {
    if (!live.suggestedRoute || live.suggestedRoute === '/results') return
    if (live.suggestedRoute === '/lobby' || live.suggestedRoute === '/quiz') {
      navigate(live.suggestedRoute, { replace: true })
    }
  }, [live.suggestedRoute, navigate])

  const profile = meQuery.data?.participant
  const displayName = profile?.displayName || session?.displayName || 'You'
  const rank = profile?.rank ?? live.yourRank
  const score = profile?.totalScore ?? live.yourScore
  const correct = profile?.totalCorrect ?? 0
  const incorrect = profile?.totalIncorrect ?? 0
  const unanswered = profile?.unansweredCount ?? 0
  const timeBonus = live.cumulativeTimeBonus
  const streakBonus = live.cumulativeStreakBonus
  const selfId = live.self?.id ?? session?.participantId ?? null

  const onLeave = async () => {
    await leaveMutation.mutateAsync()
    navigate('/join', { replace: true })
  }

  return (
    <ParticipantShell
      connectionStatus={live.connectionStatus}
      isOffline={live.isOffline}
      lastError={live.lastError}
      onRetryConnection={() => live.reconnect()}
      subtitle={meQuery.data?.room.quizTitle || session?.quizTitle || 'Results'}
    >
      <div className="space-y-6 pb-8">
        <div className="participant-celebrate text-center">
          <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
            Final results
          </p>
          <h1 className="mt-2 font-display text-3xl font-bold text-[var(--heading)]">
            Quiz complete!
          </h1>
        </div>

        {meQuery.isLoading ? <LoadingState label="Loading your results…" /> : null}

        {meQuery.isError ? (
          <EmptyState
            title="Could not load results"
            description="Your live standing is still shown below when available."
            action={
              <Button type="button" variant="outline" onClick={() => void meQuery.refetch()}>
                Try again
              </Button>
            }
          />
        ) : null}

        {!meQuery.isLoading ? (
          <ResultsSummary
            displayName={displayName}
            rank={rank}
            score={score}
            correct={correct}
            incorrect={incorrect}
            unanswered={unanswered}
            timeBonus={timeBonus}
            streakBonus={streakBonus}
          />
        ) : null}

        <PodiumView podium={live.podium} />

        <LiveLeaderboardCard
          yourRank={rank ?? null}
          yourScore={score}
          leaderboard={live.leaderboard}
          previousRanks={live.previousLeaderboardRanks}
          selfParticipantId={selfId}
          topN={10}
          title="Final standing"
        />

        <Button
          type="button"
          variant="outline"
          className="h-12 w-full"
          onClick={() => void onLeave()}
          disabled={leaveMutation.isPending}
        >
          Return home
        </Button>
      </div>
    </ParticipantShell>
  )
}
