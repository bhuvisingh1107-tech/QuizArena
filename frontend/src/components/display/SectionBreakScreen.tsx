import { LeaderboardScreen } from '@/components/display/LeaderboardScreen'
import type {
  DisplaySection,
  DisplaySectionStats,
} from '@/hooks/displayLiveReducer'
import type { LeaderboardEntry } from '@/types/api'
import { cn } from '@/lib/utils'

interface SectionBreakScreenProps {
  section: DisplaySection | null
  top3: LeaderboardEntry[]
  sectionStats: DisplaySectionStats | null
  leaderboard: LeaderboardEntry[]
  previousRanks?: Record<string, number>
  className?: string
}

const MEDALS = ['1st', '2nd', '3rd'] as const

export function SectionBreakScreen({
  section,
  top3,
  sectionStats,
  leaderboard,
  previousRanks,
  className,
}: SectionBreakScreenProps) {
  const name = section?.name ?? 'Section'

  return (
    <section
      className={cn('flex flex-1 flex-col gap-8', className)}
      aria-label="Section break"
    >
      <div className="text-center">
        <p className="text-sm uppercase tracking-[0.3em] text-[var(--primary)] lg:text-base">
          Section completed
        </p>
        <h1
          className="mt-3 font-display font-extrabold text-[var(--heading)]"
          style={{ fontSize: 'clamp(2rem, 5vw, 4rem)' }}
        >
          {name}
        </h1>
        <p className="mt-3 text-base text-[var(--muted-foreground)] lg:text-lg">
          Waiting for the next section…
        </p>
      </div>

      {sectionStats ? (
        <div
          className="mx-auto grid w-full max-w-3xl gap-4 sm:grid-cols-3"
          data-testid="section-stats"
        >
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/70 px-5 py-4 text-center">
            <p className="text-xs uppercase tracking-wider text-[var(--muted-foreground)]">
              Avg accuracy
            </p>
            <p className="mt-1 font-display text-3xl font-bold text-[var(--color-success)]">
              {sectionStats.averageAccuracy}%
            </p>
          </div>
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/70 px-5 py-4 text-center">
            <p className="text-xs uppercase tracking-wider text-[var(--muted-foreground)]">
              Questions
            </p>
            <p className="mt-1 font-display text-3xl font-bold text-[var(--primary)]">
              {sectionStats.questionCount}
            </p>
          </div>
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/70 px-5 py-4 text-center">
            <p className="text-xs uppercase tracking-wider text-[var(--muted-foreground)]">
              Players
            </p>
            <p className="mt-1 font-display text-3xl font-bold text-[var(--accent)]">
              {sectionStats.participantCount}
            </p>
          </div>
        </div>
      ) : null}

      {top3.length > 0 ? (
        <div
          className="mx-auto flex w-full max-w-3xl flex-wrap items-end justify-center gap-6"
          data-testid="section-top3"
        >
          {top3.slice(0, 3).map((entry, index) => (
            <div
              key={entry.participantId}
              data-testid={`section-top-${entry.rank}`}
              className={cn(
                'flex w-36 flex-col items-center gap-2 rounded-2xl border border-[var(--border)] bg-[var(--card)]/80 px-4 py-5 text-center',
                entry.rank === 1 && 'scale-105 border-[var(--accent)]/50',
              )}
            >
              <span className="text-4xl">{MEDALS[index] ?? `#${entry.rank}`}</span>
              <p className="truncate font-display text-lg font-semibold text-[#f0f4fa]">
                {entry.displayName}
              </p>
              <p className="font-display text-xl font-bold text-[var(--accent)]">
                {entry.score}
              </p>
            </div>
          ))}
        </div>
      ) : null}

      <LeaderboardScreen
        leaderboard={leaderboard}
        previousRanks={previousRanks}
        title="Section standings"
        topN={10}
      />
    </section>
  )
}
