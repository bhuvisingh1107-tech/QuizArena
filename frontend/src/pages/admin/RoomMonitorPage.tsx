import {
  Copy,
  DoorClosed,
  DoorOpen,
  Pause,
  Play,
  Printer,
  Square,
  Trophy,
} from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ConfirmDialog } from '@/components/shared/ConfirmDialog'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
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
import { useRoomParticipants } from '@/hooks/queries/useRoomParticipants'
import { useRoomResults } from '@/hooks/queries/useRoomResults'
import { useAdminWebSocket } from '@/hooks/useAdminWebSocket'
import { cn } from '@/lib/utils'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import type { LiveParticipant, RoomState } from '@/types/api'

const connectionVariant: Record<string, 'default' | 'success' | 'warning' | 'danger' | 'secondary'> =
  {
    connecting: 'warning',
    connected: 'success',
    disconnected: 'secondary',
    error: 'danger',
  }

function canRest(
  state: RoomState,
  action: 'openLobby' | 'toggle' | 'start' | 'pause' | 'resume' | 'end' | 'close',
): boolean {
  switch (action) {
    case 'openLobby':
      return state === 'Setup'
    case 'toggle':
      return state === 'Lobby'
    case 'start':
      return state === 'Lobby'
    case 'pause':
      return state === 'Active'
    case 'resume':
      return state === 'Paused'
    case 'end':
      return state === 'Active' || state === 'Paused' || state === 'SectionBreak'
    case 'close':
      return state === 'Lobby' || state === 'Completed'
    default:
      return false
  }
}

function formatTimer(
  timerEndsAt?: string | null,
  _tick = 0,
  paused = false,
): string {
  void _tick
  if (!timerEndsAt) return 'Manual timing'
  const end = new Date(timerEndsAt).getTime()
  const remaining = Math.max(0, Math.ceil((end - Date.now()) / 1000))
  const m = Math.floor(remaining / 60)
  const s = remaining % 60
  const label = `${m}:${String(s).padStart(2, '0')} remaining`
  return paused ? `${label} (paused)` : label
}

