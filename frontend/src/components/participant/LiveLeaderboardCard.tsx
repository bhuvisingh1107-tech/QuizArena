import type { LeaderboardEntry } from '@/types/api'
import { cn } from '@/lib/utils'

interface LiveLeaderboardCardProps {
  yourRank: number | null
  yourScore: number
  leaderboard: LeaderboardEntry[]
  topN?: number
  className?: string
}

export function LiveLeaderboardCard({
  yourRank,
  yourScore,
  leaderboard,
  topN = 5,
  className,
}: LiveLeaderboardCardProps) {
  const top = leaderboard.slice(0, topN)

  return (
    <section
      className={cn(
        'rounded-xl border border-[var(--border)] bg-[var(--card)]/80 p-4',
        className,
      )}
      aria-label="Live leaderboard"
    >
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">
            Your standing
          </p>
          <p className="font-display text-2xl font-bold text-[#f0f4fa]">
            {yourRank != null ? `#${yourRank}` : '—'}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">
            Score
          </p>
          <p className="font-display text-2xl font-bold text-[var(--accent)]">{yourScore}</p>
        </div>
      </div>

      {top.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">Leaderboard updates after scoring.</p>
      ) : (
        <ol className="space-y-2">
          {top.map((entry) => (
            <li
              key={entry.participantId}
              className="flex items-center justify-between gap-3 rounded-lg bg-[var(--secondary)]/60 px-3 py-2 text-sm"
            >
              <span className="flex min-w-0 items-center gap-2">
                <span className="w-6 shrink-0 font-display font-semibold text-[var(--primary)]">
                  {entry.rank}
                </span>
                <span className="truncate text-[#f0f4fa]">{entry.displayName}</span>
              </span>
              <span className="shrink-0 font-medium text-[var(--accent)]">{entry.score}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
