import { ClipboardPlus, ImagePlus, Radio, Users } from 'lucide-react'
import { Link } from 'react-router-dom'

import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
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
import { useLiveRooms } from '@/hooks/queries/useLiveRooms'
import { useQuizzes } from '@/hooks/queries/useQuizzes'

const ACTIVE_STATES = new Set(['Setup', 'Lobby', 'Active', 'Paused', 'SectionBreak'])

export function DashboardPage() {
  const quizzes = useQuizzes({ limit: 5, offset: 0 })
  const allRooms = useLiveRooms({ limit: 100, offset: 0 })

  const rooms = allRooms.data?.items ?? []
  const activeCount = rooms.filter((r) => ACTIVE_STATES.has(r.state)).length
  const completedCount = rooms.filter((r) => r.state === 'Completed' || r.state === 'Closed').length

  const isLoading = quizzes.isLoading || allRooms.isLoading
  const isError = quizzes.isError || allRooms.isError

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Overview of quizzes, live sessions, and quick actions."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link to="/admin/quizzes/new">
                <ClipboardPlus className="h-4 w-4" />
                Create quiz
              </Link>
            </Button>
            <Button asChild variant="secondary">
              <Link to="/admin/live-rooms">
                <Radio className="h-4 w-4" />
                Create live room
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/admin/media">
                <ImagePlus className="h-4 w-4" />
                Open media
              </Link>
            </Button>
          </div>
        }
      />

      {isLoading ? <LoadingState label="Loading dashboard…" /> : null}
      {isError ? (
        <ErrorState
          message="Failed to load dashboard metrics"
          onRetry={() => {
            void quizzes.refetch()
            void allRooms.refetch()
          }}
        />
      ) : null}

      {!isLoading && !isError ? (
        <>
          <div className="mb-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Total quizzes</CardDescription>
                <CardTitle className="text-3xl">{quizzes.data?.total ?? 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Active rooms</CardDescription>
                <CardTitle className="text-3xl text-[var(--primary)]">{activeCount}</CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-[var(--muted-foreground)]">
                Setup, Lobby, Active, Paused, SectionBreak
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Completed rooms</CardDescription>
                <CardTitle className="text-3xl">{completedCount}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-1.5">
                  <Users className="h-3.5 w-3.5" />
                  Participants today
                </CardDescription>
                <CardTitle className="text-3xl text-[var(--muted-foreground)]">—</CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-[var(--muted-foreground)]">
                Live only — no REST aggregate endpoint; visible while monitoring a room.
              </CardContent>
            </Card>
          </div>

          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-display text-xl font-semibold text-[#f0f4fa]">Recent quizzes</h2>
              <Button asChild variant="ghost" size="sm">
                <Link to="/admin/quizzes">View all</Link>
              </Button>
            </div>

            {!quizzes.data?.items.length ? (
              <EmptyState
                title="No quizzes yet"
                description="Create your first quiz to get started."
                action={
                  <Button asChild>
                    <Link to="/admin/quizzes/new">Create quiz</Link>
                  </Button>
                }
              />
            ) : (
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)]/60">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Title</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Updated</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {quizzes.data.items.map((quiz) => (
                      <TableRow key={quiz.id}>
                        <TableCell>
                          <Link
                            to={`/admin/quizzes/${quiz.id}`}
                            className="font-medium text-[#f0f4fa] hover:text-[var(--primary)]"
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
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  )
}
