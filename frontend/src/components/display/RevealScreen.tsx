import { DisplayMedia } from '@/components/display/DisplayMedia'
import type {
  DisplayLiveQuestion,
  DisplayOptionDistribution,
} from '@/hooks/displayLiveReducer'
import { cn } from '@/lib/utils'

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

interface RevealScreenProps {
  question: DisplayLiveQuestion
  secretToken: string
  optionDistribution?: DisplayOptionDistribution[]
  explanation?: string | null
  accuracyPercent?: number | null
  answeredCount?: number | null
  className?: string
}

export function RevealScreen({
  question,
  secretToken,
  optionDistribution = [],
  explanation,
  accuracyPercent,
  answeredCount,
  className,
}: RevealScreenProps) {
  const sorted = [...question.options].sort((a, b) => a.sortOrder - b.sortOrder)
  const qNumber = question.index + 1
  const total =
    typeof question.totalQuestions === 'number' ? question.totalQuestions : null

  const distributionByOption = new Map(
    optionDistribution.map((row) => [row.optionId, row]),
  )

  return (
    <section
      className={cn('flex flex-1 flex-col gap-5 lg:gap-7', className)}
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
        {accuracyPercent != null ? (
          <p
            className="rounded-md border border-[var(--color-success)]/40 bg-[var(--color-success)]/15 px-4 py-2 text-sm font-medium text-[var(--color-success)] lg:text-base"
            data-testid="accuracy-badge"
          >
            {accuracyPercent}% correct
            {answeredCount != null ? ` · ${answeredCount} answered` : ''}
          </p>
        ) : null}
      </div>

      <h1
        className="max-w-6xl font-display font-extrabold leading-tight text-[#f0f4fa]"
        style={{ fontSize: 'clamp(1.75rem, 4vw, 3.25rem)' }}
      >
        {question.promptText || '…'}
      </h1>

      {question.imageUrl || question.mediaFileId ? (
        <DisplayMedia
          key={question.id}
          questionId={question.id}
          imageUrl={question.imageUrl}
          mediaFileId={question.mediaFileId}
          questionType={question.questionType}
          secretToken={secretToken}
        />
      ) : null}

      <ul className="grid gap-3 sm:grid-cols-2 lg:gap-4" role="list">
        {sorted.map((option, index) => {
          const letter = LETTERS[index] ?? String(index + 1)
          const isCorrect = option.isCorrect === true
          const isIncorrect = option.isCorrect === false
          const stats = distributionByOption.get(option.id)
          const percent = stats?.percent ?? 0

          return (
            <li
              key={option.id}
              data-testid={`reveal-option-${letter}`}
              data-correct={isCorrect ? 'true' : isIncorrect ? 'false' : undefined}
              className={cn(
                'flex flex-col gap-3 rounded-2xl border px-5 py-5 lg:px-6 lg:py-6',
                isCorrect &&
                  'border-[var(--color-cyan-mint)]/70 bg-[var(--color-cyan-mint)]/20 shadow-[0_0_24px_rgba(45,212,191,0.12)]',
                isIncorrect &&
                  'border-[var(--destructive)]/35 bg-[var(--destructive)]/10 opacity-80',
                !isCorrect &&
                  !isIncorrect &&
                  'border-[var(--border)] bg-[var(--card)]/80',
              )}
            >
              <div className="flex items-start gap-4">
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
                  <span
                    className="font-sans leading-snug text-[#f0f4fa]"
                    style={{ fontSize: 'clamp(1.125rem, 2vw, 1.5rem)' }}
                  >
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
                {stats ? (
                  <span className="shrink-0 font-display text-xl font-bold tabular-nums text-[var(--accent)] lg:text-2xl">
                    {percent}%
                  </span>
                ) : null}
              </div>

              {stats ? (
                <div
                  className="h-3 overflow-hidden rounded-full bg-[var(--secondary)]"
                  data-testid={`reveal-bar-${letter}`}
                >
                  <div
                    className={cn(
                      'reveal-bar-fill h-full rounded-full transition-all duration-700 ease-out',
                      isCorrect ? 'bg-[var(--color-cyan-mint)]' : 'bg-[var(--primary)]/70',
                    )}
                    style={{ width: `${percent}%` }}
                  />
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>

      {explanation ? (
        <aside
          className="mt-auto rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 px-6 py-5 lg:px-8 lg:py-6"
          data-testid="reveal-explanation"
        >
          <p className="mb-2 text-xs uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
            Explanation
          </p>
          <p
            className="font-sans leading-relaxed text-[#f0f4fa]"
            style={{ fontSize: 'clamp(1rem, 2vw, 1.25rem)' }}
          >
            {explanation}
          </p>
        </aside>
      ) : null}
    </section>
  )
}
