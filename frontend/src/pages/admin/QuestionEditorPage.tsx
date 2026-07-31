import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, ImagePlus, Plus, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { useMediaMutations } from '@/hooks/queries/useMedia'
import { useOptionMutations, useOptions } from '@/hooks/queries/useOptions'
import { useQuestionMutations, useQuestions } from '@/hooks/queries/useQuestions'
import { useQuiz } from '@/hooks/queries/useQuiz'
import { useSections } from '@/hooks/queries/useSections'
import { cn } from '@/lib/utils'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import type { AnswerOption, Question, QuestionType } from '@/types/api'

function SortableRow({
  id,
  children,
  className,
}: {
  id: string
  children: ReactNode
  className?: string
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id,
  })

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      className={cn(
        'flex items-start gap-2 rounded-lg border border-[var(--border)] bg-[var(--color-ink)]/50 p-3',
        isDragging && 'opacity-70 ring-2 ring-[var(--primary)]',
        className,
      )}
    >
      <button
        type="button"
        className="mt-1 cursor-grab text-[var(--muted-foreground)] active:cursor-grabbing"
        aria-label="Drag to reorder"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}

export function QuestionEditorPage() {
  const { quizId = '', sectionId: routeSectionId, questionId: routeQuestionId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const quizQuery = useQuiz(quizId)
  const sectionsQuery = useSections(quizId)

  const sections = useMemo(
    () => [...(sectionsQuery.data?.items ?? [])].sort((a, b) => a.sortOrder - b.sortOrder),
    [sectionsQuery.data],
  )

  const selectedSectionId =
    routeSectionId || searchParams.get('sectionId') || sections[0]?.id || ''

  const questionsQuery = useQuestions(quizId, selectedSectionId, Boolean(selectedSectionId))
  const { createQuestion, updateQuestion } = useQuestionMutations(
    quizId,
    selectedSectionId || 'pending',
  )

  const questions = useMemo(
    () => [...(questionsQuery.data?.items ?? [])].sort((a, b) => a.sortOrder - b.sortOrder),
    [questionsQuery.data],
  )

  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(
    routeQuestionId ?? null,
  )

  useEffect(() => {
    if (routeQuestionId) {
      setSelectedQuestionId(routeQuestionId)
      return
    }
    if (selectedQuestionId && questions.some((q) => q.id === selectedQuestionId)) return
    setSelectedQuestionId(questions[0]?.id ?? null)
  }, [questions, routeQuestionId, selectedQuestionId])

  const selectedQuestion = questions.find((q) => q.id === selectedQuestionId) ?? null

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const selectSection = (sectionId: string) => {
    setSearchParams({ sectionId })
    setSelectedQuestionId(null)
    navigate(`/admin/quizzes/${quizId}/questions?sectionId=${sectionId}`, { replace: true })
  }

  const onQuestionDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = questions.findIndex((q) => q.id === active.id)
    const newIndex = questions.findIndex((q) => q.id === over.id)
    if (oldIndex < 0 || newIndex < 0) return
    const reordered = arrayMove(questions, oldIndex, newIndex)
    try {
      await Promise.all(
        reordered.map((question, index) =>
          updateQuestion.mutateAsync({
            questionId: question.id,
            input: { sortOrder: index },
          }),
        ),
      )
      toastSuccess('Question order updated')
    } catch (error) {
      toastError(error)
    }
  }

  const addQuestion = async () => {
    try {
      const created = await createQuestion.mutateAsync({
        questionType: 'Text',
        promptText: 'New question',
        basePoints: 1,
        allowMultipleCorrect: false,
        sortOrder: questions.length,
      })
      setSelectedQuestionId(created.id)
      toastSuccess('Question created')
    } catch (error) {
      toastError(error)
    }
  }

  if (quizQuery.isLoading || sectionsQuery.isLoading) {
    return <LoadingState label="Loading question editor…" />
  }

  if (quizQuery.isError || !quizQuery.data) {
    return (
      <ErrorState
        message="Failed to load quiz"
        onRetry={() => void quizQuery.refetch()}
      />
    )
  }

  if (sections.length === 0) {
    return (
      <EmptyState
        title="Add a section first"
        description="Questions belong to sections. Create one on the quiz edit page."
        action={
          <Button asChild>
            <Link to={`/admin/quizzes/${quizId}`}>Back to quiz</Link>
          </Button>
        }
      />
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Question editor"
        description={`${quizQuery.data.title} — build prompts and answer options.`}
        actions={
          <Button asChild variant="outline">
            <Link to={`/admin/quizzes/${quizId}`}>Back to quiz</Link>
          </Button>
        }
      />

      <div className="flex flex-wrap gap-2">
        {sections.map((section) => (
          <Button
            key={section.id}
            size="sm"
            variant={section.id === selectedSectionId ? 'default' : 'outline'}
            onClick={() => selectSection(section.id)}
          >
            {section.name}
          </Button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Questions</CardTitle>
            <CardDescription>Drag to reorder</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button className="w-full" size="sm" onClick={() => void addQuestion()}>
              <Plus className="h-4 w-4" />
              Add question
            </Button>

            {questionsQuery.isLoading ? <LoadingState className="min-h-[120px]" /> : null}
            {questionsQuery.isError ? (
              <ErrorState
                message="Failed to load questions"
                onRetry={() => void questionsQuery.refetch()}
              />
            ) : null}

            {!questionsQuery.isLoading && questions.length === 0 ? (
              <p className="text-sm text-[var(--muted-foreground)]">No questions in this section.</p>
            ) : null}

            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={(e) => void onQuestionDragEnd(e)}
            >
              <SortableContext
                items={questions.map((q) => q.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-2">
                  {questions.map((question) => (
                    <SortableRow key={question.id} id={question.id} className="p-2">
                      <button
                        type="button"
                        className={cn(
                          'w-full rounded-md px-2 py-1.5 text-left text-sm transition-colors',
                          question.id === selectedQuestionId
                            ? 'bg-[var(--primary)]/15 text-[var(--primary)]'
                            : 'hover:bg-[var(--secondary)]',
                        )}
                        onClick={() => {
                          setSelectedQuestionId(question.id)
                          navigate(
                            `/admin/quizzes/${quizId}/sections/${selectedSectionId}/questions/${question.id}`,
                            { replace: true },
                          )
                        }}
                      >
                        <span className="line-clamp-2">
                          {question.promptText || 'Untitled question'}
                        </span>
                        <span className="mt-1 block text-xs text-[var(--muted-foreground)]">
                          {question.allowMultipleCorrect ? 'Multi-select' : 'MCQ'} ·{' '}
                          {question.basePoints} pts
                        </span>
                      </button>
                    </SortableRow>
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          </CardContent>
        </Card>

        {selectedQuestion && selectedSectionId ? (
          <QuestionDetailPanel
            quizId={quizId}
            sectionId={selectedSectionId}
            question={selectedQuestion}
            onDeleted={() => setSelectedQuestionId(null)}
          />
        ) : (
          <EmptyState
            title="Select a question"
            description="Choose a question from the list or create a new one."
          />
        )}
      </div>
    </div>
  )
}

function QuestionDetailPanel({
  quizId,
  sectionId,
  question,
  onDeleted,
}: {
  quizId: string
  sectionId: string
  question: Question
  onDeleted: () => void
}) {
  const { updateQuestion, deleteQuestion } = useQuestionMutations(quizId, sectionId)
  const optionsQuery = useOptions(quizId, sectionId, question.id)
  const { createOption, updateOption, deleteOption } = useOptionMutations(
    quizId,
    sectionId,
    question.id,
  )
  const { uploadMedia, attachMedia } = useMediaMutations()

  const [promptText, setPromptText] = useState(question.promptText ?? '')
  const [questionType, setQuestionType] = useState<QuestionType>(question.questionType)
  const [basePoints, setBasePoints] = useState(question.basePoints)
  const [allowMultipleCorrect, setAllowMultipleCorrect] = useState(question.allowMultipleCorrect)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    setPromptText(question.promptText ?? '')
    setQuestionType(question.questionType)
    setBasePoints(question.basePoints)
    setAllowMultipleCorrect(question.allowMultipleCorrect)
  }, [question])

  const options = useMemo(
    () => [...(optionsQuery.data?.items ?? [])].sort((a, b) => a.sortOrder - b.sortOrder),
    [optionsQuery.data],
  )

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const saveQuestion = async () => {
    try {
      await updateQuestion.mutateAsync({
        questionId: question.id,
        input: {
          promptText: promptText.trim(),
          questionType,
          basePoints,
          allowMultipleCorrect,
        },
      })
      toastSuccess('Question saved')
    } catch (error) {
      toastError(error)
    }
  }

  const onOptionDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = options.findIndex((o) => o.id === active.id)
    const newIndex = options.findIndex((o) => o.id === over.id)
    if (oldIndex < 0 || newIndex < 0) return
    const reordered = arrayMove(options, oldIndex, newIndex)
    try {
      await Promise.all(
        reordered.map((option, index) =>
          updateOption.mutateAsync({
            optionId: option.id,
            input: { sortOrder: index },
          }),
        ),
      )
      toastSuccess('Option order updated')
    } catch (error) {
      toastError(error)
    }
  }

  const setCorrect = async (option: AnswerOption, isCorrect: boolean) => {
    try {
      if (!allowMultipleCorrect && isCorrect) {
        await Promise.all(
          options.map((o) =>
            updateOption.mutateAsync({
              optionId: o.id,
              input: { isCorrect: o.id === option.id },
            }),
          ),
        )
      } else {
        await updateOption.mutateAsync({
          optionId: option.id,
          input: { isCorrect },
        })
      }
      toastSuccess('Correct answer updated')
    } catch (error) {
      toastError(error)
    }
  }

  const onUploadImage = async (file: File | null) => {
    if (!file) return
    setUploading(true)
    try {
      const media = await uploadMedia.mutateAsync({
        file,
        category: 'question_image',
        quizId,
      })
      await attachMedia.mutateAsync({
        mediaId: media.id,
        quizId,
        sectionId,
        questionId: question.id,
      })
      setQuestionType('Image')
      await updateQuestion.mutateAsync({
        questionId: question.id,
        input: { questionType: 'Image' },
      })
      toastSuccess('Image attached')
    } catch (error) {
      toastError(error)
    } finally {
      setUploading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Edit question</CardTitle>
        <CardDescription>Prompt, scoring, and answer options.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="prompt">Prompt</Label>
          <Textarea
            id="prompt"
            rows={3}
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-2">
            <Label>Type</Label>
            <Select
              value={questionType}
              onValueChange={(v) => setQuestionType(v as QuestionType)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Text">Text</SelectItem>
                <SelectItem value="Image">Image</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="points">Base points</Label>
            <Input
              id="points"
              type="number"
              min={1}
              value={basePoints}
              onChange={(e) => setBasePoints(Number(e.target.value) || 1)}
            />
          </div>
          <label className="flex items-end justify-between gap-3 rounded-md border border-[var(--border)] px-3 py-2">
            <span className="text-sm">
              {allowMultipleCorrect ? 'Multiple select' : 'Single choice (MCQ)'}
            </span>
            <Switch
              checked={allowMultipleCorrect}
              onCheckedChange={setAllowMultipleCorrect}
            />
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Label
            htmlFor="image-upload"
            className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-md border border-[var(--border)] px-3 text-sm hover:bg-[var(--secondary)]"
          >
            <ImagePlus className="h-4 w-4" />
            {uploading ? 'Uploading…' : 'Upload question image'}
          </Label>
          <Input
            id="image-upload"
            type="file"
            accept="image/*"
            className="hidden"
            disabled={uploading}
            onChange={(e) => void onUploadImage(e.target.files?.[0] ?? null)}
          />
          {question.mediaFileId ? (
            <span className="text-xs text-[var(--muted-foreground)]">
              Media: {question.mediaFileId}
            </span>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button onClick={() => void saveQuestion()}>Save question</Button>
          <Button
            variant="destructive"
            onClick={() => {
              if (!window.confirm('Delete this question?')) return
              void deleteQuestion
                .mutateAsync(question.id)
                .then(() => {
                  toastSuccess('Question deleted')
                  onDeleted()
                })
                .catch(toastError)
            }}
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>

        <div className="space-y-3 border-t border-[var(--border)] pt-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-display text-base font-semibold">Answer options</h3>
              <p className="text-xs text-[var(--muted-foreground)]">
                Mark correct with {allowMultipleCorrect ? 'checkboxes' : 'radio'}. Drag to reorder.
              </p>
            </div>
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                void createOption
                  .mutateAsync({
                    text: `Option ${options.length + 1}`,
                    isCorrect: false,
                    sortOrder: options.length,
                  })
                  .then(() => toastSuccess('Option added'))
                  .catch(toastError)
              }
            >
              <Plus className="h-4 w-4" />
              Add option
            </Button>
          </div>

          {optionsQuery.isLoading ? <LoadingState className="min-h-[100px]" /> : null}
          {optionsQuery.isError ? (
            <ErrorState message="Failed to load options" onRetry={() => void optionsQuery.refetch()} />
          ) : null}

          {!optionsQuery.isLoading && options.length === 0 ? (
            <EmptyState title="No options" description="Add at least two answer options." />
          ) : null}

          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={(e) => void onOptionDragEnd(e)}
          >
            <SortableContext items={options.map((o) => o.id)} strategy={verticalListSortingStrategy}>
              <div className="space-y-2">
                {options.map((option) => (
                  <SortableRow key={option.id} id={option.id}>
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                      <input
                        type={allowMultipleCorrect ? 'checkbox' : 'radio'}
                        name={`correct-${question.id}`}
                        checked={option.isCorrect}
                        onChange={(e) => void setCorrect(option, e.target.checked)}
                        className="mt-1"
                        aria-label="Mark correct"
                      />
                      <Input
                        defaultValue={option.text}
                        onBlur={(e) => {
                          const text = e.target.value.trim()
                          if (!text || text === option.text) return
                          void updateOption
                            .mutateAsync({ optionId: option.id, input: { text } })
                            .then(() => toastSuccess('Option updated'))
                            .catch(toastError)
                        }}
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-[var(--destructive)]"
                        onClick={() =>
                          void deleteOption
                            .mutateAsync(option.id)
                            .then(() => toastSuccess('Option deleted'))
                            .catch(toastError)
                        }
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </SortableRow>
                ))}
              </div>
            </SortableContext>
          </DndContext>
        </div>
      </CardContent>
    </Card>
  )
}
