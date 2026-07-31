import { LeaderboardScreen } from '@/components/display/LeaderboardScreen'
import type { DisplaySection } from '@/hooks/displayLiveReducer'
import type { LeaderboardEntry } from '@/types/api'
import { cn } from '@/lib/utils'

interface SectionBreakScreenProps {
  section: DisplaySection | null
  leaderboard: LeaderboardEntry[]
  previousRanks?: Record<string, number>
  className?: string
}

export function SectionBreakScreen({
  section,
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
        <h1 className="mt-3 font-display text-4xl font-extrabold text-[#f0f4fa] lg:text-6xl">
          {name}
        </h1>
        <p className="mt-3 text-base text-[var(--muted-foreground)] lg:text-lg">
          Waiting for the next section…
        </p>
      </div>

      <LeaderboardScreen
        leaderboard={leaderboard}
        previousRanks={previousRanks}
        title="Section standings"
        topN={8}
      />
    </section>
  )
}
