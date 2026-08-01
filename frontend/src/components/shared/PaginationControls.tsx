import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface PaginationControlsProps {
  offset: number
  limit: number
  total: number
  onOffsetChange: (offset: number) => void
  isFetching?: boolean
  className?: string
}

export function PaginationControls({
  offset,
  limit,
  total,
  onOffsetChange,
  isFetching,
  className,
}: PaginationControlsProps) {
  const canPrev = offset > 0
  const canNext = offset + limit < total
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + limit, total)

  return (
    <div
      className={cn(
        'mt-4 flex flex-col gap-3 text-sm text-[var(--muted-foreground)] sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
    >
      <p>
        Showing {from}–{to} of {total}
        {isFetching ? ' · refreshing…' : ''}
      </p>
      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!canPrev}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
        >
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!canNext}
          onClick={() => onOffsetChange(offset + limit)}
        >
          Next
        </Button>
      </div>
    </div>
  )
}
