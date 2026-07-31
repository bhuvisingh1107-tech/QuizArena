import { zodResolver } from '@hookform/resolvers/zod'
import {
  ArrowDown,
  ArrowUp,
  Loader2,
  Pencil,
  Plus,
  Radio,
  Trash2,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { z } from 'zod'

import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { useLiveRoomMutations } from '@/hooks/queries/useLiveRoomMutations'
import { useQuiz } from '@/hooks/queries/useQuiz'
import { useQuizMutations } from '@/hooks/queries/useQuizMutations'
import { useSectionMutations, useSections } from '@/hooks/queries/useSections'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import type { Section } from '@/types/api'

const editFormSchema = z.object({
  title: z.string().min(1, 'Title is required').max(255),
  description: z.string().max(10_000).optional(),
  questionAdvanceMode: z.enum(['manual', 'automatic']),
  answerRevealBehavior: z.enum(['after_each', 'session_end']),
  timeBonusEnabled: z.boolean(),
  timeBonusMaxPoints: z.coerce.number().int().min(0),
  streakBonusEnabled: z.boolean(),
  questionOrderShuffle: z.boolean(),
  answerOptionShuffle: z.boolean(),
})

type EditFormValues = z.infer<typeof editFormSchema>

export function EditQuizPage() {
  const { quizId = '' } = useParams()
  const navigate = useNavigate()
  const quizQuery = useQuiz(quizId)
  const sectionsQuery = useSections(quizId)
  const { updateQuiz, deleteQuiz, publishQuiz, archiveQuiz, duplicateQuiz, restoreQuiz } =
    useQuizMutations()
  const { createSection, updateSection, deleteSection } = useSectionMutations(quizId)
  const { createRoom } = useLiveRoomMutations()

  const [sectionName, setSectionName] = useState('')
  const [renameTarget, setRenameTarget] = useState<Section | null>(null)
  const [renameValue, setRenameValue] = useState('')

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<EditFormValues>({
    resolver: zodResolver(editFormSchema),
  })

  useEffect(() => {
    const quiz = quizQuery.data
    if (!quiz) return
    reset({
      title: quiz.title,
      description: quiz.description ?? '',
      questionAdvanceMode: quiz.config?.questionAdvanceMode ?? 'manual',
      answerRevealBehavior: quiz.config?.answerRevealBehavior ?? 'after_each',
      timeBonusEnabled: quiz.config?.timeBonusEnabled ?? false,
      timeBonusMaxPoints: quiz.config?.timeBonusMaxPoints ?? 0,
      streakBonusEnabled: quiz.config?.streakBonusEnabled ?? false,
      questionOrderShuffle: quiz.config?.questionOrderShuffle ?? false,
      answerOptionShuffle: quiz.config?.answerOptionShuffle ?? false,
    })
  }, [quizQuery.data, reset])

  const sections = [...(sectionsQuery.data?.items ?? [])].sort(
    (a, b) => a.sortOrder - b.sortOrder,
  )

  const onSave = handleSubmit(async (values) => {
    try {
      await updateQuiz.mutateAsync({
        quizId,
        input: {
          title: values.title.trim(),
          description: values.description?.trim() || null,
          config: {
            questionAdvanceMode: values.questionAdvanceMode,
            answerRevealBehavior: values.answerRevealBehavior,
            timeBonusEnabled: values.timeBonusEnabled,
            timeBonusMaxPoints: values.timeBonusMaxPoints,
            streakBonusEnabled: values.streakBonusEnabled,
            questionOrderShuffle: values.questionOrderShuffle,
            answerOptionShuffle: values.answerOptionShuffle,
          },
        },
      })
      toastSuccess('Quiz saved')
    } catch (error) {
      toastError(error)
    }
  })

  const moveSection = async (section: Section, direction: -1 | 1) => {
    const index = sections.findIndex((s) => s.id === section.id)
    const swapWith = sections[index + direction]
    if (!swapWith) return
    try {
      await Promise.all([
        updateSection.mutateAsync({
          sectionId: section.id,
          input: { sortOrder: swapWith.sortOrder },
        }),
        updateSection.mutateAsync({
          sectionId: swapWith.id,
          input: { sortOrder: section.sortOrder },
        }),
      ])
      toastSuccess('Section order updated')
    } catch (error) {
      toastError(error)
    }
  }

  const hostLiveRoom = async () => {
    try {
      const room = await createRoom.mutateAsync({ quizId })
      toastSuccess('Live room created')
      navigate(`/admin/live-rooms/${room.id}`)
    } catch (error) {
      toastError(error)
    }
  }

  if (quizQuery.isLoading) return <LoadingState label="Loading quiz…" />
  if (quizQuery.isError || !quizQuery.data) {
    return (
      <ErrorState
        message={quizQuery.error instanceof Error ? quizQuery.error.message : 'Quiz not found'}
        onRetry={() => void quizQuery.refetch()}
      />
    )
  }

  const quiz = quizQuery.data

  return (
    <div className="space-y-8">
      <PageHeader
        title={quiz.title}
        description="Edit metadata, scoring config, and sections."
        actions={
          <div className="flex flex-wrap gap-2">
            <StatusBadge status={quiz.status} />
            {quiz.status === 'Ready' ? (
              <Button onClick={() => void hostLiveRoom()}>
                <Radio className="h-4 w-4" />
                Host live room
              </Button>
            ) : null}
            <Button
              variant="secondary"
              onClick={() =>
                void publishQuiz
                  .mutateAsync(quizId)
                  .then(() => toastSuccess('Published / validated'))
                  .catch(toastError)
              }
            >
              Publish
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                void archiveQuiz
                  .mutateAsync(quizId)
                  .then(() => toastSuccess('Archived'))
                  .catch(toastError)
              }
            >
              Archive
            </Button>
            {quiz.status === 'Archived' ? (
              <Button
                variant="outline"
                onClick={() =>
                  void restoreQuiz
                    .mutateAsync(quizId)
                    .then(() => toastSuccess('Restored'))
                    .catch(toastError)
                }
              >
                Restore
              </Button>
            ) : null}
            <Button
              variant="outline"
              onClick={() =>
                void duplicateQuiz
                  .mutateAsync(quizId)
                  .then((copy) => {
                    toastSuccess('Duplicated')
                    navigate(`/admin/quizzes/${copy.id}`)
                  })
                  .catch(toastError)
              }
            >
              Duplicate
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (!window.confirm('Delete this quiz?')) return
                void deleteQuiz
                  .mutateAsync({ quizId })
                  .then(() => {
                    toastSuccess('Deleted')
                    navigate('/admin/quizzes')
                  })
                  .catch(toastError)
              }}
            >
              Delete
            </Button>
          </div>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Quiz details</CardTitle>
          <CardDescription>Title, description, and scoring behavior.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSave} className="space-y-5" noValidate>
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" {...register('title')} />
              {errors.title ? (
                <p className="text-xs text-[var(--destructive)]">{errors.title.message}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={3} {...register('description')} />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Question advance</Label>
                <Select
                  value={watch('questionAdvanceMode')}
                  onValueChange={(v) =>
                    setValue('questionAdvanceMode', v as 'manual' | 'automatic', {
                      shouldDirty: true,
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manual">Manual</SelectItem>
                    <SelectItem value="automatic">Automatic</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Answer reveal</Label>
                <Select
                  value={watch('answerRevealBehavior')}
                  onValueChange={(v) =>
                    setValue('answerRevealBehavior', v as 'after_each' | 'session_end', {
                      shouldDirty: true,
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="after_each">After each</SelectItem>
                    <SelectItem value="session_end">Session end</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex items-center justify-between rounded-md border border-[var(--border)] px-3 py-2">
                <span className="text-sm">Time bonus</span>
                <Switch
                  checked={watch('timeBonusEnabled')}
                  onCheckedChange={(checked) =>
                    setValue('timeBonusEnabled', checked, { shouldDirty: true })
                  }
                />
              </label>
              <div className="space-y-2">
                <Label htmlFor="timeBonusMaxPoints">Time bonus max points</Label>
                <Input
                  id="timeBonusMaxPoints"
                  type="number"
                  min={0}
                  {...register('timeBonusMaxPoints')}
                />
              </div>
              <label className="flex items-center justify-between rounded-md border border-[var(--border)] px-3 py-2">
                <span className="text-sm">Streak bonus</span>
                <Switch
                  checked={watch('streakBonusEnabled')}
                  onCheckedChange={(checked) =>
                    setValue('streakBonusEnabled', checked, { shouldDirty: true })
                  }
                />
              </label>
              <label className="flex items-center justify-between rounded-md border border-[var(--border)] px-3 py-2">
                <span className="text-sm">Shuffle questions</span>
                <Switch
                  checked={watch('questionOrderShuffle')}
                  onCheckedChange={(checked) =>
                    setValue('questionOrderShuffle', checked, { shouldDirty: true })
                  }
                />
              </label>
              <label className="flex items-center justify-between rounded-md border border-[var(--border)] px-3 py-2 sm:col-span-2">
                <span className="text-sm">Shuffle answer options</span>
                <Switch
                  checked={watch('answerOptionShuffle')}
                  onCheckedChange={(checked) =>
                    setValue('answerOptionShuffle', checked, { shouldDirty: true })
                  }
                />
              </label>
            </div>

            <div className="flex justify-end">
              <Button type="submit" disabled={isSubmitting || !isDirty}>
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Save changes
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sections</CardTitle>
          <CardDescription>
            Organize questions into sections. Open the question editor for each section.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            className="flex flex-col gap-2 sm:flex-row"
            onSubmit={(e) => {
              e.preventDefault()
              const name = sectionName.trim()
              if (!name) return
              void createSection
                .mutateAsync({ name, sortOrder: sections.length })
                .then(() => {
                  setSectionName('')
                  toastSuccess('Section added')
                })
                .catch(toastError)
            }}
          >
            <Input
              placeholder="New section name"
              value={sectionName}
              onChange={(e) => setSectionName(e.target.value)}
            />
            <Button type="submit">
              <Plus className="h-4 w-4" />
              Add section
            </Button>
          </form>

          {sectionsQuery.isLoading ? <LoadingState label="Loading sections…" /> : null}
          {sectionsQuery.isError ? (
            <ErrorState
              message="Failed to load sections"
              onRetry={() => void sectionsQuery.refetch()}
            />
          ) : null}

          {!sectionsQuery.isLoading && sections.length === 0 ? (
            <EmptyState
              title="No sections"
              description="Add a section before creating questions."
            />
          ) : null}

          <ul className="space-y-2">
            {sections.map((section, index) => (
              <li
                key={section.id}
                className="flex flex-col gap-3 rounded-lg border border-[var(--border)] bg-[var(--color-ink)]/40 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="font-medium text-[#f0f4fa]">{section.name}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Order {section.sortOrder}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={index === 0}
                    onClick={() => void moveSection(section, -1)}
                    aria-label="Move up"
                  >
                    <ArrowUp className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={index === sections.length - 1}
                    onClick={() => void moveSection(section, 1)}
                    aria-label="Move down"
                  >
                    <ArrowDown className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      setRenameTarget(section)
                      setRenameValue(section.name)
                    }}
                    aria-label="Rename"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button asChild variant="secondary" size="sm">
                    <Link to={`/admin/quizzes/${quizId}/questions?sectionId=${section.id}`}>
                      Questions
                    </Link>
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-[var(--destructive)]"
                    onClick={() => {
                      if (!window.confirm(`Delete section “${section.name}”?`)) return
                      void deleteSection
                        .mutateAsync(section.id)
                        .then(() => toastSuccess('Section deleted'))
                        .catch(toastError)
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Dialog open={Boolean(renameTarget)} onOpenChange={(open) => !open && setRenameTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename section</DialogTitle>
            <DialogDescription>Update the section display name.</DialogDescription>
          </DialogHeader>
          <Input value={renameValue} onChange={(e) => setRenameValue(e.target.value)} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameTarget(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (!renameTarget) return
                void updateSection
                  .mutateAsync({
                    sectionId: renameTarget.id,
                    input: { name: renameValue.trim() },
                  })
                  .then(() => {
                    toastSuccess('Section renamed')
                    setRenameTarget(null)
                  })
                  .catch(toastError)
              }}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
