import { useEffect, useState } from 'react'

import { cn } from '@/lib/utils'

interface QuestionTimerProps {
  timeLimitSeconds?: number | null
  timerEndsAt?: string | null
  openedAt?: string | null
  paused?: boolean
  className?: string
}

function computeRemaining(
  timeLimitSeconds: number | null | undefined,
  timerEndsAt: string | null | undefined,
  openedAt: string | null | undefined,
): number | null {
  if (timerEndsAt) {
    const end = new Date(timerEndsAt).getTime()
    if (!Number.isNaN(end)) {
      return Math.max(0, Math.ceil((end - Date.now()) / 1000))
    }
  }
  if (timeLimitSeconds && openedAt) {
    const start = new Date(openedAt).getTime()
    if (!Number.isNaN(start)) {
      const end = start + timeLimitSeconds * 1000
      return Math.max(0, Math.ceil((end - Date.now()) / 1000))
    }
  }
  if (timeLimitSeconds) {
    return timeLimitSeconds
  }
  return null
}

function hasDeadline(
  timeLimitSeconds: number | null | undefined,
  timerEndsAt: string | null | undefined,
  openedAt: string | null | undefined,
): boolean {
  return Boolean(timerEndsAt || (timeLimitSeconds && openedAt) || timeLimitSeconds)
}

export function QuestionTimer({
  timeLimitSeconds,
  timerEndsAt,
  openedAt,
  paused = false,
  className,
}: QuestionTimerProps) {
  const [remaining, setRemaining] = useState<number | null>(() =>
    computeRemaining(timeLimitSeconds, timerEndsAt, openedAt),
  )

  useEffect(() => {
    if (!hasDeadline(timeLimitSeconds, timerEndsAt, openedAt)) {
      setRemaining(null)
      return
    }

    const tick = () => {
      setRemaining(computeRemaining(timeLimitSeconds, timerEndsAt, openedAt))
    }

    tick()
    if (paused) return

    const id = window.setInterval(tick, 250)
    return () => window.clearInterval(id)
  }, [timeLimitSeconds, timerEndsAt, openedAt, paused])

  if (remaining == null || !timeLimitSeconds) return null

  const total = timeLimitSeconds
  const progress = Math.max(0, Math.min(100, (remaining / total) * 100))
  const urgent = remaining <= 5

  return (
    <div className={cn('space-y-2', className)} aria-live="polite">
      <div className="flex items-center justify-between text-xs text-[var(--muted-foreground)]">
        <span>Time remaining</span>
        <span
          className={cn(
            'font-display text-sm font-semibold tabular-nums',
            urgent ? 'text-[var(--destructive)]' : 'text-[var(--foreground)]',
          )}
        >
          {remaining}s
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-[var(--secondary)]"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
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
