import {
  Copy,
  Pause,
  Play,
  Radio,
  SkipForward,
  Square,
  DoorOpen,
  DoorClosed,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

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
import { useLiveRoomMutations } from '@/hooks/queries/useLiveRoomMutations'
import { useAdminWebSocket } from '@/hooks/useAdminWebSocket'
import { cn } from '@/lib/utils'
import { toastError, toastSuccess } from '@/lib/toast-helpers'

const connectionVariant: Record<string, 'default' | 'success' | 'warning' | 'danger' | 'secondary'> =
  {
    connecting: 'warning',
    connected: 'success',
    disconnected: 'secondary',
    error: 'danger',
  }

export function RoomMonitorPage() {
  const { roomId = '' } = useParams()
  const roomQuery = useLiveRoom(roomId)
  const live = useAdminWebSocket({ roomId, enabled: Boolean(roomId) })
  const {
    openLobby,
    toggleLobby,
    startSession,
    pauseSession,
    resumeSession,
    endSession,
    closeRoom,
  } = useLiveRoomMutations()

  const room = live.room ?? roomQuery.data ?? null
  const participants = Object.values(live.participants)

  const copy = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      toastSuccess(`${label} copied`)
    } catch {
      toastError(new Error('Clipboard unavailable'))
    }
  }

  const runRest = async (label: string, action: () => Promise<unknown>) => {
    try {
      await action()
      toastSuccess(label)
      void roomQuery.refetch()
    } catch (error) {
      toastError(error)
    }
  }

  const runWs = (type: string, label: string) => {
    const ok = live.send(type, {})
    if (ok) toastSuccess(label)
  }

  if (roomQuery.isLoading && !room) {
    return <LoadingState label="Loading room monitor…" />
  }

  if (roomQuery.isError && !room) {
    return (
      <ErrorState
        message={roomQuery.error instanceof Error ? roomQuery.error.message : 'Room not found'}
        onRetry={() => void roomQuery.refetch()}
      />
    )
  }

  if (!room) {
    return <ErrorState message="Room not found" />
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={room.quizTitleSnapshot}
        description={`Room code ${room.roomCode}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge state={room.state} />
            <Badge variant={connectionVariant[live.connectionStatus] ?? 'secondary'}>
              WS: {live.connectionStatus}
            </Badge>
            <Button asChild variant="outline" size="sm">
              <Link to="/admin/live-rooms">All rooms</Link>
            </Button>
          </div>
        }
      />

      {live.lastError ? (
        <ErrorState
          title="Live connection issue"
          message={live.lastError}
          onRetry={() => live.clearError()}
        />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Participants</CardDescription>
            <CardTitle className="text-3xl">{participants.length}</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-[var(--muted-foreground)]">
            From live WebSocket presence
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Submissions</CardDescription>
            <CardTitle className="text-3xl">{live.submissionCount}</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-[var(--muted-foreground)]">
            Current question
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Question index</CardDescription>
            <CardTitle className="text-3xl">
              {room.currentQuestionIndex ?? live.currentQuestion?.index ?? '—'}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Links</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center justify-between gap-2 rounded-md border border-[var(--border)] px-3 py-2 text-sm">
              <span className="truncate text-[var(--muted-foreground)]">{room.joinUrl}</span>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => void copy('Join URL', room.joinUrl)}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex items-center justify-between gap-2 rounded-md border border-[var(--border)] px-3 py-2 text-sm">
              <span className="truncate text-[var(--muted-foreground)]">{room.displayUrl}</span>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => void copy('Display URL', room.displayUrl)}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Room lifecycle</CardTitle>
            <CardDescription>REST controls</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => void runRest('Lobby opened', () => openLobby.mutateAsync(room.id))}
            >
              <DoorOpen className="h-4 w-4" />
              Open lobby
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void runRest('Lobby toggled', () => toggleLobby.mutateAsync(room.id))}
            >
              Toggle lobby
            </Button>
            <Button
              size="sm"
              onClick={() => void runRest('Session started', () => startSession.mutateAsync(room.id))}
            >
              <Play className="h-4 w-4" />
              Start
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void runRest('Paused', () => pauseSession.mutateAsync(room.id))}
            >
              <Pause className="h-4 w-4" />
              Pause
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void runRest('Resumed', () => resumeSession.mutateAsync(room.id))}
            >
              <Radio className="h-4 w-4" />
              Resume
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => void runRest('Session ended', () => endSession.mutateAsync(room.id))}
            >
              <Square className="h-4 w-4" />
              End
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void runRest('Room closed', () => closeRoom.mutateAsync(room.id))}
            >
              <DoorClosed className="h-4 w-4" />
              Close
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Quiz execution</CardTitle>
          <CardDescription>WebSocket admin controls</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => runWs('admin:start_question', 'Start question sent')}>
            Start question
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => runWs('admin:close_question', 'Close question sent')}
          >
            Close question
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => runWs('admin:reveal_answer', 'Reveal sent')}
          >
            Reveal answer
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => runWs('admin:next_question', 'Next question sent')}
          >
            <SkipForward className="h-4 w-4" />
            Next question
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => runWs('admin:next_section', 'Next section sent')}
          >
            Next section
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => runWs('admin:end_quiz', 'End quiz sent')}
          >
            End quiz
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Current question</CardTitle>
          </CardHeader>
          <CardContent>
            {live.currentQuestion ? (
              <div className="space-y-2 text-sm">
                <p className="font-medium text-[#f0f4fa]">
                  {live.currentQuestion.promptText ?? `Question #${live.currentQuestion.index}`}
                </p>
                <p className="text-[var(--muted-foreground)]">
                  State: {live.currentQuestion.state ?? '—'} · Submissions: {live.submissionCount}
                </p>
              </div>
            ) : (
              <p className="text-sm text-[var(--muted-foreground)]">No active question.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Leaderboard</CardTitle>
          </CardHeader>
          <CardContent>
            {live.leaderboard.length === 0 ? (
              <p className="text-sm text-[var(--muted-foreground)]">Waiting for scores…</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Score</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {live.leaderboard.map((entry) => (
                    <TableRow key={entry.participantId}>
                      <TableCell>{entry.rank}</TableCell>
                      <TableCell>{entry.displayName}</TableCell>
                      <TableCell>{entry.score}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Participants</CardTitle>
        </CardHeader>
        <CardContent>
          {participants.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">
              No participants yet. Open the lobby and share the join URL.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Connection</TableHead>
                  <TableHead>Score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {participants.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium text-[#f0f4fa]">{p.displayName}</TableCell>
                    <TableCell className="text-[var(--muted-foreground)]">
                      {p.email ?? '—'}
                    </TableCell>
                    <TableCell>{p.state}</TableCell>
                    <TableCell>
                      <span
                        className={cn(
                          'text-xs font-medium',
                          p.connected === false
                            ? 'text-[var(--destructive)]'
                            : 'text-[var(--color-success)]',
                        )}
                      >
                        {p.connected === false ? 'Offline' : 'Online'}
                      </span>
                    </TableCell>
                    <TableCell>{p.score ?? 0}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
