import { AudioLines, ImagePlus, Loader2, Trash2, Video } from 'lucide-react'
import { useRef, useState } from 'react'

import { ChooseExistingMediaDialog } from '@/components/quiz-builder/ChooseExistingMediaDialog'
import { Button } from '@/components/ui/button'
import { useMedia, useMediaMutations } from '@/hooks/queries/useMedia'
import { useQuestionMutations } from '@/hooks/queries/useQuestions'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import type { MediaCategory, MediaFile } from '@/types/api'

interface QuestionMediaSectionProps {
  quizId: string
  sectionId: string
  questionId: string | null
  mediaFileId?: string | null
  /** Called after attach so parent can refresh local question state. */
  onAttached?: (mediaFileId: string) => void
  /** Called after media is cleared from the question. */
  onCleared?: () => void
  disabledReason?: string | null
}

export function QuestionMediaSection({
  quizId,
  sectionId,
  questionId,
  mediaFileId,
  onAttached,
  onCleared,
  disabledReason,
}: QuestionMediaSectionProps) {
  const imageInputRef = useRef<HTMLInputElement>(null)
  const audioInputRef = useRef<HTMLInputElement>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const { uploadMedia, attachMedia } = useMediaMutations()
  const { updateQuestion } = useQuestionMutations(quizId, sectionId)
  const attachedQuery = useMedia(mediaFileId ?? undefined, Boolean(mediaFileId))

  const canAttach = Boolean(questionId) && !disabledReason

  const uploadAndAttach = async (file: File, category: MediaCategory) => {
    if (!questionId) return
    setBusy(true)
    try {
      const media = await uploadMedia.mutateAsync({ file, category, quizId })
      const result = await attachMedia.mutateAsync({
        mediaId: media.id,
        quizId,
        sectionId,
        questionId,
      })
      onAttached?.(result.mediaFileId)
      toastSuccess('Media attached')
    } catch (error) {
      toastError(error)
    } finally {
      setBusy(false)
    }
  }

  const attachExisting = async (media: MediaFile) => {
    if (!questionId) return
    setBusy(true)
    try {
      const result = await attachMedia.mutateAsync({
        mediaId: media.id,
        quizId,
        sectionId,
        questionId,
      })
      onAttached?.(result.mediaFileId)
      toastSuccess('Media attached')
    } catch (error) {
      toastError(error)
    } finally {
      setBusy(false)
    }
  }

  const removeMedia = async () => {
    if (!questionId || !mediaFileId) return
    if (!window.confirm('Remove attached media from this question?')) return
    setBusy(true)
    try {
      await updateQuestion.mutateAsync({
        questionId,
        input: { clearMedia: true },
      })
      onCleared?.()
      toastSuccess('Media removed')
    } catch (error) {
      toastError(error)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3 rounded-md border border-[var(--border)] p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-[#f0f4fa]">Media</h3>
        {busy ? <Loader2 className="h-4 w-4 animate-spin text-[var(--muted-foreground)]" /> : null}
      </div>

      {disabledReason ? (
        <p className="text-xs text-[var(--muted-foreground)]">{disabledReason}</p>
      ) : null}

      {!questionId ? (
        <p className="text-xs text-[var(--muted-foreground)]">
          Save the question first to attach media.
        </p>
      ) : null}

      {mediaFileId && attachedQuery.data ? (
        <div className="rounded-md border border-[var(--border)] bg-[var(--color-ink)]/40 px-3 py-2 text-sm">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="font-medium text-[#f0f4fa]">
                {attachedQuery.data.originalFilename || 'Attached media'}
              </p>
              <p className="text-xs text-[var(--muted-foreground)]">
                {attachedQuery.data.category} · {attachedQuery.data.mimeType}
              </p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="shrink-0 text-[var(--destructive)]"
              aria-label="Remove media"
              disabled={!canAttach || busy}
              onClick={() => void removeMedia()}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
          {attachedQuery.data.mimeType.startsWith('image/') ? (
            <img
              src={attachedQuery.data.url}
              alt=""
              className="mt-2 max-h-40 rounded-md object-contain"
            />
          ) : null}
          {attachedQuery.data.mimeType.startsWith('audio/') ? (
            <audio controls src={attachedQuery.data.url} className="mt-2 w-full" />
          ) : null}
        </div>
      ) : mediaFileId ? (
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-[var(--muted-foreground)]">Media attached ({mediaFileId})</p>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-[var(--destructive)]"
            disabled={!canAttach || busy}
            onClick={() => void removeMedia()}
          >
            <Trash2 className="h-4 w-4" />
            Remove media
          </Button>
        </div>
      ) : (
        <p className="text-xs text-[var(--muted-foreground)]">No media attached.</p>
      )}

      <div className="flex flex-wrap gap-2">
        <input
          ref={imageInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (file) void uploadAndAttach(file, 'question_image')
          }}
        />
        <input
          ref={audioInputRef}
          type="file"
          accept="audio/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (file) void uploadAndAttach(file, 'question_audio')
          }}
        />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={!canAttach || busy}
          onClick={() => imageInputRef.current?.click()}
        >
          <ImagePlus className="h-4 w-4" />
          Upload Image
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={!canAttach || busy}
          onClick={() => audioInputRef.current?.click()}
        >
          <AudioLines className="h-4 w-4" />
          Upload Audio
        </Button>
        <Button type="button" variant="outline" size="sm" disabled title="Not available in v1">
          <Video className="h-4 w-4" />
          Upload Video
          <span className="text-[10px] text-[var(--muted-foreground)]">Not in v1</span>
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!canAttach || busy}
          onClick={() => setPickerOpen(true)}
        >
          Choose Existing Media
        </Button>
      </div>

      <ChooseExistingMediaDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        quizId={quizId}
        categories={['question_image', 'question_audio']}
        onSelect={(media) => void attachExisting(media)}
      />
    </div>
  )
}
