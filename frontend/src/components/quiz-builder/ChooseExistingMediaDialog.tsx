import { useMemo, useState } from 'react'

import { EmptyState } from '@/components/shared/EmptyState'
import { LoadingState } from '@/components/shared/LoadingState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useQuizMedia } from '@/hooks/queries/useMedia'
import { cn } from '@/lib/utils'
import type { MediaCategory, MediaFile } from '@/types/api'

interface ChooseExistingMediaDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  quizId: string
  /** Limit picker to image or audio categories when set. */
  categories?: MediaCategory[]
  onSelect: (media: MediaFile) => void
}

export function ChooseExistingMediaDialog({
  open,
  onOpenChange,
  quizId,
  categories,
  onSelect,
}: ChooseExistingMediaDialogProps) {
  const mediaQuery = useQuizMedia(quizId, {}, open)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const items = useMemo(() => {
    const all = mediaQuery.data?.items ?? []
    if (!categories?.length) return all
    return all.filter((m) => categories.includes(m.category))
  }, [mediaQuery.data, categories])

  const selected = items.find((m) => m.id === selectedId) ?? null

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setSelectedId(null)
        onOpenChange(next)
      }}
    >
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Choose existing media</DialogTitle>
          <DialogDescription>
            Media previously uploaded for this quiz.
          </DialogDescription>
        </DialogHeader>

        {mediaQuery.isLoading ? <LoadingState label="Loading media…" /> : null}

        {!mediaQuery.isLoading && items.length === 0 ? (
          <EmptyState
            title="No media yet"
            description="Upload an image or audio file first, then it will appear here."
          />
        ) : null}

        {items.length > 0 ? (
          <ul className="max-h-72 space-y-2 overflow-auto">
            {items.map((media) => (
              <li key={media.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(media.id)}
                  className={cn(
                    'flex w-full items-start gap-3 rounded-lg border px-3 py-2 text-left transition-colors',
                    selectedId === media.id
                      ? 'border-[var(--primary)] bg-[var(--primary)]/10'
                      : 'border-[var(--border)] hover:bg-[var(--secondary)]',
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-[#f0f4fa]">
                      {media.originalFilename || media.id}
                    </p>
                    <p className="text-xs text-[var(--muted-foreground)]">
                      {media.mimeType} · {(media.fileSize / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <Badge variant="secondary">{media.category}</Badge>
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={!selected}
            onClick={() => {
              if (!selected) return
              onSelect(selected)
              setSelectedId(null)
              onOpenChange(false)
            }}
          >
            Attach selected
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
