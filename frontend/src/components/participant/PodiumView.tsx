import type { Podium } from '@/types/api'
import { cn } from '@/lib/utils'

interface PodiumViewProps {
  podium: Podium | null
  className?: string
}

const ORDER: Array<1 | 2 | 3> = [2, 1, 3]

export function PodiumView({ podium, className }: PodiumViewProps) {
  const byRank = new Map(podium?.entries.map((e) => [e.rank, e]) ?? [])

  if (!podium?.entries.length) {
    return (
      <div
        className={cn(
          'rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)]/40 px-4 py-10 text-center text-sm text-[var(--muted-foreground)]',
          className,
        )}
      >
        Podium will appear when final results are ready.
      </div>
    )
  }

  return (
    <section className={cn('space-y-4', className)} aria-label="Podium">
      <h2 className="font-display text-center text-xl font-semibold text-[#f0f4fa]">Podium</h2>
      <div className="flex items-end justify-center gap-3 pt-2">
        {ORDER.map((rank) => {
          const entry = byRank.get(rank)
          const height = rank === 1 ? 'h-28' : rank === 2 ? 'h-20' : 'h-16'
          const accent =
            rank === 1
              ? 'bg-[var(--accent)] text-[var(--accent-foreground)]'
              : rank === 2
                ? 'bg-[var(--primary)]/80 text-[var(--primary-foreground)]'
                : 'bg-[var(--secondary)] text-[var(--foreground)]'

          return (
            <div key={rank} className="flex w-24 flex-col items-center gap-2 sm:w-28">
              <p className="truncate text-center text-sm font-medium text-[#f0f4fa]">
                {entry?.displayName ?? '—'}
              </p>
              <p className="text-xs text-[var(--muted-foreground)]">
                {entry != null ? `${entry.score} pts` : ''}
              </p>
              <div
                className={cn(
                  'flex w-full flex-col items-center justify-start rounded-t-xl pt-3 font-display text-2xl font-bold',
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
    </section>
  )
}
