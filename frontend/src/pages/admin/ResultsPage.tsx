import { Link } from 'react-router-dom'

import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useLiveRooms } from '@/hooks/queries/useLiveRooms'

export function ResultsPage() {
  const completed = useLiveRooms({ state: 'Completed', limit: 50 })
  const closed = useLiveRooms({ state: 'Closed', limit: 50 })

  const isLoading = completed.isLoading || closed.isLoading
  const isError = completed.isError || closed.isError

  const items = [
    ...(completed.data?.items ?? []),
    ...(closed.data?.items ?? []),
  ].sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())

  return (
    <div>
      <PageHeader
        title="Results"
        description="Completed and closed sessions. Open a room for podium and leaderboard."
      />

      {isLoading ? <LoadingState label="Loading results…" /> : null}
      {isError ? (
        <ErrorState
          message="Failed to load session results"
          onRetry={() => {
            void completed.refetch()
            void closed.refetch()
          }}
        />
      ) : null}

      {!isLoading && !isError && items.length === 0 ? (
        <EmptyState
          title="No completed sessions"
          description="Finish a live room to see results here."
          action={
            <Button asChild>
              <Link to="/admin/live-rooms">Go to live rooms</Link>
            </Button>
          }
        />
      ) : null}

      {!isLoading && !isError && items.length > 0 ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)]/60">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Quiz</TableHead>
                <TableHead>Code</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Completed</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((room) => (
                <TableRow key={room.id}>
                  <TableCell className="font-medium text-[#f0f4fa]">
                    {room.quizTitleSnapshot}
                  </TableCell>
                  <TableCell className="font-mono text-[var(--primary)]">{room.roomCode}</TableCell>
                  <TableCell>
                    <StatusBadge state={room.state} />
                  </TableCell>
                  <TableCell className="text-[var(--muted-foreground)]">
                    {room.completedAt
                      ? new Date(room.completedAt).toLocaleString()
                      : new Date(room.updatedAt).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Button asChild size="sm" variant="secondary">
                      <Link to={`/admin/results/${room.id}`}>View results</Link>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
    </div>
  )
}
