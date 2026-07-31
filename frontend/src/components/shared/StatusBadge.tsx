import { Badge, type BadgeProps } from '@/components/ui/badge'
import type { QuizStatus, RoomState } from '@/types/api'

const quizVariant: Record<QuizStatus, BadgeProps['variant']> = {
  Draft: 'secondary',
  Ready: 'success',
  InUse: 'default',
  Archived: 'warning',
  Deleted: 'danger',
}

const roomVariant: Record<RoomState, BadgeProps['variant']> = {
  Setup: 'secondary',
  Lobby: 'accent',
  Active: 'success',
  Paused: 'warning',
  SectionBreak: 'default',
  Completed: 'outline',
  Closed: 'danger',
}

interface QuizStatusBadgeProps {
  status: QuizStatus
  className?: string
}

export function QuizStatusBadge({ status, className }: QuizStatusBadgeProps) {
  return (
    <Badge variant={quizVariant[status]} className={className}>
      {status}
    </Badge>
  )
}

interface RoomStatusBadgeProps {
  state: RoomState
  className?: string
}

export function RoomStatusBadge({ state, className }: RoomStatusBadgeProps) {
  return (
    <Badge variant={roomVariant[state]} className={className}>
      {state}
    </Badge>
  )
}

/** Convenience alias matching the brief. */
export function StatusBadge({
  status,
  state,
  className,
}: {
  status?: QuizStatus
  state?: RoomState
  className?: string
}) {
  if (status) return <QuizStatusBadge status={status} className={className} />
  if (state) return <RoomStatusBadge state={state} className={className} />
  return null
}
