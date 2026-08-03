import { MoreHorizontal, Plus, Radio, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ConfirmDialog } from '@/components/shared/ConfirmDialog'
import { DataTable } from '@/components/shared/DataTable'
import { ErrorState } from '@/components/shared/ErrorState'
import { PageHeader } from '@/components/shared/PageHeader'
import { PaginationControls } from '@/components/shared/PaginationControls'
import { SearchBar } from '@/components/shared/SearchBar'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { useLiveRoomMutations } from '@/hooks/queries/useLiveRoomMutations'
import { useOptions } from '@/hooks/queries/useOptions'
import { useQuestions } from '@/hooks/queries/useQuestions'
import { useQuizMutations } from '@/hooks/queries/useQuizMutations'
import { useQuizzes } from '@/hooks/queries/useQuizzes'
import { useSections } from '@/hooks/queries/useSections'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import type { Quiz, QuizStatus } from '@/types/api'

const PAGE_SIZE = 20
const STATUS_OPTIONS: Array<QuizStatus | 'all'> = [
  'all',
  'Draft',
  'Ready',
  'InUse',
  'Archived',
  'Deleted',
]

type SortKey = 'title' | 'updated' | 'status'

type ConfirmAction =
  | { type: 'delete'; quiz: Quiz }
  | { type: 'archive'; quiz: Quiz }
  | { type: 'bulk-delete' }
  | { type: 'bulk-archive' }
  | null

