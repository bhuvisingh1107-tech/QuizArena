import type { DisplayLiveQuestion } from '@/hooks/displayLiveReducer'
import { cn } from '@/lib/utils'

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

interface QuestionScreenProps {
  question: DisplayLiveQuestion
  className?: string
}

export function QuestionScreen({ question, className }: QuestionScreenProps) {
  const sorted = [...question.options].sort((a, b) => a.sortOrder - b.sortOrder)
  const qNumber = question.index + 1
  const total =
    typeof question.totalQuestions === 'number' ? question.totalQuestions : null

  return (
    <section
      className={cn('flex flex-1 flex-col gap-6 lg:gap-8', className)}
      aria-label="Current question"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm uppercase tracking-[0.25em] text-[var(--primary)] lg:text-base">
            Question {qNumber}
            {total != null ? ` of ${total}` : ''}
          </p>
          {question.sectionName ? (
            <p className="mt-1 font-sans text-base text-[var(--muted-foreground)] lg:text-lg">
              {question.sectionName}
            </p>
          ) : null}
        </div>
        {question.state === 'Closed' ? (
          <p className="rounded-md border border-[var(--accent)]/40 bg-[var(--accent)]/15 px-4 py-2 text-sm font-medium text-[var(--accent)]">
            Answers locked
          </p>
        ) : null}
      </div>

      <h1 className="max-w-6xl font-display text-3xl font-extrabold leading-tight text-[#f0f4fa] sm:text-4xl lg:text-6xl">
        {question.promptText || '…'}
      </h1>

      {question.mediaFileId ? (
        <div
          className="flex min-h-32 items-center justify-center rounded-2xl border border-dashed border-[var(--border)] bg-[var(--card)]/50 px-6 py-10"
          data-testid="media-placeholder"
        >
          <div className="text-center">
            <p className="font-display text-xl font-semibold text-[#f0f4fa]">Media prompt</p>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Visual content is managed by the host — watch the stage display
            </p>
          </div>
        </div>
      ) : null}

      <ul className="mt-auto grid gap-3 sm:grid-cols-2 lg:gap-4" role="list">
        {sorted.map((option, index) => {
          const letter = LETTERS[index] ?? String(index + 1)
          return (
            <li
              key={option.id}
              data-testid={`option-tile-${letter}`}
              className="flex min-h-20 items-start gap-4 rounded-2xl border border-[var(--border)] bg-[var(--card)]/80 px-5 py-5 lg:min-h-24 lg:px-6 lg:py-6"
            >
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[var(--primary)]/20 font-display text-xl font-bold text-[var(--primary)] lg:h-14 lg:w-14 lg:text-2xl">
                {letter}
              </span>
              <span className="pt-2 font-sans text-xl leading-snug text-[#f0f4fa] lg:text-2xl">
                {option.text}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
