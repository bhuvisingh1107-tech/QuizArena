import type { LeaderboardEntry } from '@/types/api'
import { cn } from '@/lib/utils'

interface LeaderboardScreenProps {
  leaderboard: LeaderboardEntry[]
  previousRanks?: Record<string, number>
  title?: string
  subtitle?: string
  topN?: number
  className?: string
}

export function LeaderboardScreen({
  leaderboard,
  previousRanks = {},
  title = 'Leaderboard',
  subtitle,
  topN = 10,
  className,
}: LeaderboardScreenProps) {
  const rows = leaderboard.slice(0, topN)

  return (
    <section
      className={cn('flex flex-1 flex-col gap-6', className)}
      aria-label="Leaderboard"
    >
      <div className="text-center">
        <h1 className="font-display text-4xl font-extrabold text-[#f0f4fa] lg:text-6xl">
          {title}
        </h1>
        {subtitle ? (
          <p className="mt-2 text-base text-[var(--muted-foreground)] lg:text-lg">{subtitle}</p>
        ) : null}
      </div>

      {rows.length === 0 ? (
        <p className="mx-auto mt-10 max-w-xl text-center text-lg text-[var(--muted-foreground)]">
          Rankings appear after the first scored question.
        </p>
      ) : (
        <ol className="mx-auto w-full max-w-4xl space-y-3">
          {rows.map((entry) => {
            const prev = previousRanks[entry.participantId]
            const delta =
              typeof prev === 'number' ? prev - entry.rank : 0
            const movedUp = delta > 0
            const movedDown = delta < 0

            return (
              <li
                key={entry.participantId}
                data-testid={`leaderboard-row-${entry.rank}`}
                data-rank-delta={delta !== 0 ? delta : undefined}
                className={cn(
                  'flex items-center justify-between gap-4 rounded-2xl border border-[var(--border)] bg-[var(--card)]/80 px-5 py-4 transition-all duration-500 lg:px-8 lg:py-5',
                  movedUp && 'border-[var(--color-success)]/40 bg-[var(--color-success)]/10',
                  movedDown && 'border-[var(--destructive)]/30 bg-[var(--destructive)]/5',
                  entry.rank === 1 && 'border-[var(--accent)]/50 shadow-[0_0_28px_rgba(245,197,66,0.12)]',
                )}
                style={{
                  transform: movedUp
                    ? 'translateY(-2px)'
                    : movedDown
                      ? 'translateY(2px)'
                      : undefined,
                }}
              >
                <div className="flex min-w-0 items-center gap-4 lg:gap-6">
                  <span
                    className={cn(
                      'flex h-12 w-12 shrink-0 items-center justify-center rounded-xl font-display text-xl font-bold lg:h-14 lg:w-14 lg:text-2xl',
                      entry.rank === 1
                        ? 'bg-[var(--accent)] text-[var(--accent-foreground)]'
                        : entry.rank <= 3
                          ? 'bg-[var(--primary)]/25 text-[var(--primary)]'
                          : 'bg-[var(--secondary)] text-[var(--muted-foreground)]',
                    )}
                  >
                    {entry.rank}
                  </span>
                  <span className="truncate font-display text-xl font-semibold text-[#f0f4fa] lg:text-3xl">
                    {entry.displayName}
                  </span>
                  {movedUp ? (
                    <span className="hidden text-sm text-[var(--color-success)] sm:inline">
                      ↑ {delta}
                    </span>
                  ) : null}
                  {movedDown ? (
                    <span className="hidden text-sm text-[var(--destructive)] sm:inline">
                      ↓ {Math.abs(delta)}
                    </span>
                  ) : null}
                </div>
                <span className="shrink-0 font-display text-2xl font-bold text-[var(--accent)] lg:text-3xl">
                  {entry.score}
                </span>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
