import { cn } from '@/lib/utils'

interface AnswerProgressRingProps {
  submitted: number
  total: number
  className?: string
}

export function AnswerProgressRing({
  submitted,
  total,
  className,
}: AnswerProgressRingProps) {
  const safeTotal = Math.max(total, 1)
  const ratio = Math.min(1, submitted / safeTotal)
  const circumference = 2 * Math.PI * 42
  const offset = circumference * (1 - ratio)

  return (
    <div
      className={cn('relative flex flex-col items-center gap-2', className)}
      data-testid="answer-progress-ring"
      aria-label={`${submitted} of ${total} answered`}
    >
      <svg
        width="120"
        height="120"
        viewBox="0 0 100 100"
        className="-rotate-90"
        aria-hidden
      >
        <circle
          cx="50"
          cy="50"
          r="42"
          fill="none"
          stroke="var(--secondary)"
          strokeWidth="8"
        />
        <circle
          cx="50"
          cy="50"
          r="42"
          fill="none"
          stroke="var(--primary)"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-500 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center pt-1">
        <span className="font-display text-2xl font-bold tabular-nums text-[#f0f4fa] lg:text-3xl">
          {submitted}
        </span>
        <span className="text-xs uppercase tracking-wider text-[var(--muted-foreground)]">
          / {total}
        </span>
      </div>
      <p className="text-sm text-[var(--muted-foreground)] lg:text-base">Answers in</p>
    </div>
  )
}
