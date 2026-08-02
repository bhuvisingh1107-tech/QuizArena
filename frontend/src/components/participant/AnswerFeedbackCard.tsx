import { CheckCircle2, XCircle } from 'lucide-react'

import { Skeleton } from '@/components/ui/skeleton'
import type {
  ParticipantLiveOption,
  ParticipantLiveQuestion,
  PersonalScoreFeedback,
} from '@/types/api'
import { cn } from '@/lib/utils'

interface AnswerFeedbackCardProps {
  question: ParticipantLiveQuestion
  options: ParticipantLiveOption[]
  feedback: PersonalScoreFeedback | null
  totalScore: number
  className?: string
}

export function AnswerFeedbackCard({
  question,
  options,
  feedback,
  totalScore,
  className,
}: AnswerFeedbackCardProps) {
  if (!feedback) {
    return (
      <section
        className={cn(
          'rounded-xl border border-[var(--border)] bg-[var(--card)]/90 p-5',
          className,
        )}
        aria-label="Answer feedback"
        aria-busy="true"
      >
        <div className="flex items-start gap-3">
          <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-7 w-32" />
            <p className="text-sm text-[var(--muted-foreground)]">Scoring…</p>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <Skeleton className="h-16 rounded-lg" />
          <Skeleton className="h-16 rounded-lg" />
        </div>
        <p className="mt-5 text-center text-sm text-[var(--muted-foreground)]">
          Checking your answer…
        </p>
      </section>
    )
  }

  const isCorrect = feedback.isCorrect
  const isUnanswered = feedback.isUnanswered
  const pointsEarned = feedback.pointsEarned

  const correctOptions = options.filter((o) => o.isCorrect === true)
  const correctText =
    correctOptions.length > 0
      ? correctOptions.map((o) => o.text).join(', ')
      : '—'

  return (
    <section
      className={cn(
        'rounded-xl border bg-[var(--card)]/90 p-5 transition-all duration-500',
        isCorrect && !isUnanswered
          ? 'border-[var(--color-success)]/50'
          : 'border-[var(--destructive)]/40',
        className,
      )}
      aria-label="Answer feedback"
    >
      <div className="flex items-start gap-3">
        {isCorrect && !isUnanswered ? (
          <CheckCircle2
            className="mt-0.5 h-8 w-8 shrink-0 text-[var(--color-success)]"
            aria-hidden
          />
        ) : (
          <XCircle
            className="mt-0.5 h-8 w-8 shrink-0 text-[var(--destructive)]"
            aria-hidden
          />
        )}
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              'font-display text-xl font-bold',
              isCorrect && !isUnanswered
                ? 'text-[var(--color-success)]'
                : 'text-[var(--destructive)]',
            )}
          >
            {isUnanswered
              ? 'No answer submitted'
              : isCorrect
                ? 'Correct!'
                : 'Incorrect!'}
          </p>
          {!isCorrect || isUnanswered ? (
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Correct answer:{' '}
              <span className="font-medium text-[#f0f4fa]">{correctText}</span>
            </p>
          ) : null}
        </div>
      </div>

      {question.explanation?.trim() ? (
        <div className="mt-4 rounded-lg bg-[var(--secondary)]/60 px-4 py-3">
          <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">
            Explanation
          </p>
          <p className="mt-1 text-sm leading-relaxed text-[#f0f4fa]">
            {question.explanation}
          </p>
        </div>
      ) : null}

      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-[var(--secondary)]/70 px-3 py-3">
          <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">
            Points earned
          </p>
          <p className="mt-1 font-display text-xl font-semibold text-[var(--accent)]">
            +{pointsEarned}
          </p>
        </div>
        <div className="rounded-lg bg-[var(--secondary)]/70 px-3 py-3">
          <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">
            Total score
          </p>
          <p className="mt-1 font-display text-xl font-semibold text-[#f0f4fa]">
            {totalScore}
          </p>
        </div>
      </div>

      {feedback.timeBonus > 0 || feedback.streakBonus > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-[var(--muted-foreground)]">
          {feedback.timeBonus > 0 ? (
            <span className="rounded-md bg-[var(--primary)]/15 px-2 py-1 text-[var(--primary)]">
              +{feedback.timeBonus} time bonus
            </span>
          ) : null}
          {feedback.streakBonus > 0 ? (
            <span className="rounded-md bg-[var(--accent)]/15 px-2 py-1 text-[var(--accent)]">
              +{feedback.streakBonus} streak bonus
            </span>
          ) : null}
        </div>
      ) : null}

      <p className="mt-5 text-center text-sm text-[var(--muted-foreground)]">
        Standings up next…
      </p>
    </section>
  )
}