export function RoomMonitorPage() {
  const { roomId = '' } = useParams()
  const roomQuery = useLiveRoom(roomId)
  const participantsQuery = useRoomParticipants(roomId)
  const live = useAdminWebSocket({ roomId, enabled: Boolean(roomId) })
  const resultsQuery = useRoomResults(
    roomId,
    Boolean(roomId) &&
      (live.room?.state === 'Completed' ||
        roomQuery.data?.state === 'Completed' ||
        roomQuery.data?.state === 'Closed'),
  )
  const {
    openLobby,
    toggleLobby,
    startSession,
    pauseSession,
    resumeSession,
    endSession,
    closeRoom,
  } = useLiveRoomMutations()

  const [endConfirm, setEndConfirm] = useState(false)
  const [closeConfirm, setCloseConfirm] = useState(false)
  const [timerTick, setTimerTick] = useState(0)

  const timerEndsAt = live.currentQuestion?.timerEndsAt
  const roomPaused = (live.room?.state ?? roomQuery.data?.state) === 'Paused'

  useEffect(() => {
    if (!timerEndsAt || roomPaused) return
    const id = setInterval(() => setTimerTick((t) => t + 1), 500)
    return () => clearInterval(id)
  }, [timerEndsAt, roomPaused])

  const room = live.room ?? roomQuery.data ?? null

  const participants = useMemo(() => {
    const map = new Map<string, LiveParticipant>()

    for (const p of participantsQuery.data?.items ?? []) {
      map.set(p.id, {
        id: p.id,
        displayName: p.displayName,
        email: p.email,
        state: p.state,
        score: p.totalScore,
        connected: p.connectionStatus === 'connected',
      })
    }

    for (const p of Object.values(live.participants)) {
      const existing = map.get(p.id)
      map.set(p.id, {
        ...existing,
        ...p,
        email: p.email ?? existing?.email ?? null,
        score: p.score ?? existing?.score ?? 0,
        connected: p.connected ?? existing?.connected,
      })
    }

    return [...map.values()].sort((a, b) => a.displayName.localeCompare(b.displayName))
  }, [participantsQuery.data?.items, live.participants])

  const leaderboard =
    live.leaderboard.length > 0
      ? live.leaderboard
      : (resultsQuery.data?.leaderboard ?? []).map((e) => ({
          rank: e.rank,
          participantId: e.participantId,
          displayName: e.displayName,
          score: e.score,
          streak: e.streak,
        }))

  const questionIndex =
    room?.currentQuestionIndex ?? live.currentQuestion?.index ?? null
  const questionTotal = room?.questionCount ?? null
  const sectionLabel =
    (live.currentQuestion as { sectionName?: string } | null)?.sectionName ??
    null

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
      void participantsQuery.refetch()
    } catch (error) {
      toastError(error)
    }
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

  const state = room.state
  const qrTarget = room.qrTarget || room.joinUrl
  const isCompleted = state === 'Completed' || state === 'Closed'

  return (
    <div className="space-y-6">
      <PageHeader
        title={room.quizTitleSnapshot}
        description="Host dashboard — control lobby, questions, and participants."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge state={state} />
            <Badge variant={connectionVariant[live.connectionStatus] ?? 'secondary'}>
              {live.connectionStatus === 'connected'
                ? 'Live'
                : live.connectionStatus === 'connecting'
                  ? 'Connecting…'
                  : live.connectionStatus === 'error'
                    ? 'Connection issue'
                    : 'Reconnecting…'}
            </Badge>
            {isCompleted ? (
              <Button asChild variant="secondary" size="sm">
                <Link to={`/admin/results/${room.id}`}>
                  <Trophy className="h-4 w-4" />
                  Results
                </Link>
              </Button>
            ) : null}
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
          onRetry={() => {
            live.clearError()
            live.reconnect()
          }}
        />
      ) : null}

      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-8 sm:flex-row sm:justify-between">
          <div className="text-center sm:text-left">
            <p className="text-sm uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
              Room code
            </p>
            <p className="font-display text-5xl font-extrabold tracking-[0.2em] text-[var(--primary)] sm:text-6xl">
              {room.roomCode}
            </p>
            {room.lobbySubState ? (
              <p className="mt-2 text-sm text-[var(--muted-foreground)]">
                Lobby: {room.lobbySubState}
              </p>
            ) : null}
          </div>
          <div className="rounded-xl bg-white p-3">
            <QRCodeSVG value={qrTarget} size={140} level="M" />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Participants" value={participants.length} />
        <StatCard label="Submissions" value={live.submissionCount} description="Current question" />
        <StatCard
          label="Progress"
          value={
            questionIndex != null && questionTotal
              ? `${questionIndex + 1}/${questionTotal}`
              : questionIndex != null
                ? String(questionIndex + 1)
                : '—'
          }
          description={sectionLabel ? `Section: ${sectionLabel}` : undefined}
        />
        <StatCard
          label="Timer"
          value={formatTimer(timerEndsAt, timerTick, roomPaused)}
          valueClassName="text-xl"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Join & display links</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center justify-between gap-2 rounded-md border border-[var(--border)] px-3 py-2 text-sm">
              <div className="min-w-0">
                <p className="text-xs text-[var(--muted-foreground)]">Join</p>
                <p className="truncate">{room.joinUrl}</p>
              </div>
              <Button
                size="icon"
                variant="ghost"
                aria-label="Copy join link"
                onClick={() => void copy('Join URL', room.joinUrl)}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex items-center justify-between gap-2 rounded-md border border-[var(--border)] px-3 py-2 text-sm">
              <div className="min-w-0">
                <p className="text-xs text-[var(--muted-foreground)]">Display</p>
                <p className="truncate">{room.displayUrl}</p>
              </div>
              <Button
                size="icon"
                variant="ghost"
                aria-label="Copy display link"
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
            <CardDescription>
              Start the quiz to begin automatic question progression. Pause freezes the timer.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={!canRest(state, 'openLobby')}
              onClick={() => void runRest('Lobby opened', () => openLobby.mutateAsync(room.id))}
            >
              <DoorOpen className="h-4 w-4" />
              Open lobby
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!canRest(state, 'toggle')}
              onClick={() => void runRest('Lobby toggled', () => toggleLobby.mutateAsync(room.id))}
            >
              Toggle lobby
            </Button>
            <Button
              size="sm"
              disabled={!canRest(state, 'start')}
              onClick={() =>
                void runRest('Quiz started', () => startSession.mutateAsync(room.id))
              }
            >
              <Play className="h-4 w-4" />
              Start Quiz
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!canRest(state, 'pause')}
              onClick={() => void runRest('Paused', () => pauseSession.mutateAsync(room.id))}
            >
              <Pause className="h-4 w-4" />
              Pause
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!canRest(state, 'resume')}
              onClick={() => void runRest('Resumed', () => resumeSession.mutateAsync(room.id))}
            >
              <Play className="h-4 w-4" />
              Resume
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={!canRest(state, 'end')}
              onClick={() => setEndConfirm(true)}
            >
              <Square className="h-4 w-4" />
              End Quiz
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!canRest(state, 'close')}
              onClick={() => setCloseConfirm(true)}
            >
              <DoorClosed className="h-4 w-4" />
              Close
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Live progression</CardTitle>
          <CardDescription>
            Questions advance automatically after the timer expires or everyone answers: reveal →
            explanation → next question → leaderboard when finished.
          </CardDescription>
        </CardHeader>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Current question</CardTitle>
          </CardHeader>
          <CardContent>
            {live.currentQuestion ? (
              <div className="space-y-2 text-sm">
                <p className="font-medium text-[var(--heading)]">
                  {live.currentQuestion.promptText ?? `Question #${live.currentQuestion.index}`}
                </p>
                <p className="text-[var(--muted-foreground)]">
                  State: {live.currentQuestion.state ?? '—'}
                  {sectionLabel ? ` · Section: ${sectionLabel}` : ''}
                  {' · '}
                  Submissions: {live.submissionCount}
                </p>
              </div>
            ) : (
              <p className="text-sm text-[var(--muted-foreground)]">No active question.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Leaderboard preview</CardTitle>
            {isCompleted ? (
              <Button asChild size="sm" variant="ghost">
                <Link to={`/admin/results/${room.id}`}>
                  <Printer className="h-4 w-4" />
                  Full results
                </Link>
              </Button>
            ) : null}
          </CardHeader>
          <CardContent>
            {leaderboard.length === 0 ? (
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
                  {leaderboard.slice(0, 10).map((entry) => (
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
          <CardDescription>
            Seeded from REST, updated via WebSocket presence
            {participantsQuery.isFetching ? ' · refreshing…' : ''}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {participantsQuery.isError && participants.length === 0 ? (
            <ErrorState
              message="Failed to load participants"
              onRetry={() => void participantsQuery.refetch()}
            />
          ) : participants.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">
              No participants yet. Open the lobby and share the join QR or URL.
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
                    <TableCell className="font-medium text-[var(--heading)]">
                      {p.displayName}
                    </TableCell>
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

      <ConfirmDialog
        open={endConfirm}
        onOpenChange={setEndConfirm}
        title="End quiz?"
        description="End the live quiz for all participants. You can still view results afterward."
        confirmLabel="End Quiz"
        variant="destructive"
        onConfirm={async () => {
          await runRest('Quiz ended', () => endSession.mutateAsync(room.id))
          setEndConfirm(false)
        }}
      />

      <ConfirmDialog
        open={closeConfirm}
        onOpenChange={setCloseConfirm}
        title="Close room?"
        description="Close this room permanently. Participants will no longer be able to join."
        confirmLabel="Close room"
        variant="destructive"
        onConfirm={async () => {
          await runRest('Room closed', () => closeRoom.mutateAsync(room.id))
          setCloseConfirm(false)
        }}
      />
    </div>
  )
}
