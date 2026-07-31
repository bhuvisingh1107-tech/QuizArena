import { MoreHorizontal, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
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
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { useQuizMutations } from '@/hooks/queries/useQuizMutations'
import { useQuizzes } from '@/hooks/queries/useQuizzes'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import type { QuizStatus } from '@/types/api'

const PAGE_SIZE = 20
const STATUS_OPTIONS: Array<QuizStatus | 'all'> = [
  'all',
  'Draft',
  'Ready',
  'InUse',
  'Archived',
  'Deleted',
]

export function QuizzesPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<QuizStatus | 'all'>('all')
  const [offset, setOffset] = useState(0)
  const debouncedSearch = useDebouncedValue(search, 350)

  const { data, isLoading, isError, error, refetch, isFetching } = useQuizzes({
    offset,
    limit: PAGE_SIZE,
    search: debouncedSearch || undefined,
    status: status === 'all' ? undefined : status,
  })

  const {
    duplicateQuiz,
    deleteQuiz,
    publishQuiz,
    archiveQuiz,
  } = useQuizMutations()

  const total = data?.total ?? 0
  const canPrev = offset > 0
  const canNext = offset + PAGE_SIZE < total

  const runAction = async (
    label: string,
    action: () => Promise<unknown>,
  ) => {
    try {
      await action()
      toastSuccess(label)
      void refetch()
    } catch (err) {
      toastError(err)
    }
  }

  return (
    <div>
      <PageHeader
        title="Quizzes"
        description="Search, filter, and manage quiz templates."
        actions={
          <Button asChild>
            <Link to="/admin/quizzes/new">
              <Plus className="h-4 w-4" />
              Create quiz
            </Link>
          </Button>
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <Input
          placeholder="Search by title…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setOffset(0)
          }}
          className="sm:max-w-sm"
        />
        <Select
          value={status}
          onValueChange={(value) => {
            setStatus(value as QuizStatus | 'all')
            setOffset(0)
          }}
        >
          <SelectTrigger className="sm:w-44">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((option) => (
              <SelectItem key={option} value={option}>
                {option === 'all' ? 'All statuses' : option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading ? <LoadingState label="Loading quizzes…" /> : null}
      {isError ? (
        <ErrorState
          message={error instanceof Error ? error.message : 'Failed to load quizzes'}
          onRetry={() => void refetch()}
        />
      ) : null}

      {!isLoading && !isError && data?.items.length === 0 ? (
        <EmptyState
          title="No quizzes found"
          description="Try another search, or create a new quiz."
          action={
            <Button asChild>
              <Link to="/admin/quizzes/new">Create quiz</Link>
            </Button>
          }
        />
      ) : null}

      {!isLoading && !isError && data && data.items.length > 0 ? (
        <>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)]/60">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((quiz) => (
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
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" aria-label="Quiz actions">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => navigate(`/admin/quizzes/${quiz.id}`)}>
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              void runAction('Quiz duplicated', () =>
                                duplicateQuiz.mutateAsync(quiz.id),
                              )
                            }
                          >
                            Duplicate
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              void runAction('Quiz published', () =>
                                publishQuiz.mutateAsync(quiz.id),
                              )
                            }
                          >
                            Publish / validate
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              void runAction('Quiz archived', () =>
                                archiveQuiz.mutateAsync(quiz.id),
                              )
                            }
                          >
                            Archive
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className="text-[var(--destructive)]"
                            onClick={() => {
                              if (!window.confirm(`Delete “${quiz.title}”?`)) return
                              void runAction('Quiz deleted', () =>
                                deleteQuiz.mutateAsync({ quizId: quiz.id }),
                              )
                            }}
                          >
                            Delete
                          </DropdownMenuItem>
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
              {isFetching ? ' · refreshing…' : ''}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={!canPrev}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!canNext}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