export function QuizzesPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<QuizStatus | 'all'>('all')
  const [offset, setOffset] = useState(0)
  const [sortKey, setSortKey] = useState<SortKey>('updated')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [confirm, setConfirm] = useState<ConfirmAction>(null)
  const [confirmLoading, setConfirmLoading] = useState(false)
  const [previewQuiz, setPreviewQuiz] = useState<Quiz | null>(null)
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
    restoreQuiz,
  } = useQuizMutations()
  const { createRoom } = useLiveRoomMutations()

  const items = useMemo(() => {
    const list = [...(data?.items ?? [])]
    list.sort((a, b) => {
      if (sortKey === 'title') return a.title.localeCompare(b.title)
      if (sortKey === 'status') return a.status.localeCompare(b.status)
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    })
    return list
  }, [data?.items, sortKey])

  const total = data?.total ?? 0
  const allSelected = items.length > 0 && items.every((q) => selected.has(q.id))

  const toggleAll = () => {
    if (allSelected) {
      setSelected(new Set())
      return
    }
    setSelected(new Set(items.map((q) => q.id)))
  }

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const runAction = async (label: string, action: () => Promise<unknown>) => {
    try {
      await action()
      toastSuccess(label)
      setSelected(new Set())
      void refetch()
    } catch (err) {
      toastError(err)
    }
  }

  const handleConfirm = async () => {
    if (!confirm) return
    setConfirmLoading(true)
    try {
      if (confirm.type === 'delete') {
        await deleteQuiz.mutateAsync({ quizId: confirm.quiz.id })
        toastSuccess('Quiz deleted')
      } else if (confirm.type === 'archive') {
        await archiveQuiz.mutateAsync(confirm.quiz.id)
        toastSuccess('Quiz archived')
      } else if (confirm.type === 'bulk-delete') {
        const ids = [...selected]
        for (const id of ids) {
          await deleteQuiz.mutateAsync({ quizId: id })
        }
        toastSuccess(`Deleted ${ids.length} quiz${ids.length === 1 ? '' : 'zes'}`)
      } else if (confirm.type === 'bulk-archive') {
        const ready = items.filter((q) => selected.has(q.id) && q.status === 'Ready')
        for (const quiz of ready) {
          await archiveQuiz.mutateAsync(quiz.id)
        }
        toastSuccess(`Archived ${ready.length} quiz${ready.length === 1 ? '' : 'zes'}`)
      }
      setSelected(new Set())
      setConfirm(null)
      void refetch()
    } catch (err) {
      toastError(err)
    } finally {
      setConfirmLoading(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Quizzes"
        description="Search, filter, and manage quiz templates."
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
                <Plus className="h-4 w-4" />
                Create quiz
              </Link>
            </Button>
          </div>
        }
      />

      <div className="mb-6 rounded-xl border border-[var(--primary)]/30 bg-[var(--primary)]/10 px-4 py-3 sm:flex sm:items-center sm:justify-between sm:gap-4">
        <div>
          <p className="font-medium text-[var(--heading)]">New: AI quiz generation</p>
          <p className="text-sm text-[var(--muted-foreground)]">
            Upload study material or enter a topic — review questions, then save as a draft.
          </p>
        </div>
        <Button asChild className="mt-3 sm:mt-0" variant="accent">
          <Link to="/admin/quizzes/ai">
            <Sparkles className="h-4 w-4" />
            Open AI generator
          </Link>
        </Button>
      </div>

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
        <SearchBar
          value={search}
          onChange={(value) => {
            setSearch(value)
            setOffset(0)
          }}
          placeholder="Search by title…"
          aria-label="Search quizzes"
          className="flex-1"
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
        <Select value={sortKey} onValueChange={(value) => setSortKey(value as SortKey)}>
          <SelectTrigger className="sm:w-44">
            <SelectValue placeholder="Sort" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="updated">Updated</SelectItem>
            <SelectItem value="title">Title</SelectItem>
            <SelectItem value="status">Status</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {selected.size > 0 ? (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--card)]/60 px-3 py-2">
          <span className="text-sm text-[var(--muted-foreground)]">{selected.size} selected</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setConfirm({ type: 'bulk-archive' })}
          >
            Archive Ready
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => setConfirm({ type: 'bulk-delete' })}
          >
            Delete
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
            Clear
          </Button>
        </div>
      ) : null}

      {isError ? (
        <ErrorState
          message={error instanceof Error ? error.message : 'Failed to load quizzes'}
          onRetry={() => void refetch()}
        />
      ) : (
        <>
          <DataTable
            loading={isLoading}
            loadingLabel="Loading quizzes…"
            empty={!isLoading && items.length === 0}
            emptyTitle="No quizzes found"
            emptyDescription="Create one manually or generate a draft with AI."
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
                <TableHead className="w-10">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    aria-label="Select all quizzes"
                    className="h-4 w-4 accent-[var(--primary)]"
                  />
                </TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead className="w-12" />
              </>
            }
          >
            {items.map((quiz) => (
              <TableRow key={quiz.id}>
                <TableCell>
                  <input
                    type="checkbox"
                    checked={selected.has(quiz.id)}
                    onChange={() => toggleOne(quiz.id)}
                    aria-label={`Select ${quiz.title}`}
                    className="h-4 w-4 accent-[var(--primary)]"
                  />
                </TableCell>
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
                      <DropdownMenuItem onClick={() => setPreviewQuiz(quiz)}>
                        Preview
                      </DropdownMenuItem>
                      {quiz.status === 'Ready' ? (
                        <DropdownMenuItem
                          disabled={createRoom.isPending}
                          onClick={() =>
                            void createRoom
                              .mutateAsync({ quizId: quiz.id })
                              .then((room) => {
                                toastSuccess('Live room created')
                                navigate(`/admin/live-rooms/${room.id}`)
                              })
                              .catch(toastError)
                          }
                        >
                          <Radio className="h-4 w-4" />
                          Host live room
                        </DropdownMenuItem>
                      ) : null}
                      <DropdownMenuItem
                        onClick={() =>
                          void runAction('Quiz duplicated', () =>
                            duplicateQuiz.mutateAsync(quiz.id),
                          )
                        }
                      >
                        Duplicate
                      </DropdownMenuItem>
                      {quiz.status === 'Draft' ? (
                        <DropdownMenuItem
                          onClick={() =>
                            void runAction('Quiz published', () =>
                              publishQuiz.mutateAsync(quiz.id),
                            )
                          }
                        >
                          Publish / validate
                        </DropdownMenuItem>
                      ) : null}
                      {quiz.status === 'Ready' ? (
                        <DropdownMenuItem
                          onClick={() => setConfirm({ type: 'archive', quiz })}
                        >
                          Archive
                        </DropdownMenuItem>
                      ) : null}
                      {quiz.status === 'Archived' ? (
                        <DropdownMenuItem
                          onClick={() =>
                            void runAction('Quiz restored', () =>
                              restoreQuiz.mutateAsync(quiz.id),
                            )
                          }
                        >
                          Restore
                        </DropdownMenuItem>
                      ) : null}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="text-[var(--destructive)]"
                        onClick={() => setConfirm({ type: 'delete', quiz })}
                      >
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </DataTable>

          {!isLoading && items.length > 0 ? (
            <PaginationControls
              offset={offset}
              limit={PAGE_SIZE}
              total={total}
              onOffsetChange={setOffset}
              isFetching={isFetching}
            />
          ) : null}
        </>
      )}

      <ConfirmDialog
        open={confirm !== null}
        onOpenChange={(open) => {
          if (!open) setConfirm(null)
        }}
        title={
          confirm?.type === 'delete'
            ? 'Delete quiz?'
            : confirm?.type === 'archive'
              ? 'Archive quiz?'
              : confirm?.type === 'bulk-delete'
                ? 'Delete selected quizzes?'
                : 'Archive selected Ready quizzes?'
        }
        description={
          confirm?.type === 'delete'
            ? `Delete “${confirm.quiz.title}”? This cannot be undone easily.`
            : confirm?.type === 'archive'
              ? `Archive “${confirm.quiz.title}”?`
              : confirm?.type === 'bulk-delete'
                ? `Delete ${selected.size} selected quiz${selected.size === 1 ? '' : 'zes'}?`
                : `Archive Ready quizzes among the ${selected.size} selected?`
        }
        confirmLabel={
          confirm?.type === 'delete' || confirm?.type === 'bulk-delete' ? 'Delete' : 'Archive'
        }
        variant={
          confirm?.type === 'delete' || confirm?.type === 'bulk-delete'
            ? 'destructive'
            : 'default'
        }
        loading={confirmLoading}
        onConfirm={handleConfirm}
      />

      <QuizPreviewDialog quiz={previewQuiz} onOpenChange={(open) => !open && setPreviewQuiz(null)} />
    </div>
  )
}

