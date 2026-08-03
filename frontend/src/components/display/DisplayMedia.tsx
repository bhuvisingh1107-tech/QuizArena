import { ImageIcon, Volume2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { resolveLiveMediaUrl } from '@/lib/media-url'
import type { QuestionType } from '@/types/api'
import { cn } from '@/lib/utils'

interface DisplayMediaProps {
  mediaFileId?: string | null
  imageUrl?: string | null
  questionType?: QuestionType
  secretToken: string
  className?: string
}

export function DisplayMedia({
  mediaFileId,
  imageUrl,
  questionType,
  secretToken,
  className,
}: DisplayMediaProps) {
  const [failed, setFailed] = useState(false)
  const url = resolveLiveMediaUrl({ imageUrl, mediaFileId, token: secretToken })

  useEffect(() => {
    setFailed(false)
  }, [imageUrl, mediaFileId, secretToken])

  if (!url || failed) {
    return (
      <div
        className={cn(
          'flex min-h-40 items-center justify-center rounded-2xl border border-dashed border-[var(--border)] bg-[var(--card)]/50 px-6 py-10',
          className,
        )}
        data-testid="media-placeholder"
        role="img"
        aria-label={failed || !url ? 'Media unavailable' : 'Media loading'}
      >
        <div className="text-center">
          <ImageIcon
            className="mx-auto mb-2 h-10 w-10 text-[var(--muted-foreground)]"
            aria-hidden
          />
          <p className="font-display text-lg font-semibold text-[var(--heading)]">
            {failed
              ? 'Could not load media'
              : !url
                ? 'Media unavailable'
                : 'Media loading…'}
          </p>
        </div>
      </div>
    )
  }

  const isAudio = questionType === 'Audio'

  if (isAudio) {
    return (
      <div
        className={cn(
          'rounded-2xl border border-[var(--border)] bg-[var(--card)]/60 p-6 lg:p-8',
          className,
        )}
        data-testid="display-media-audio"
      >
        <div className="mb-4 flex items-center gap-3 text-[var(--muted-foreground)]">
          <Volume2 className="h-6 w-6" aria-hidden />
          <span className="font-display text-lg font-semibold text-[#f0f4fa]">
            Listen to the clip
          </span>
        </div>
        <audio
          controls
          autoPlay
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
    <div
      className={cn(
        'overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]/40',
        className,
      )}
      data-testid="display-media-image"
    >
      <img
        src={url}
        alt="Question media"
        className="mx-auto max-h-[min(40vh,420px)] w-full object-contain"
        data-testid="display-media-img"
        onError={() => setFailed(true)}
      />
    </div>
  )
}
