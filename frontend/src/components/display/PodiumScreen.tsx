import type { DisplaySessionHighlights } from '@/hooks/displayLiveReducer'
import type { LeaderboardEntry, Podium, PodiumEntry } from '@/types/api'
import { cn } from '@/lib/utils'

interface PodiumScreenProps {
  podium: Podium | null
  leaderboard?: LeaderboardEntry[]
  quizTitle?: string
  sessionHighlights?: DisplaySessionHighlights | null
  className?: string
}

const ORDER: Array<1 | 2 | 3> = [2, 1, 3]
const MEDALS: Record<1 | 2 | 3, string> = { 1: '1st', 2: '2nd', 3: '3rd' }

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function PodiumScreen({
  podium,
  leaderboard = [],
  quizTitle,
  sessionHighlights,
  className,
}: PodiumScreenProps) {
  const byRank = new Map<number, PodiumEntry>()
  // Prefer podium order (slice top 3) so competition-rank ties still fill 3 slots.
  const podiumSlots = (podium?.entries ?? []).slice(0, 3)
  podiumSlots.forEach((entry, index) => {
    byRank.set(index + 1, { ...entry, rank: (index + 1) as 1 | 2 | 3 })
  })
  const hasPodium = podiumSlots.length > 0
  const finalList =
    leaderboard.length > 0
      ? leaderboard
      : (podium?.entries.map((e) => ({
          rank: e.rank,
          participantId: e.participantId,
          displayName: e.displayName,
          score: e.score,
        })) ?? [])

  const winner = sessionHighlights?.winner

  return (
    <section
      className={cn('relative flex flex-1 flex-col gap-8 overflow-hidden', className)}
      aria-label="Final podium"
    >
      <div className="display-confetti pointer-events-none absolute inset-0" aria-hidden />

      <div className="relative text-center">
        <p className="text-sm uppercase tracking-[0.3em] text-[var(--accent)] lg:text-base">
          Quiz completed
        </p>
        <h1
          className="mt-3 font-display font-extrabold text-[#f0f4fa]"
          style={{ fontSize: 'clamp(2rem, 5vw, 4rem)' }}
        >
          {quizTitle ?? 'Final results'}
        </h1>
        {winner ? (
          <p
            className="mt-3 font-display text-2xl font-semibold text-[var(--accent)] lg:text-3xl"
            data-testid="quiz-winner"
          >
            {winner.displayName} wins with {winner.score} pts!
          </p>
        ) : (
          <p className="mt-2 text-base text-[var(--muted-foreground)] lg:text-lg">
            Congratulations to all players!
          </p>
        )}
        {sessionHighlights?.averageScore != null ? (
          <p className="mt-2 text-lg text-[var(--muted-foreground)]">
            Average score:{' '}
            <span className="font-display font-bold text-[var(--primary)]">
              {sessionHighlights.averageScore}
            </span>
          </p>
        ) : null}
      </div>

      {hasPodium ? (
        <div
          className="relative flex items-end justify-center gap-4 pt-4 lg:gap-8"
          data-testid="podium-top3"
        >
          {ORDER.map((rank) => {
            const entry = byRank.get(rank)
            const height =
              rank === 1 ? 'h-40 lg:h-52' : rank === 2 ? 'h-28 lg:h-36' : 'h-24 lg:h-28'
            const accent =
              rank === 1
                ? 'bg-[var(--accent)] text-[var(--accent-foreground)] shadow-[0_0_40px_rgba(245,197,66,0.25)]'
                : rank === 2
                  ? 'bg-[var(--primary)]/85 text-[var(--primary-foreground)]'
                  : 'bg-[var(--secondary)] text-[var(--foreground)]'

            return (
              <div
                key={rank}
                data-testid={`podium-rank-${rank}`}
                className={cn(
                  'flex w-28 flex-col items-center gap-3 sm:w-36 lg:w-44',
                  rank === 1 && 'relative z-10 scale-105',
                )}
              >
                <span className="text-4xl lg:text-5xl">{MEDALS[rank]}</span>
                <p className="truncate text-center font-display text-lg font-semibold text-[#f0f4fa] lg:text-2xl">
                  {entry?.displayName ?? '—'}
                </p>
                <p className="text-sm text-[var(--muted-foreground)] lg:text-base">
                  {entry != null ? `${entry.score} pts` : ''}
                </p>
                <div
                  className={cn(
                    'flex w-full flex-col items-center justify-start rounded-t-2xl pt-4 font-display text-4xl font-bold lg:text-5xl',
                    height,
                    accent,
                  )}
                >
                  {rank}
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <p className="text-center text-lg text-[var(--muted-foreground)]">
          Final rankings are loading…
        </p>
      )}

      {sessionHighlights?.fastestAnswer ? (
        <div
          className="mx-auto w-full max-w-2xl rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-6 py-4 text-center"
          data-testid="fastest-answer"
        >
          <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
            Fastest answer
          </p>
          <p className="mt-1 font-display text-xl text-[#f0f4fa]">
            {sessionHighlights.fastestAnswer.displayName} —{' '}
            {formatMs(sessionHighlights.fastestAnswer.responseTimeMs)}
          </p>
        </div>
      ) : null}

      {(sessionHighlights?.hardestQuestion || sessionHighlights?.mostMissedQuestion) && (
        <div className="mx-auto grid w-full max-w-3xl gap-4 sm:grid-cols-2">
          {sessionHighlights.hardestQuestion ? (
            <div
              className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-5 py-4"
              data-testid="hardest-question"
            >
              <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
                Hardest question
              </p>
              <p className="mt-2 line-clamp-2 text-[#f0f4fa]">
                {sessionHighlights.hardestQuestion.promptText ?? 'Question'}
              </p>
              <p className="mt-1 text-sm text-[var(--destructive)]">
                {sessionHighlights.hardestQuestion.accuracyPercent}% accuracy
              </p>
            </div>
          ) : null}
          {sessionHighlights.mostMissedQuestion ? (
            <div
              className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-5 py-4"
              data-testid="most-missed-question"
            >
              <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
                Most missed
              </p>
              <p className="mt-2 line-clamp-2 text-[#f0f4fa]">
                {sessionHighlights.mostMissedQuestion.promptText ?? 'Question'}
              </p>
              <p className="mt-1 text-sm text-[var(--destructive)]">
                {sessionHighlights.mostMissedQuestion.missPercent ??
                  100 - sessionHighlights.mostMissedQuestion.accuracyPercent}
                % miss rate
              </p>
            </div>
          ) : null}
        </div>
      )}

      {finalList.length > 0 ? (
        <div className="relative mx-auto w-full max-w-3xl">
          <p className="mb-3 text-center text-xs uppercase tracking-[0.25em] text-[var(--muted-foreground)]">
            Top 10 final rankings
          </p>
          <ol className="space-y-2">
            {finalList.slice(0, 10).map((entry) => (
              <li
                key={entry.participantId}
                className="flex items-center justify-between rounded-xl border border-[var(--border)]/80 bg-[var(--card)]/60 px-4 py-3"
              >
                <span className="flex min-w-0 items-center gap-3">
                  <span className="w-8 font-display font-bold text-[var(--primary)]">
                    #{entry.rank}
                  </span>
                  <span className="truncate text-[#f0f4fa]">{entry.displayName}</span>
                </span>
                <span className="font-medium text-[var(--accent)]">{entry.score}</span>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      <style>{`
        @keyframes confetti-fall {
          0% { transform: translateY(-10vh) rotate(0deg); opacity: 1; }
          100% { transform: translateY(110vh) rotate(720deg); opacity: 0; }
        }
        .display-confetti::before,
        .display-confetti::after {
          content: '';
          position: absolute;
          inset: 0;
          background-image:
            radial-gradient(circle, var(--accent) 2px, transparent 2px),
            radial-gradient(circle, var(--primary) 2px, transparent 2px),
            radial-gradient(circle, var(--color-cyan-mint) 2px, transparent 2px);
          background-size: 80px 80px, 120px 120px, 100px 100px;
          background-position: 0 0, 40px 40px, 20px 60px;
          animation: confetti-fall 6s linear infinite;
          opacity: 0.35;
        }
        .display-confetti::after {
          animation-duration: 8s;
          animation-delay: 1s;
          opacity: 0.25;
        }
      `}</style>
    </section>
  )
}
