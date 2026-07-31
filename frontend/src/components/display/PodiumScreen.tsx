import type { LeaderboardEntry, Podium } from '@/types/api'
import { cn } from '@/lib/utils'

interface PodiumScreenProps {
  podium: Podium | null
  leaderboard?: LeaderboardEntry[]
  quizTitle?: string
  className?: string
}

const ORDER: Array<1 | 2 | 3> = [2, 1, 3]

export function PodiumScreen({
  podium,
  leaderboard = [],
  quizTitle,
  className,
}: PodiumScreenProps) {
  const byRank = new Map(podium?.entries.map((e) => [e.rank, e]) ?? [])
  const hasPodium = Boolean(podium?.entries.length)
  const finalList =
    leaderboard.length > 0
      ? leaderboard
      : (podium?.entries.map((e) => ({
          rank: e.rank,
          participantId: e.participantId,
          displayName: e.displayName,
          score: e.score,
        })) ?? [])

  return (
    <section
      className={cn('flex flex-1 flex-col gap-8', className)}
      aria-label="Final podium"
    >
      <div className="text-center">
        <p className="text-sm uppercase tracking-[0.3em] text-[var(--accent)] lg:text-base">
          Quiz completed
        </p>
        <h1 className="mt-3 font-display text-4xl font-extrabold text-[#f0f4fa] lg:text-6xl">
          {quizTitle ? `${quizTitle}` : 'Final results'}
        </h1>
        <p className="mt-2 text-base text-[var(--muted-foreground)] lg:text-lg">
          Congratulations to all players!
        </p>
      </div>

      {hasPodium ? (
        <div className="flex items-end justify-center gap-4 pt-4 lg:gap-8" data-testid="podium-top3">
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

      {finalList.length > 0 ? (
        <div className="mx-auto w-full max-w-3xl">
          <p className="mb-3 text-center text-xs uppercase tracking-[0.25em] text-[var(--muted-foreground)]">
            Final rankings
          </p>
          <ol className="space-y-2">
            {finalList.slice(0, 12).map((entry) => (
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
    </section>
  )
}
