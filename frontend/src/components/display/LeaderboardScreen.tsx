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

function findBiggestClimber(
  rows: LeaderboardEntry[],
  previousRanks: Record<string, number>,
): string | null {
  let bestId: string | null = null
  let bestDelta = 0
  for (const entry of rows) {
    const prev = previousRanks[entry.participantId]
    if (typeof prev !== 'number') continue
    const delta = prev - entry.rank
    if (delta > bestDelta) {
      bestDelta = delta
      bestId = entry.participantId
    }
  }
  return bestId
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
  const biggestClimber = findBiggestClimber(rows, previousRanks)

  return (
    <section
      className={cn('flex flex-1 flex-col gap-6', className)}
      aria-label="Leaderboard"
    >
      <div className="text-center">
        <h1
          className="font-display font-extrabold text-[#f0f4fa]"
          style={{ fontSize: 'clamp(2rem, 5vw, 4rem)' }}
        >
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
          {rows.map((entry, index) => {
            const prev = previousRanks[entry.participantId]
            const delta =
              typeof prev === 'number' ? prev - entry.rank : 0
            const movedUp = delta > 0
            const movedDown = delta < 0
            const isClimber = entry.participantId === biggestClimber && delta > 0

            return (
              <li
                key={entry.participantId}
                data-testid={`leaderboard-row-${entry.rank}`}
                data-rank-delta={delta !== 0 ? delta : undefined}
                data-biggest-climber={isClimber ? 'true' : undefined}
                className={cn(
                  'leaderboard-row-enter flex items-center justify-between gap-4 rounded-2xl border border-[var(--border)] bg-[var(--card)]/80 px-5 py-4 transition-all duration-500 lg:px-8 lg:py-5',
                  movedUp && 'border-[var(--color-success)]/40 bg-[var(--color-success)]/10',
                  movedDown && 'border-[var(--destructive)]/30 bg-[var(--destructive)]/5',
                  entry.rank === 1 &&
                    'border-[var(--accent)]/50 shadow-[0_0_28px_rgba(245,197,66,0.12)]',
                  isClimber &&
                    'ring-2 ring-[var(--color-success)]/60 shadow-[0_0_32px_rgba(34,197,94,0.15)]',
                )}
                style={{
                  animationDelay: `${index * 60}ms`,
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
                  <div className="min-w-0">
                    <span
                      className="block truncate font-display font-semibold text-[#f0f4fa]"
                      style={{ fontSize: 'clamp(1.125rem, 2.5vw, 1.875rem)' }}
                    >
                      {entry.displayName}
                    </span>
                    {typeof entry.streak === 'number' && entry.streak > 0 ? (
                      <span className="text-sm text-[var(--accent)]">
                        🔥 {entry.streak} streak
                      </span>
                    ) : null}
                  </div>
                  {movedUp ? (
                    <span
                      className="hidden shrink-0 text-sm font-semibold text-[var(--color-success)] sm:inline"
                      data-testid={`rank-up-${entry.rank}`}
                    >
                      ↑ {delta}
                    </span>
                  ) : null}
                  {movedDown ? (
                    <span className="hidden shrink-0 text-sm text-[var(--destructive)] sm:inline">
                      ↓ {Math.abs(delta)}
                    </span>
                  ) : null}
                  {isClimber ? (
                    <span className="hidden rounded-full bg-[var(--color-success)]/20 px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-[var(--color-success)] sm:inline">
                      Biggest climb
                    </span>
                  ) : null}
                </div>
                <span
                  className="shrink-0 font-display font-bold text-[var(--accent)]"
                  style={{ fontSize: 'clamp(1.25rem, 2.5vw, 1.875rem)' }}
                >
                  {entry.score}
                </span>
              </li>
            )
          })}
        </ol>
      )}

      <style>{`
        @keyframes leaderboard-row-in {
          from { opacity: 0; transform: translateX(-12px); }
          to { opacity: 1; transform: translateX(0); }
        }
        .leaderboard-row-enter {
          animation: leaderboard-row-in 450ms ease-out both;
        }
      `}</style>
    </section>
  )
}
