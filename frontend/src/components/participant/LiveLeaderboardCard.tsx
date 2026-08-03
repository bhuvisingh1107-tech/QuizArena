import { memo } from 'react'

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

export const LiveLeaderboardCard = memo(function LiveLeaderboardCard({
  yourRank,
  yourScore,
  leaderboard,
  previousRanks = {},
  selfParticipantId,
  topN = 5,
  title = 'Live leaderboard',
  compact = false,
  className,
}: LiveLeaderboardCardProps) {
  const top = leaderboard.slice(0, topN)

  return (
    <section
      className={cn(
        'flex h-full flex-col rounded-xl border border-[var(--border)] bg-[var(--card)]/80 p-4',
        className,
      )}
      aria-label="Live leaderboard"
      data-testid="participant-live-leaderboard"
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

      <div className="mb-2 grid grid-cols-[1.75rem_minmax(0,1fr)_2.75rem_2.5rem_2.25rem] gap-2 text-[0.65rem] uppercase tracking-wide text-[var(--muted-foreground)]">
        <span>#</span>
        <span>Name</span>
        <span className="text-right">Score</span>
        <span className="text-right">Bonus</span>
        <span className="text-right">Streak</span>
      </div>

      {top.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">
          Rankings update live after each answer.
        </p>
      ) : (
        <ol className="min-h-0 flex-1 space-y-2 overflow-y-auto">
          {top.map((entry) => {
            const isSelf = selfParticipantId === entry.participantId
            const prev = previousRanks[entry.participantId]
            const delta = typeof prev === 'number' ? prev - entry.rank : 0
            const movedUp = delta > 0
            const movedDown = delta < 0
            const timeBonus = entry.lastTimeBonus ?? entry.timeBonus ?? 0

            return (
              <li
                key={entry.participantId}
                className={cn(
                  'grid grid-cols-[1.75rem_minmax(0,1fr)_2.75rem_2.5rem_2.25rem] items-center gap-2 rounded-lg px-2 py-2 text-sm transition-all duration-500',
                  isSelf
                    ? 'border border-[var(--primary)]/50 bg-[var(--primary)]/15'
                    : 'bg-[var(--secondary)]/60',
                  movedUp && 'border-[var(--color-success)]/30',
                  movedDown && 'border-[var(--destructive)]/20',
                )}
                style={{
                  transform: movedUp
                    ? 'translateY(-2px)'
                    : movedDown
                      ? 'translateY(2px)'
                      : undefined,
                }}
              >
                <span
                  className={cn(
                    'font-display font-semibold',
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
                  {movedUp ? (
                    <span className="ml-1 text-xs text-[var(--color-success)]">↑{delta}</span>
                  ) : null}
                  {movedDown ? (
                    <span className="ml-1 text-xs text-[var(--destructive)]">
                      ↓{Math.abs(delta)}
                    </span>
                  ) : null}
                </span>
                <span className="text-right font-medium text-[var(--accent)]">{entry.score}</span>
                <span className="text-right text-xs text-[#f0f4fa]/90">+{timeBonus}</span>
                <span className="text-right text-xs text-[var(--muted-foreground)]">
                  {entry.streak ?? 0}
                </span>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
})
