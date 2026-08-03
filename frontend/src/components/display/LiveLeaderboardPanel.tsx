import { memo, useMemo } from 'react'

import type { LeaderboardEntry } from '@/types/api'
import { cn } from '@/lib/utils'

interface LiveLeaderboardPanelProps {
  leaderboard: LeaderboardEntry[]
  previousRanks?: Record<string, number>
  title?: string
  className?: string
  /** When true, omit top-3 medal styling (mid-quiz panel). */
  compactMedals?: boolean
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

export const LiveLeaderboardPanel = memo(function LiveLeaderboardPanel({
  leaderboard,
  previousRanks = {},
  title = 'Live Leaderboard',
  className,
  compactMedals = true,
}: LiveLeaderboardPanelProps) {
  const biggestClimber = useMemo(
    () => findBiggestClimber(leaderboard, previousRanks),
    [leaderboard, previousRanks],
  )

  return (
    <aside
      className={cn(
        'flex h-full min-h-0 w-full flex-col rounded-2xl border border-[var(--border)]/80 bg-[var(--card)]/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] backdrop-blur-sm',
        className,
      )}
      aria-label="Live leaderboard"
      data-testid="live-leaderboard-panel"
    >
      <div className="border-b border-[var(--border)]/70 px-4 py-3 lg:px-5 lg:py-4">
        <p className="text-[0.65rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted-foreground)]">
          Standings
        </p>
        <h2 className="mt-1 font-display text-xl font-bold text-[#f0f4fa] lg:text-2xl">
          {title}
        </h2>
        <div className="mt-3 grid grid-cols-[2.25rem_minmax(0,1fr)_3.25rem_3.5rem_2.75rem] gap-2 text-[0.65rem] uppercase tracking-wide text-[var(--muted-foreground)]">
          <span>Rank</span>
          <span>Name</span>
          <span className="text-right">Score</span>
          <span className="text-right">Bonus</span>
          <span className="text-right">Streak</span>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2 lg:px-3 lg:py-3">
        {leaderboard.length === 0 ? (
          <p className="px-3 py-8 text-center text-sm text-[var(--muted-foreground)]">
            Rankings update live as answers come in.
          </p>
        ) : (
          <ol className="space-y-1.5">
            {leaderboard.map((entry, index) => {
              const prev = previousRanks[entry.participantId]
              const delta = typeof prev === 'number' ? prev - entry.rank : 0
              const movedUp = delta > 0
              const movedDown = delta < 0
              const isClimber = entry.participantId === biggestClimber && delta > 0
              const timeBonus = entry.lastTimeBonus ?? entry.timeBonus ?? 0

              return (
                <li
                  key={entry.participantId}
                  data-testid={`live-lb-row-${entry.rank}`}
                  data-rank-delta={delta !== 0 ? delta : undefined}
                  className={cn(
                    'live-lb-row grid grid-cols-[2.25rem_minmax(0,1fr)_3.25rem_3.5rem_2.75rem] items-center gap-2 rounded-xl border px-2.5 py-2.5 transition-all duration-500 lg:px-3',
                    entry.rank === 1 && !compactMedals
                      ? 'border-[#f5c542]/50 bg-[linear-gradient(90deg,rgba(245,197,66,0.14),transparent)]'
                      : 'border-transparent bg-[var(--secondary)]/45',
                    movedUp && 'border-[var(--color-success)]/35 bg-[var(--color-success)]/10',
                    movedDown && 'border-[var(--destructive)]/25',
                    isClimber && 'ring-1 ring-[var(--color-success)]/50',
                  )}
                  style={{
                    animationDelay: `${Math.min(index, 12) * 35}ms`,
                    transform: movedUp
                      ? 'translateY(-2px)'
                      : movedDown
                        ? 'translateY(2px)'
                        : undefined,
                  }}
                >
                  <span
                    className={cn(
                      'font-display text-sm font-bold',
                      entry.rank <= 3 ? 'text-[var(--accent)]' : 'text-[var(--muted-foreground)]',
                    )}
                  >
                    {entry.rank}
                  </span>
                  <span className="truncate font-medium text-[#f0f4fa]">
                    {entry.displayName}
                    {movedUp ? (
                      <span className="ml-1 text-xs text-[var(--color-success)]">↑{delta}</span>
                    ) : null}
                    {movedDown ? (
                      <span className="ml-1 text-xs text-[var(--destructive)]">
                        ↓{Math.abs(delta)}
                      </span>
                    ) : null}
                  </span>
                  <span className="text-right font-display font-semibold text-[var(--accent)]">
                    {entry.score}
                  </span>
                  <span className="text-right text-sm text-[#f0f4fa]/90">+{timeBonus}</span>
                  <span className="text-right text-sm text-[var(--muted-foreground)]">
                    {entry.streak ?? 0}
                  </span>
                </li>
              )
            })}
          </ol>
        )}
      </div>

      <style>{`
        @keyframes live-lb-in {
          from { opacity: 0; transform: translateX(8px); }
          to { opacity: 1; transform: translateX(0); }
        }
        .live-lb-row {
          animation: live-lb-in 380ms ease-out both;
        }
      `}</style>
    </aside>
  )
})
