import { computeAccuracyPercent } from '@/hooks/participantLiveReducer'
import { cn } from '@/lib/utils'

export interface ResultsSummaryProps {
  displayName: string
  rank: number | null | undefined
  score: number
  correct: number
  incorrect: number
  unanswered?: number
  className?: string
}

export function ResultsSummary({
  displayName,
  rank,
  score,
  correct,
  incorrect,
  unanswered = 0,
  className,
}: ResultsSummaryProps) {
  const accuracy = computeAccuracyPercent(correct, incorrect)

  return (
    <section
      className={cn(
        'rounded-xl border border-[var(--border)] bg-[var(--card)]/90 p-5',
        className,
      )}
      aria-label="Your results"
    >
      <p className="text-sm text-[var(--muted-foreground)]">Nice work,</p>
      <h2 className="font-display text-2xl font-bold text-[#f0f4fa]">{displayName}</h2>

      <div className="mt-5 grid grid-cols-2 gap-3">
        <Stat label="Rank" value={rank != null ? `#${rank}` : '—'} accent />
        <Stat label="Score" value={String(score)} accent />
        <Stat label="Correct" value={String(correct)} />
        <Stat label="Incorrect" value={String(incorrect)} />
        <Stat label="Unanswered" value={String(unanswered)} />
        <Stat label="Accuracy" value={`${accuracy}%`} />
      </div>
    </section>
  )
}

function Stat({
  label,
  value,
  accent = false,
}: {
  label: string
  value: string
  accent?: boolean
}) {
  return (
    <div className="rounded-lg bg-[var(--secondary)]/70 px-3 py-3">
      <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">{label}</p>
      <p
        className={cn(
          'mt-1 font-display text-xl font-semibold',
          accent ? 'text-[var(--accent)]' : 'text-[#f0f4fa]',
        )}
      >
        {value}
      </p>
    </div>
  )
}
