import { Link } from 'react-router-dom'

import { DataTable } from '@/components/shared/DataTable'
import { ErrorState } from '@/components/shared/ErrorState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { TableCell, TableHead, TableRow } from '@/components/ui/table'
import { useLiveRooms } from '@/hooks/queries/useLiveRooms'

export function ResultsPage() {
  // API accepts a single `state` filter only — fetch Completed and Closed separately.
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
        description="Completed and closed sessions. Open a room for podium, analytics, and export."
      />

      {isError ? (
        <ErrorState
          message="Failed to load session results"
          onRetry={() => {
            void completed.refetch()
            void closed.refetch()
          }}
        />
      ) : (
        <DataTable
          loading={isLoading}
          loadingLabel="Loading results…"
          empty={!isLoading && items.length === 0}
          emptyTitle="No completed sessions"
          emptyDescription="Finish a live room to see results here."
          emptyAction={
            <Button asChild>
              <Link to="/admin/live-rooms">Go to live rooms</Link>
            </Button>
          }
          columns={
            <>
              <TableHead>Quiz</TableHead>
              <TableHead>Code</TableHead>
              <TableHead>State</TableHead>
              <TableHead>Completed</TableHead>
              <TableHead />
            </>
          }
        >
          {items.map((room) => (
            <TableRow key={room.id}>
              <TableCell className="font-medium text-[var(--heading)]">
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
        </DataTable>
      )}
    </div>
  )
}
