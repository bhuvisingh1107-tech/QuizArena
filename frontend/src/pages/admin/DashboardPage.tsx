import { Archive, ClipboardPlus, FileEdit, Radio, Sparkles, Trophy, Users } from 'lucide-react'
import { Link } from 'react-router-dom'

import { DataTable } from '@/components/shared/DataTable'
import { ErrorState } from '@/components/shared/ErrorState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { TableCell, TableHead, TableRow } from '@/components/ui/table'
import { useDashboardSummary } from '@/hooks/queries/useDashboardSummary'
import { useLiveRooms } from '@/hooks/queries/useLiveRooms'
import { useQuizzes } from '@/hooks/queries/useQuizzes'

const ACTIVE_STATES = new Set(['Setup', 'Lobby', 'Active', 'Paused', 'SectionBreak'])

export function DashboardPage() {
  const summary = useDashboardSummary()
  const quizzes = useQuizzes({ limit: 5, offset: 0 })
  const rooms = useLiveRooms({ limit: 50, offset: 0 })

  const activeRooms = (rooms.data?.items ?? []).filter((r) => ACTIVE_STATES.has(r.state))
  const isLoading = summary.isLoading
  const isError = summary.isError

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Overview of quizzes, live sessions, and quick actions."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="accent">
              <Link to="/admin/quizzes/ai">
                <Sparkles className="h-4 w-4" />
                Generate with AI
              </Link>
            </Button>
            <Button asChild>
              <Link to="/admin/quizzes/new">
                <ClipboardPlus className="h-4 w-4" />
                Create Quiz
              </Link>
            </Button>
            <Button asChild variant="secondary">
              <Link to="/admin/live-rooms">
                <Radio className="h-4 w-4" />
                Create Live Room
              </Link>
            </Button>
          </div>
        }
      />

      {isError ? (
        <ErrorState
          message={
            summary.error instanceof Error
              ? summary.error.message
              : 'Failed to load dashboard summary'
          }
          onRetry={() => {
            void summary.refetch()
            void quizzes.refetch()
            void rooms.refetch()
          }}
        />
      ) : null}

      {!isError ? (
        <>
          <div className="mb-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Total quizzes"
              value={summary.data?.quizzesTotal ?? 0}
              loading={isLoading}
            />
            <StatCard
              label="Draft"
              value={summary.data?.quizzesDraft ?? 0}
              icon={<FileEdit className="h-3.5 w-3.5" />}
              loading={isLoading}
            />
            <StatCard
              label="Ready"
              value={summary.data?.quizzesReady ?? 0}
              loading={isLoading}
              valueClassName="text-[var(--primary)]"
            />
            <StatCard
              label="Live / In use"
              value={summary.data?.quizzesInUse ?? 0}
              loading={isLoading}
            />
            <StatCard
              label="Active rooms"
              value={summary.data?.roomsActive ?? 0}
              icon={<Radio className="h-3.5 w-3.5" />}
              loading={isLoading}
              valueClassName="text-[var(--primary)]"
            />
            <StatCard
              label="Completed rooms"
              value={summary.data?.roomsCompleted ?? 0}
              icon={<Trophy className="h-3.5 w-3.5" />}
              loading={isLoading}
            />
            <StatCard
              label="Archived quizzes"
              value={summary.data?.quizzesArchived ?? 0}
              icon={<Archive className="h-3.5 w-3.5" />}
              loading={isLoading}
            />
            <StatCard
              label="Participants today"
              value={summary.data?.participantsToday ?? 0}
              icon={<Users className="h-3.5 w-3.5" />}
              loading={isLoading}
            />
          </div>

          <div className="grid gap-8 xl:grid-cols-2">
            <div>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-display text-xl font-semibold">Recent quizzes</h2>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/admin/quizzes">View all</Link>
                </Button>
              </div>
              {quizzes.isLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : quizzes.isError ? (
                <ErrorState
                  message="Failed to load quizzes"
                  onRetry={() => void quizzes.refetch()}
                />
              ) : (
                <DataTable
                  empty={!quizzes.data?.items.length}
                  emptyTitle="No quizzes yet"
                  emptyDescription="Create manually or generate with AI."
                  emptyAction={
                    <div className="flex flex-wrap justify-center gap-2">
                      <Button asChild variant="accent">
                        <Link to="/admin/quizzes/ai">
                          <Sparkles className="h-4 w-4" />
                          Generate with AI
                        </Link>
                      </Button>
                      <Button asChild>
                        <Link to="/admin/quizzes/new">Create quiz</Link>
                      </Button>
                    </div>
                  }
                  columns={
                    <>
                      <TableHead>Title</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Updated</TableHead>
                    </>
                  }
                >
                  {quizzes.data?.items.map((quiz) => (
                    <TableRow key={quiz.id}>
                      <TableCell>
                        <Link
                          to={`/admin/quizzes/${quiz.id}`}
                          className="font-medium text-[var(--heading)] hover:text-[var(--primary)]"
                        >
                          {quiz.title}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={quiz.status} />
                      </TableCell>
                      <TableCell className="text-[var(--muted-foreground)]">
                        {new Date(quiz.updatedAt).toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </DataTable>
              )}
            </div>

            <div>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-display text-xl font-semibold">Active rooms</h2>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/admin/live-rooms">View all</Link>
                </Button>
              </div>
              {rooms.isLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : rooms.isError ? (
                <ErrorState message="Failed to load rooms" onRetry={() => void rooms.refetch()} />
              ) : (
                <DataTable
                  empty={activeRooms.length === 0}
                  emptyTitle="No active rooms"
                  emptyDescription="Create a live room from a Ready quiz."
                  emptyAction={
                    <Button asChild>
                      <Link to="/admin/live-rooms">Create live room</Link>
                    </Button>
                  }
                  columns={
                    <>
                      <TableHead>Quiz</TableHead>
                      <TableHead>Code</TableHead>
                      <TableHead>State</TableHead>
                    </>
                  }
                >
                  {activeRooms.slice(0, 5).map((room) => (
                    <TableRow key={room.id}>
                      <TableCell>
                        <Link
                          to={`/admin/live-rooms/${room.id}`}
                          className="font-medium text-[var(--heading)] hover:text-[var(--primary)]"
                        >
                          {room.quizTitleSnapshot}
                        </Link>
                      </TableCell>
                      <TableCell className="font-mono text-[var(--primary)]">
                        {room.roomCode}
                      </TableCell>
                      <TableCell>
                        <StatusBadge state={room.state} />
                      </TableCell>
                    </TableRow>
                  ))}
                </DataTable>
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
