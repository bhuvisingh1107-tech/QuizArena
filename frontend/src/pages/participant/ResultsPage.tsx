import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

import { LiveLeaderboardCard } from '@/components/participant/LiveLeaderboardCard'
import { ParticipantShell } from '@/components/participant/ParticipantShell'
import { PodiumView } from '@/components/participant/PodiumView'
import { ResultsSummary } from '@/components/participant/ResultsSummary'
import { EmptyState } from '@/components/shared/EmptyState'
import { LoadingState } from '@/components/shared/LoadingState'
import { Button } from '@/components/ui/button'
import {
  useParticipantLeaveMutation,
  useParticipantMeQuery,
  useParticipantSession,
} from '@/hooks/queries/useParticipantSession'
import { useParticipantWebSocket } from '@/hooks/useParticipantWebSocket'

export function ResultsPage() {
  const navigate = useNavigate()
  const { session } = useParticipantSession()
  const meQuery = useParticipantMeQuery(Boolean(session?.sessionToken))
  const leaveMutation = useParticipantLeaveMutation()
  const live = useParticipantWebSocket({ enabled: Boolean(session?.sessionToken) })

  useEffect(() => {
    if (!live.suggestedRoute || live.suggestedRoute === '/results') return
    // Only navigate away from results if room somehow returns to lobby/active mid-view
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

  const onLeave = async () => {
    await leaveMutation.mutateAsync()
    navigate('/join', { replace: true })
  }

  return (
    <ParticipantShell
      connectionStatus={live.connectionStatus}
      isOffline={live.isOffline}
      subtitle={meQuery.data?.room.quizTitle || session?.quizTitle || 'Results'}
    >
      <div className="space-y-6 pb-8">
        <div className="text-center">
          <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
            Final results
          </p>
          <h1 className="mt-2 font-display text-3xl font-bold text-[#f0f4fa]">Quiz complete</h1>
        </div>

        {meQuery.isLoading ? <LoadingState label="Loading your results…" /> : null}

        {meQuery.isError ? (
          <EmptyState
            title="Could not load results"
            description="Your live standing is still shown below when available."
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
          />
        ) : null}

        <PodiumView podium={live.podium} />

        <LiveLeaderboardCard
          yourRank={rank ?? null}
          yourScore={score}
          leaderboard={live.leaderboard}
          topN={10}
        />

        <EmptyState
          title="Section scores unavailable"
          description="Detailed section breakdowns are not provided on the participant results view."
          className="py-8"
        />

        <Button
          type="button"
          variant="outline"
          className="h-12 w-full"
          onClick={() => void onLeave()}
          disabled={leaveMutation.isPending}
        >
          Leave and join another quiz
        </Button>
      </div>
    </ParticipantShell>
  )
}
