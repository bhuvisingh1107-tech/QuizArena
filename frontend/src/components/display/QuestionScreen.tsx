import { AnswerProgressRing } from '@/components/display/AnswerProgressRing'
import { DisplayMedia } from '@/components/display/DisplayMedia'
import { DisplayTimer } from '@/components/display/DisplayTimer'
import type { DisplayLiveQuestion } from '@/hooks/displayLiveReducer'
import { cn } from '@/lib/utils'

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

interface QuestionScreenProps {
  question: DisplayLiveQuestion
  secretToken: string
  submittedCount?: number
  participantCount?: number
  questionOpenedAt?: number | null
  paused?: boolean
  className?: string
}

export function QuestionScreen({
  question,
  secretToken,
  submittedCount = 0,
  participantCount = 0,
  questionOpenedAt,
  paused = false,
  className,
}: QuestionScreenProps) {
  const sorted = [...question.options].sort((a, b) => a.sortOrder - b.sortOrder)
  const qNumber = question.index + 1
  const total =
    typeof question.totalQuestions === 'number' ? question.totalQuestions : null
  const progressPercent =
    total != null && total > 0 ? Math.min(100, (qNumber / total) * 100) : null

  return (
    <section
      className={cn('flex flex-1 flex-col gap-5 lg:gap-7', className)}
      aria-label="Current question"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p
            className="text-sm uppercase tracking-[0.25em] text-[var(--primary)] lg:text-base"
            data-testid="question-number"
          >
            Question {qNumber}
            {total != null ? ` of ${total}` : ''}
          </p>
          {question.sectionName ? (
            <p className="mt-1 font-sans text-base text-[var(--muted-foreground)] lg:text-lg">
              {question.sectionName}
            </p>
          ) : null}
          {progressPercent != null ? (
            <div
              className="mt-3 h-1.5 max-w-md overflow-hidden rounded-full bg-[var(--secondary)]"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progressPercent}
              data-testid="question-progress-bar"
            >
              <div
                className="h-full rounded-full bg-[var(--primary)] transition-all duration-500"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          ) : null}
        </div>

        <div className="flex shrink-0 items-start gap-6">
          {participantCount > 0 ? (
            <AnswerProgressRing submitted={submittedCount} total={participantCount} />
          ) : null}
          <DisplayTimer
            timeLimitSeconds={question.timeLimitSeconds}
            questionOpenedAt={questionOpenedAt}
            timerEndsAt={question.timerEndsAt}
            paused={paused}
          />
        </div>
      </div>

      <h1
        className="max-w-6xl font-display font-extrabold leading-tight text-[#f0f4fa]"
        style={{ fontSize: 'clamp(1.75rem, 4vw, 3.75rem)' }}
      >
        {question.promptText || '…'}
      </h1>

      {question.mediaFileId ? (
        <DisplayMedia
          mediaFileId={question.mediaFileId}
          questionType={question.questionType}
          secretToken={secretToken}
        />
      ) : null}

      <ul className="mt-auto grid gap-3 sm:grid-cols-2 lg:gap-4" role="list" aria-label="Answer choices">
        {sorted.length === 0 ? (
          <li className="col-span-full rounded-2xl border border-dashed border-[var(--border)] px-5 py-10 text-center text-[var(--muted-foreground)]">
            Waiting for answer choices…
          </li>
        ) : null}
        {sorted.map((option, index) => {
          const letter = LETTERS[index] ?? String(index + 1)
          return (
            <li
              key={option.id}
              data-testid={`option-tile-${letter}`}
              className="flex min-h-20 items-start gap-4 rounded-2xl border border-[var(--border)] bg-[var(--card)]/80 px-5 py-5 transition-colors lg:min-h-24 lg:px-6 lg:py-6"
            >
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[var(--primary)]/20 font-display text-xl font-bold text-[var(--primary)] lg:h-14 lg:w-14 lg:text-2xl">
                {letter}
              </span>
              <span
                className="pt-2 font-sans leading-snug text-[var(--heading)]"
                style={{ fontSize: 'clamp(1.125rem, 2vw, 1.5rem)' }}
              >
                {option.text}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
