import { Link, useParams } from 'react-router-dom'

import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useLiveRoom } from '@/hooks/queries/useLiveRoom'
import { useAdminWebSocket } from '@/hooks/useAdminWebSocket'

export function RoomResultsPage() {
  const { roomId = '' } = useParams()
  const roomQuery = useLiveRoom(roomId)
  const live = useAdminWebSocket({
    roomId,
    enabled: Boolean(roomId) && Boolean(roomQuery.data),
  })

  const room = live.room ?? roomQuery.data ?? null
  const leaderboard = live.leaderboard
  const podium = live.podium?.entries ?? leaderboard.slice(0, 3).map((entry, index) => ({
    rank: (index + 1) as 1 | 2 | 3,
    participantId: entry.participantId,
    displayName: entry.displayName,
    score: entry.score,
  }))

  if (roomQuery.isLoading) return <LoadingState label="Loading results…" />
  if (roomQuery.isError || !room) {
    return (
      <ErrorState
        message={roomQuery.error instanceof Error ? roomQuery.error.message : 'Room not found'}
        onRetry={() => void roomQuery.refetch()}
      />
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={room.quizTitleSnapshot}
        description={`Results for room ${room.roomCode}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge state={room.state} />
            <Badge variant="secondary">WS: {live.connectionStatus}</Badge>
            <Button asChild variant="outline" size="sm">
              <Link to="/admin/results">Back</Link>
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((index) => {
          const entry = podium[index]
          return (
            <Card key={index} className={index === 0 ? 'border-[var(--accent)]/50' : undefined}>
              <CardHeader>
                <CardDescription>#{index + 1}</CardDescription>
                <CardTitle className="text-xl">
                  {entry?.displayName ?? '—'}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-semibold text-[var(--primary)]">
                {entry?.score ?? '—'}
              </CardContent>
            </Card>
          )
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Final leaderboard</CardTitle>
          <CardDescription>
            Loaded via WebSocket resync when available for completed rooms.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {leaderboard.length === 0 ? (
            <EmptyState
              title="No leaderboard data yet"
              description="Connect while the room still allows admin WS access, or wait for scoring events."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rank</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Streak</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leaderboard.map((entry) => (
                  <TableRow key={entry.participantId}>
                    <TableCell>{entry.rank}</TableCell>
                    <TableCell className="font-medium text-[#f0f4fa]">
                      {entry.displayName}
                    </TableCell>
                    <TableCell>{entry.score}</TableCell>
                    <TableCell>{entry.streak ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <EmptyState
        title="Analytics API not available yet"
        description="Question and section analytics endpoints are not implemented on the backend. Leaderboard and podium above are shown when the live resync provides them."
      />
    </div>
  )
}
