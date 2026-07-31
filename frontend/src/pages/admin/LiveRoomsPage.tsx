import { MoreHorizontal, Plus, Radio } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useLiveRoomMutations } from '@/hooks/queries/useLiveRoomMutations'
import { useLiveRooms } from '@/hooks/queries/useLiveRooms'
import { useQuizzes } from '@/hooks/queries/useQuizzes'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import type { RoomState } from '@/types/api'

const PAGE_SIZE = 20
const STATE_OPTIONS: Array<RoomState | 'all'> = [
  'all',
  'Setup',
  'Lobby',
  'Active',
  'Paused',
  'SectionBreak',
  'Completed',
  'Closed',
]

export function LiveRoomsPage() {
  const navigate = useNavigate()
  const [state, setState] = useState<RoomState | 'all'>('all')
  const [offset, setOffset] = useState(0)
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedQuizId, setSelectedQuizId] = useState('')

  const roomsQuery = useLiveRooms({
    offset,
    limit: PAGE_SIZE,
    state: state === 'all' ? undefined : state,
  })
  const readyQuizzes = useQuizzes({ status: 'Ready', limit: 100 })
  const { createRoom, openLobby, startSession, deleteRoom } = useLiveRoomMutations()

  const total = roomsQuery.data?.total ?? 0
  const items = roomsQuery.data?.items ?? []
  const quizOptions = useMemo(
    () => readyQuizzes.data?.items ?? [],
    [readyQuizzes.data],
  )

  const create = async () => {
    if (!selectedQuizId) {
      toastError(new Error('Select a Ready quiz'))
      return
    }
    try {
      const room = await createRoom.mutateAsync({ quizId: selectedQuizId })
      toastSuccess('Live room created')
      setCreateOpen(false)
      navigate(`/admin/live-rooms/${room.id}`)
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <div>
      <PageHeader
        title="Live Rooms"
        description="Create sessions from Ready quizzes and open the host monitor."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Create live room
          </Button>
        }
      />

      <div className="mb-4">
        <Select
          value={state}
          onValueChange={(value) => {
            setState(value as RoomState | 'all')
            setOffset(0)
          }}
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Filter state" />
          </SelectTrigger>
          <SelectContent>
            {STATE_OPTIONS.map((option) => (
              <SelectItem key={option} value={option}>
                {option === 'all' ? 'All states' : option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {roomsQuery.isLoading ? <LoadingState label="Loading rooms…" /> : null}
      {roomsQuery.isError ? (
        <ErrorState
          message={
            roomsQuery.error instanceof Error
              ? roomsQuery.error.message
              : 'Failed to load live rooms'
          }
          onRetry={() => void roomsQuery.refetch()}
        />
      ) : null}

      {!roomsQuery.isLoading && !roomsQuery.isError && items.length === 0 ? (
        <EmptyState
          title="No live rooms"
          description="Create a room from a Ready quiz to start hosting."
          action={
            <Button onClick={() => setCreateOpen(true)}>
              <Radio className="h-4 w-4" />
              Create live room
            </Button>
          }
        />
      ) : null}

      {!roomsQuery.isLoading && !roomsQuery.isError && items.length > 0 ? (
        <>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)]/60">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Quiz</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((room) => (
                  <TableRow key={room.id}>
                    <TableCell className="font-medium text-[#f0f4fa]">
                      <Link
                        to={`/admin/live-rooms/${room.id}`}
                        className="hover:text-[var(--primary)]"
                      >
                        {room.quizTitleSnapshot}
                      </Link>
                    </TableCell>
                    <TableCell className="font-mono text-[var(--primary)]">{room.roomCode}</TableCell>
                    <TableCell>
                      <StatusBadge state={room.state} />
                    </TableCell>
                    <TableCell className="text-[var(--muted-foreground)]">
                      {new Date(room.createdAt).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" aria-label="Room actions">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => navigate(`/admin/live-rooms/${room.id}`)}
                          >
                            Open monitor
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              void openLobby
                                .mutateAsync(room.id)
                                .then(() => toastSuccess('Lobby opened'))
                                .catch(toastError)
                            }
                          >
                            Open lobby
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              void startSession
                                .mutateAsync(room.id)
                                .then(() => toastSuccess('Session started'))
                                .catch(toastError)
                            }
                          >
                            Start
                          </DropdownMenuItem>
                          {(room.state === 'Setup' || room.state === 'Closed') && (
                            <>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                className="text-[var(--destructive)]"
                                onClick={() => {
                                  if (!window.confirm('Delete this room?')) return
                                  void deleteRoom
                                    .mutateAsync(room.id)
                                    .then(() => toastSuccess('Room deleted'))
                                    .catch(toastError)
                                }}
                              >
                                Delete
                              </DropdownMenuItem>
                            </>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="mt-4 flex items-center justify-between text-sm text-[var(--muted-foreground)]">
            <p>
              Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      ) : null}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create live room</DialogTitle>
            <DialogDescription>Select a Ready quiz to snapshot into a session.</DialogDescription>
          </DialogHeader>
          <Select value={selectedQuizId} onValueChange={setSelectedQuizId}>
            <SelectTrigger>
              <SelectValue placeholder="Choose quiz" />
            </SelectTrigger>
            <SelectContent>
              {quizOptions.map((quiz) => (
                <SelectItem key={quiz.id} value={quiz.id}>
                  {quiz.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {quizOptions.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">
              No Ready quizzes available. Publish a quiz first.
            </p>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void create()} disabled={!selectedQuizId}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
