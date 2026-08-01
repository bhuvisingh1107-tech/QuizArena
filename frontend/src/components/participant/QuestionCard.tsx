import { ImageIcon, Volume2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { QuestionTimer } from '@/components/participant/QuestionTimer'
import { mediaContentUrl } from '@/lib/media-url'
import type { ParticipantLiveQuestion } from '@/types/api'
import { cn } from '@/lib/utils'

interface QuestionCardProps {
  question: ParticipantLiveQuestion
  sessionToken?: string | null
  openedAt?: string | null
  paused?: boolean
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

function QuestionMedia({
  mediaFileId,
  questionType,
  sessionToken,
}: {
  mediaFileId: string
  questionType?: ParticipantLiveQuestion['questionType']
  sessionToken?: string | null
}) {
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setFailed(false)
  }, [mediaFileId])

  if (!sessionToken || failed) {
    const unavailable = !sessionToken || failed
    return (
      <div
        className="mt-4 flex min-h-36 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--border)] bg-[var(--secondary)]/40 px-4 py-8 text-center"
        role="img"
        aria-label={unavailable ? 'Media unavailable' : 'Media loading'}
      >
        <ImageIcon className="h-8 w-8 text-[var(--muted-foreground)]" aria-hidden />
        <p className="text-sm text-[var(--muted-foreground)]">
          {failed
            ? 'Could not load media.'
            : !sessionToken
              ? 'Media unavailable.'
              : 'Media loading…'}
        </p>
      </div>
    )
  }

  const url = mediaContentUrl(mediaFileId, sessionToken)
  const isAudio = questionType === 'Audio'

  if (isAudio) {
    return (
      <div className="mt-4 rounded-lg border border-[var(--border)] bg-[var(--secondary)]/40 p-4">
        <div className="mb-2 flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
          <Volume2 className="h-4 w-4" aria-hidden />
          Listen to the clip
        </div>
        <audio
          controls
          preload="metadata"
          className="w-full"
          src={url}
          onError={() => setFailed(true)}
        >
          Your browser does not support audio playback.
        </audio>
      </div>
    )
  }

  return (
    <div className="mt-4 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--secondary)]/30">
      <img
        src={url}
        alt="Question media"
        className="max-h-64 w-full object-contain"
        onError={() => setFailed(true)}
      />
    </div>
  )
}

export function QuestionCard({
  question,
  sessionToken,
  openedAt,
  paused = false,
  className,
}: QuestionCardProps) {
  const number = question.index + 1
  const total = question.totalQuestions
  const progressPercent =
    total != null && total > 0 ? Math.round((number / total) * 100) : null

  return (
    <article
      className={cn(
        'rounded-xl border border-[var(--border)] bg-[var(--card)]/90 p-5',
        className,
      )}
    >
      {progressPercent != null ? (
        <div className="mb-4 space-y-1">
          <div className="flex justify-between text-xs text-[var(--muted-foreground)]">
            <span>
              Question {number}
              {total != null ? ` of ${total}` : ''}
            </span>
            <span>{progressPercent}%</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-[var(--secondary)]">
            <div
              className="h-full rounded-full bg-[var(--primary)] transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      ) : null}

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

      <QuestionTimer
        timeLimitSeconds={question.timeLimitSeconds}
        timerEndsAt={question.timerEndsAt}
        openedAt={openedAt}
        paused={paused}
        className="mb-4"
      />

      <h2 className="font-display text-xl font-semibold leading-snug text-[#f0f4fa] sm:text-2xl">
        {question.promptText?.trim() || 'Question'}
      </h2>

      {question.mediaFileId ? (
        <QuestionMedia
          key={question.mediaFileId}
          mediaFileId={question.mediaFileId}
          questionType={question.questionType}
          sessionToken={sessionToken}
        />
      ) : null}
    </article>
  )
}
