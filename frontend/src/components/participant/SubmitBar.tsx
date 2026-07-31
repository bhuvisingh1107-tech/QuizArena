import { Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { AnswerSubmitState } from '@/types/api'
import { cn } from '@/lib/utils'

interface SubmitBarProps {
  onSubmit: () => void
  disabled?: boolean
  canSubmit?: boolean
  submissionStatus: AnswerSubmitState
  submissionError?: string | null
  className?: string
}

function statusText(status: AnswerSubmitState, error?: string | null): string {
  switch (status) {
    case 'submitting':
      return 'Submitting your answer…'
    case 'submitted':
      return 'Answer submitted — waiting for reveal.'
    case 'already_submitted':
      return 'You already answered this question.'
    case 'rejected':
      return error || 'Answer was rejected. Try again if still open.'
    case 'selecting':
      return 'Ready to submit'
    default:
      return 'Select an answer to continue'
  }
}

export function SubmitBar({
  onSubmit,
  disabled = false,
  canSubmit = false,
  submissionStatus,
  submissionError,
  className,
}: SubmitBarProps) {
  const submitting = submissionStatus === 'submitting'
  const alreadyDone =
    submissionStatus === 'submitted' || submissionStatus === 'already_submitted'
  const blocked = disabled || submitting || alreadyDone || !canSubmit

  return (
    <div className={cn('space-y-2', className)}>
      <Button
        type="button"
        size="lg"
        className="h-12 w-full text-base"
        disabled={blocked}
        onClick={onSubmit}
        aria-busy={submitting}
      >
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        {alreadyDone ? 'Submitted' : submitting ? 'Submitting…' : 'Submit answer'}
      </Button>
      <p
        className={cn(
          'text-center text-sm',
          submissionStatus === 'rejected'
            ? 'text-[var(--destructive)]'
            : 'text-[var(--muted-foreground)]',
        )}
        role="status"
        aria-live="polite"
      >
        {statusText(submissionStatus, submissionError)}
      </p>
    </div>
  )
}
