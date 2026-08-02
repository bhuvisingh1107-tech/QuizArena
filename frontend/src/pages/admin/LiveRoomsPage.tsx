import { MoreHorizontal, Plus, Radio } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ConfirmDialog } from '@/components/shared/ConfirmDialog'
import { DataTable } from '@/components/shared/DataTable'
import { ErrorState } from '@/components/shared/ErrorState'
import { PageHeader } from '@/components/shared/PageHeader'
import { PaginationControls } from '@/components/shared/PaginationControls'
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
import { TableCell, TableHead, TableRow } from '@/components/ui/table'
import { useLiveRoomMutations } from '@/hooks/queries/useLiveRoomMutations'
import { useLiveRooms } from '@/hooks/queries/useLiveRooms'
import { useQuizzes } from '@/hooks/queries/useQuizzes'
import { canRest } from '@/lib/room-lifecycle'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import type { LiveRoom, RoomState } from '@/types/api'

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
  const [deleteTarget, setDeleteTarget] = useState<LiveRoom | null>(null)
  const [deleting, setDeleting] = useState(false)

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
      setSelectedQuizId('')
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

      {roomsQuery.isError ? (
        <ErrorState
          message={
            roomsQuery.error instanceof Error
              ? roomsQuery.error.message
              : 'Failed to load live rooms'
          }
          onRetry={() => void roomsQuery.refetch()}
        />
      ) : (
        <>
          <DataTable
            loading={roomsQuery.isLoading}
            loadingLabel="Loading rooms…"
            empty={!roomsQuery.isLoading && items.length === 0}
            emptyTitle="No live rooms"
            emptyDescription="Create a room from a Ready quiz to start hosting."
            emptyAction={
              <Button onClick={() => setCreateOpen(true)}>
                <Radio className="h-4 w-4" />
                Create live room
              </Button>
            }
            columns={
              <>
                <TableHead>Quiz</TableHead>
                <TableHead>Code</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="w-12" />
              </>
            }
          >
            {items.map((room) => (
              <TableRow key={room.id}>
                <TableCell className="font-medium text-[var(--heading)]">
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
                      {(room.state === 'Completed' || room.state === 'Closed') && (
                        <DropdownMenuItem
                          onClick={() => navigate(`/admin/results/${room.id}`)}
                        >
                          View results
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem
                        disabled={!canRest(room.state, 'openLobby')}
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
                        disabled={!canRest(room.state, 'start')}
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
                            onClick={() => setDeleteTarget(room)}
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
          </DataTable>

          {!roomsQuery.isLoading && items.length > 0 ? (
            <PaginationControls
              offset={offset}
              limit={PAGE_SIZE}
              total={total}
              onOffsetChange={setOffset}
              isFetching={roomsQuery.isFetching}
            />
          ) : null}
        </>
      )}

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
            <Button
              onClick={() => void create()}
              disabled={!selectedQuizId || createRoom.isPending}
            >
              {createRoom.isPending ? 'Creating…' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        title="Delete live room?"
        description={
          deleteTarget
            ? `Delete room ${deleteTarget.roomCode} (${deleteTarget.quizTitleSnapshot})?`
            : undefined
        }
        confirmLabel="Delete"
        variant="destructive"
        loading={deleting}
        onConfirm={async () => {
          if (!deleteTarget) return
          setDeleting(true)
          try {
            await deleteRoom.mutateAsync(deleteTarget.id)
            toastSuccess('Room deleted')
            setDeleteTarget(null)
          } catch (error) {
            toastError(error)
          } finally {
            setDeleting(false)
          }
        }}
      />
    </div>
  )
}
