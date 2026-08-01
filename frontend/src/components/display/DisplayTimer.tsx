import { useEffect, useState } from 'react'

import { cn } from '@/lib/utils'

interface DisplayTimerProps {
  timeLimitSeconds?: number | null
  questionOpenedAt?: number | null
  timerEndsAt?: string | null
  paused?: boolean
  className?: string
}

export function DisplayTimer({
  timeLimitSeconds,
  questionOpenedAt,
  timerEndsAt,
  paused = false,
  className,
}: DisplayTimerProps) {
  const [remaining, setRemaining] = useState<number | null>(null)

  useEffect(() => {
    if (!timeLimitSeconds) {
      setRemaining(null)
      return
    }

    const computeRemaining = () => {
      if (timerEndsAt) {
        const end = new Date(timerEndsAt).getTime()
        if (!Number.isNaN(end)) {
          return Math.max(0, Math.ceil((end - Date.now()) / 1000))
        }
      }
      if (questionOpenedAt) {
        const endTime = questionOpenedAt + timeLimitSeconds * 1000
        return Math.max(0, Math.ceil((endTime - Date.now()) / 1000))
      }
      return timeLimitSeconds
    }

    setRemaining(computeRemaining())
    if (paused) return

    const id = window.setInterval(() => {
      setRemaining(computeRemaining())
    }, 250)

    return () => window.clearInterval(id)
  }, [timeLimitSeconds, questionOpenedAt, timerEndsAt, paused])

  if (remaining == null || !timeLimitSeconds) return null

  const progress = Math.max(0, Math.min(100, (remaining / timeLimitSeconds) * 100))
  const urgent = remaining <= 5

  return (
    <div
      className={cn('flex flex-col items-end gap-2', className)}
      aria-live="polite"
      data-testid="display-timer"
    >
      <div
        className={cn(
          'font-display text-4xl font-bold tabular-nums lg:text-5xl',
          urgent ? 'text-[var(--destructive)] animate-pulse' : 'text-[var(--accent)]',
        )}
      >
        {remaining}s
      </div>
      <div
        className="h-2 w-32 overflow-hidden rounded-full bg-[var(--secondary)] lg:w-40"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={timeLimitSeconds}
        aria-valuenow={remaining}
      >
        <div
          className={cn(
            'h-full rounded-full transition-all duration-300 ease-linear',
            urgent ? 'bg-[var(--destructive)]' : 'bg-[var(--primary)]',
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}
