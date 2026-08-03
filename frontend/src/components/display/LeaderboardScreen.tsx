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

function medalForRank(rank: number): string | null {
  if (rank === 1) return '🥇'
  if (rank === 2) return '🥈'
  if (rank === 3) return '🥉'
  return null
}

function rowTone(entry: LeaderboardEntry): string {
  if (entry.rank === 1) {
    return 'border-[#f5c542]/60 bg-[linear-gradient(90deg,rgba(245,197,66,0.18),transparent)]'
  }
  if (entry.rank === 2) {
    return 'border-[#c0c7d1]/50 bg-[linear-gradient(90deg,rgba(192,199,209,0.16),transparent)]'
  }
  if (entry.rank === 3) {
    return 'border-[#cd7f32]/50 bg-[linear-gradient(90deg,rgba(205,127,50,0.16),transparent)]'
  }
  if (entry.lastIsCorrect === false) {
    return 'border-[var(--destructive)]/45 bg-[var(--destructive)]/10'
  }
  const bonus = entry.lastTimeBonus ?? entry.timeBonus
  if (typeof bonus === 'number') {
    if (bonus >= 8) return 'border-emerald-400/45 bg-emerald-500/10'
    if (bonus >= 4) return 'border-amber-300/45 bg-amber-400/10'
    if (bonus > 0) return 'border-orange-400/45 bg-orange-500/10'
  }
  if ((entry.streak ?? 0) >= 3) return 'border-emerald-400/35 bg-emerald-500/5'
  return 'border-[var(--border)] bg-[var(--card)]/80'
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
        <div className="mt-3 flex flex-wrap items-center justify-center gap-4 text-xs uppercase tracking-wide text-[var(--muted-foreground)]">
          <span>Rank</span>
          <span>Name</span>
          <span>Score</span>
          <span>Time bonus</span>
          <span>Streak</span>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="mx-auto mt-10 max-w-xl text-center text-lg text-[var(--muted-foreground)]">
          Rankings appear after the first scored question.
        </p>
      ) : (
        <ol className="mx-auto w-full max-w-4xl space-y-3">
          {rows.map((entry, index) => {
            const prev = previousRanks[entry.participantId]
            const delta = typeof prev === 'number' ? prev - entry.rank : 0
            const movedUp = delta > 0
            const movedDown = delta < 0
            const isClimber = entry.participantId === biggestClimber && delta > 0
            const medal = medalForRank(entry.rank)
            const timeBonus = entry.lastTimeBonus ?? entry.timeBonus ?? 0

            return (
              <li
                key={entry.participantId}
                data-testid={`leaderboard-row-${entry.rank}`}
                data-rank-delta={delta !== 0 ? delta : undefined}
                data-biggest-climber={isClimber ? 'true' : undefined}
                className={cn(
                  'leaderboard-row-enter flex items-center justify-between gap-4 rounded-2xl border px-5 py-4 transition-all duration-500 lg:px-8 lg:py-5',
                  rowTone(entry),
                  movedUp && 'translate-y-[-2px]',
                  movedDown && 'translate-y-[2px]',
                  isClimber && 'ring-2 ring-[var(--color-success)]/60',
                )}
                style={{ animationDelay: `${index * 60}ms` }}
              >
                <div className="flex min-w-0 items-center gap-4 lg:gap-6">
                  <span
                    className={cn(
                      'flex h-12 w-12 shrink-0 items-center justify-center rounded-xl font-display text-xl font-bold lg:h-14 lg:w-14 lg:text-2xl',
                      entry.rank === 1 && 'bg-[#f5c542] text-[#1a1408]',
                      entry.rank === 2 && 'bg-[#c0c7d1] text-[#1a1f28]',
                      entry.rank === 3 && 'bg-[#cd7f32] text-[#1a1208]',
                      entry.rank > 3 && 'bg-[var(--secondary)] text-[var(--muted-foreground)]',
                    )}
                    aria-label={`Rank ${entry.rank}`}
                  >
                    {medal ?? entry.rank}
                  </span>
                  <div className="min-w-0">
                    <span
                      className="block truncate font-display font-semibold text-[#f0f4fa]"
                      style={{ fontSize: 'clamp(1.125rem, 2.5vw, 1.875rem)' }}
                    >
                      {entry.displayName}
                    </span>
                    <div className="mt-1 flex flex-wrap items-center gap-3 text-sm">
                      <span className="text-[var(--muted-foreground)]">
                        Streak{' '}
                        <strong className="text-[var(--accent)]">{entry.streak ?? 0}</strong>
                      </span>
                      <span className="text-[var(--muted-foreground)]">
                        Time bonus{' '}
                        <strong className="text-[#f0f4fa]">+{timeBonus}</strong>
                      </span>
                      {entry.lastIsCorrect === false ? (
                        <span className="font-medium text-[var(--destructive)]">Incorrect</span>
                      ) : null}
                    </div>
                  </div>
                  {movedUp ? (
                    <span className="hidden shrink-0 text-sm font-semibold text-[var(--color-success)] sm:inline">
                      ↑ {delta}
                    </span>
                  ) : null}
                  {movedDown ? (
                    <span className="hidden shrink-0 text-sm text-[var(--destructive)] sm:inline">
                      ↓ {Math.abs(delta)}
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
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .leaderboard-row-enter {
          animation: leaderboard-row-in 450ms ease-out both;
        }
      `}</style>
    </section>
  )
}
