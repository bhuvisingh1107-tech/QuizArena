import { ImageIcon } from 'lucide-react'

import type { ParticipantLiveQuestion } from '@/types/api'
import { cn } from '@/lib/utils'

interface QuestionCardProps {
  question: ParticipantLiveQuestion
  className?: string
}

function statusLabel(state: ParticipantLiveQuestion['state']): string {
  switch (state) {
    case 'Open':
    case 'BuzzerOpen':
      return 'Open'
    case 'Closed':
    case 'BuzzerLocked':
      return 'Closed'
    case 'Revealed':
      return 'Revealed'
    case 'Scored':
      return 'Scored'
    default:
      return state ?? 'Pending'
  }
}

export function QuestionCard({ question, className }: QuestionCardProps) {
  const number = question.index + 1
  const total = question.totalQuestions

  return (
    <article
      className={cn(
        'rounded-xl border border-[var(--border)] bg-[var(--card)]/90 p-5',
        className,
      )}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-[var(--muted-foreground)]">
        <span className="rounded-md bg-[var(--secondary)] px-2 py-1 font-medium text-[var(--primary)]">
          Q{number}
          {total != null ? ` / ${total}` : ''}
        </span>
        {question.sectionName ? (
          <span className="rounded-md bg-[var(--secondary)] px-2 py-1">{question.sectionName}</span>
        ) : null}
        <span className="rounded-md bg-[var(--secondary)] px-2 py-1">
          {statusLabel(question.state)}
        </span>
        {typeof question.basePoints === 'number' ? (
          <span className="rounded-md bg-[var(--secondary)] px-2 py-1">
            {question.basePoints} pts
          </span>
        ) : null}
      </div>

      <h2 className="font-display text-xl font-semibold leading-snug text-[#f0f4fa] sm:text-2xl">
        {question.promptText?.trim() || 'Question'}
      </h2>

      {question.mediaFileId ? (
        <div
          className="mt-4 flex min-h-36 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--border)] bg-[var(--secondary)]/40 px-4 py-8 text-center"
          role="img"
          aria-label="Media content unavailable on participant devices"
        >
          <ImageIcon className="h-8 w-8 text-[var(--muted-foreground)]" aria-hidden />
          <p className="text-sm text-[var(--muted-foreground)]">
            Media attached — view on the host display.
          </p>
        </div>
      ) : null}
    </article>
  )
}
