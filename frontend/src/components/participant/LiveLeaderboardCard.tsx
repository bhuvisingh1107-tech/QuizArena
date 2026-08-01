import type { LeaderboardEntry } from '@/types/api'
import { cn } from '@/lib/utils'

interface LiveLeaderboardCardProps {
  yourRank: number | null
  yourScore: number
  leaderboard: LeaderboardEntry[]
  previousRanks?: Record<string, number>
  selfParticipantId?: string | null
  topN?: number
  title?: string
  compact?: boolean
  className?: string
}

export function LiveLeaderboardCard({
  yourRank,
  yourScore,
  leaderboard,
  previousRanks = {},
  selfParticipantId,
  topN = 5,
  title = 'Your standing',
  compact = false,
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
      {!compact ? (
        <div className="mb-3 flex items-end justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">
              {title}
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
      ) : null}

      {top.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">
          Leaderboard updates after scoring.
        </p>
      ) : (
        <ol className="space-y-2">
          {top.map((entry) => {
            const isSelf = selfParticipantId === entry.participantId
            const prev = previousRanks[entry.participantId]
            const delta = typeof prev === 'number' ? prev - entry.rank : 0
            const movedUp = delta > 0
            const movedDown = delta < 0

            return (
              <li
                key={entry.participantId}
                className={cn(
                  'flex items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-500',
                  isSelf
                    ? 'border border-[var(--primary)]/50 bg-[var(--primary)]/15'
                    : 'bg-[var(--secondary)]/60',
                  movedUp && 'border-[var(--color-success)]/30',
                  movedDown && 'border-[var(--destructive)]/20',
                )}
                style={{
                  transform: movedUp
                    ? 'translateY(-1px)'
                    : movedDown
                      ? 'translateY(1px)'
                      : undefined,
                }}
              >
                <span className="flex min-w-0 flex-1 items-center gap-2">
                  <span
                    className={cn(
                      'w-6 shrink-0 font-display font-semibold',
                      entry.rank === 1
                        ? 'text-[var(--accent)]'
                        : 'text-[var(--primary)]',
                    )}
                  >
                    {entry.rank}
                  </span>
                  <span className="truncate text-[#f0f4fa]">
                    {entry.displayName}
                    {isSelf ? (
                      <span className="ml-1 text-xs text-[var(--primary)]">(you)</span>
                    ) : null}
                  </span>
                  {movedUp ? (
                    <span className="shrink-0 text-xs text-[var(--color-success)]">↑{delta}</span>
                  ) : null}
                  {movedDown ? (
                    <span className="shrink-0 text-xs text-[var(--destructive)]">
                      ↓{Math.abs(delta)}
                    </span>
                  ) : null}
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  {typeof entry.streak === 'number' && entry.streak > 0 ? (
                    <span className="text-xs text-[var(--accent)]">🔥{entry.streak}</span>
                  ) : null}
                  <span className="font-medium text-[var(--accent)]">{entry.score}</span>
                </span>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