function QuizPreviewDialog({
  quiz,
  onOpenChange,
}: {
  quiz: Quiz | null
  onOpenChange: (open: boolean) => void
}) {
  const sections = useSections(quiz?.id, Boolean(quiz))

  return (
    <Dialog open={Boolean(quiz)} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{quiz?.title ?? 'Preview'}</DialogTitle>
          <DialogDescription>
            Read-only preview of sections, questions, and options.
          </DialogDescription>
        </DialogHeader>
        {!quiz ? null : sections.isLoading ? (
          <p className="text-sm text-[var(--muted-foreground)]">Loading preview…</p>
        ) : sections.isError ? (
          <p className="text-sm text-[var(--destructive)]">Failed to load sections.</p>
        ) : !sections.data?.items.length ? (
          <p className="text-sm text-[var(--muted-foreground)]">No sections yet.</p>
        ) : (
          <div className="space-y-4">
            {[...sections.data.items]
              .sort((a, b) => a.sortOrder - b.sortOrder)
              .map((section) => (
                <PreviewSection key={section.id} quizId={quiz.id} sectionId={section.id} name={section.name} />
              ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function PreviewSection({
  quizId,
  sectionId,
  name,
}: {
  quizId: string
  sectionId: string
  name: string
}) {
  const questions = useQuestions(quizId, sectionId)

  return (
    <div className="rounded-lg border border-[var(--border)] p-3">
      <h3 className="mb-2 font-display text-base font-semibold">{name}</h3>
      {questions.isLoading ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading questions…</p>
      ) : !questions.data?.items.length ? (
        <p className="text-sm text-[var(--muted-foreground)]">No questions.</p>
      ) : (
        <ul className="space-y-3">
          {[...questions.data.items]
            .sort((a, b) => a.sortOrder - b.sortOrder)
            .map((question, index) => (
              <li key={question.id} className="text-sm">
                <p className="font-medium text-[var(--heading)]">
                  {index + 1}. {question.promptText ?? '(No prompt)'}
                </p>
                <p className="text-xs text-[var(--muted-foreground)]">
                  {question.questionType} · {question.basePoints} pts
                  {question.timeLimitSeconds ? ` · ${question.timeLimitSeconds}s` : ''}
                </p>
                <PreviewOptions
                  quizId={quizId}
                  sectionId={sectionId}
                  questionId={question.id}
                />
              </li>
            ))}
        </ul>
      )}
    </div>
  )
}

function PreviewOptions({
  quizId,
  sectionId,
  questionId,
}: {
  quizId: string
  sectionId: string
  questionId: string
}) {
  const options = useOptions(quizId, sectionId, questionId)
  if (options.isLoading || !options.data?.items.length) return null

  return (
    <ul className="mt-1 space-y-0.5 pl-4 text-xs text-[var(--muted-foreground)]">
      {[...options.data.items]
        .sort((a, b) => a.sortOrder - b.sortOrder)
        .map((option) => (
          <li key={option.id}>
            {option.isCorrect ? '✓ ' : '• '}
            {option.text}
          </li>
        ))}
    </ul>
  )
}
