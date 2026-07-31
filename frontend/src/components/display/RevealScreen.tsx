import type { DisplayLiveQuestion } from '@/hooks/displayLiveReducer'
import type { LeaderboardEntry } from '@/types/api'
import { cn } from '@/lib/utils'

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

interface RevealScreenProps {
  question: DisplayLiveQuestion
  leaderboard?: LeaderboardEntry[]
  className?: string
}

export function RevealScreen({
  question,
  leaderboard = [],
  className,
}: RevealScreenProps) {
  const sorted = [...question.options].sort((a, b) => a.sortOrder - b.sortOrder)
  const qNumber = question.index + 1
  const total =
    typeof question.totalQuestions === 'number' ? question.totalQuestions : null
  const top = leaderboard.slice(0, 5)

  return (
    <section
      className={cn('flex flex-1 flex-col gap-6 lg:gap-8', className)}
      aria-label="Answer reveal"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm uppercase tracking-[0.25em] text-[var(--accent)] lg:text-base">
            Reveal · Question {qNumber}
            {total != null ? ` of ${total}` : ''}
          </p>
          {question.sectionName ? (
            <p className="mt-1 font-sans text-base text-[var(--muted-foreground)] lg:text-lg">
              {question.sectionName}
            </p>
          ) : null}
        </div>
        <p className="rounded-md border border-[var(--color-success)]/40 bg-[var(--color-success)]/15 px-4 py-2 text-sm font-medium text-[var(--color-success)]">
          Correct answers highlighted
        </p>
      </div>

      <h1 className="max-w-6xl font-display text-3xl font-extrabold leading-tight text-[#f0f4fa] sm:text-4xl lg:text-5xl">
        {question.promptText || '…'}
      </h1>

      {question.mediaFileId ? (
        <div
          className="flex min-h-24 items-center justify-center rounded-2xl border border-dashed border-[var(--border)] bg-[var(--card)]/50 px-6 py-8"
          data-testid="media-placeholder"
        >
          <p className="text-sm text-[var(--muted-foreground)]">Media prompt available on host display</p>
        </div>
      ) : null}

      <ul className="grid gap-3 sm:grid-cols-2 lg:gap-4" role="list">
        {sorted.map((option, index) => {
          const letter = LETTERS[index] ?? String(index + 1)
          const isCorrect = option.isCorrect === true
          const isIncorrect = option.isCorrect === false
          return (
            <li
              key={option.id}
              data-testid={`reveal-option-${letter}`}
              data-correct={isCorrect ? 'true' : isIncorrect ? 'false' : undefined}
              className={cn(
                'flex min-h-20 items-start gap-4 rounded-2xl border px-5 py-5 transition-colors lg:min-h-24 lg:px-6 lg:py-6',
                isCorrect &&
                  'border-[var(--color-cyan-mint)]/70 bg-[var(--color-cyan-mint)]/20 shadow-[0_0_24px_rgba(45,212,191,0.12)]',
                isIncorrect &&
                  'border-[var(--destructive)]/35 bg-[var(--destructive)]/10 opacity-70',
                !isCorrect &&
                  !isIncorrect &&
                  'border-[var(--border)] bg-[var(--card)]/80',
              )}
            >
              <span
                className={cn(
                  'flex h-12 w-12 shrink-0 items-center justify-center rounded-xl font-display text-xl font-bold lg:h-14 lg:w-14 lg:text-2xl',
                  isCorrect &&
                    'bg-[var(--color-cyan-mint)] text-[var(--color-ink)]',
                  isIncorrect && 'bg-[var(--destructive)]/30 text-[var(--destructive)]',
                  !isCorrect &&
                    !isIncorrect &&
                    'bg-[var(--secondary)] text-[var(--muted-foreground)]',
                )}
              >
                {letter}
              </span>
              <span className="flex flex-1 flex-col gap-1 pt-2">
                <span className="font-sans text-xl leading-snug text-[#f0f4fa] lg:text-2xl">
                  {option.text}
                </span>
                {isCorrect ? (
                  <span
                    className="text-sm font-medium uppercase tracking-wide text-[var(--color-cyan-mint)]"
                    data-testid="correct-marker"
                  >
                    Correct
                  </span>
                ) : null}
              </span>
            </li>
          )
        })}
      </ul>

      {top.length > 0 ? (
        <aside className="mt-auto rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-5 py-4">
          <p className="mb-3 text-xs uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
            Live standings
          </p>
          <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            {top.map((entry) => (
              <li
                key={entry.participantId}
                className="flex items-center justify-between gap-2 rounded-lg bg-[var(--secondary)]/50 px-3 py-2"
              >
                <span className="truncate font-sans text-sm text-[#f0f4fa]">
                  <span className="mr-2 font-display font-bold text-[var(--primary)]">
                    #{entry.rank}
                  </span>
                  {entry.displayName}
                </span>
                <span className="shrink-0 font-medium text-[var(--accent)]">{entry.score}</span>
              </li>
            ))}
          </ol>
        </aside>
      ) : null}
    </section>
  )
}
