import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { questionKindLabel, inferQuestionKind } from '@/components/quiz-builder/McqOptionsEditor'
import { QuestionEditorDialog } from '@/components/quiz-builder/QuestionEditorDialog'
import { ConfirmDialog } from '@/components/shared/ConfirmDialog'
import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useOptions } from '@/hooks/queries/useOptions'
import { useQuestionMutations, useQuestions } from '@/hooks/queries/useQuestions'
import { apiPost } from '@/lib/api-client'
import { firstMcqOptionError, isMcqOptionsValid } from '@/lib/mcq-validation'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import { cn } from '@/lib/utils'
import type { Question, Section } from '@/types/api'

function QuestionTypeBadge({
  quizId,
  sectionId,
  question,
}: {
  quizId: string
  sectionId: string
  question: Question
}) {
  const optionsQuery = useOptions(quizId, sectionId, question.id)
  const kind = inferQuestionKind(optionsQuery.data?.items ?? [])
  return (
    <Badge variant="secondary">{questionKindLabel(kind, question.questionType)}</Badge>
  )
}

function QuestionMcqErrors({
  quizId,
  sectionId,
  questionId,
  onValidity,
}: {
  quizId: string
  sectionId: string
  questionId: string
  onValidity?: (questionId: string, valid: boolean) => void
}) {
  const optionsQuery = useOptions(quizId, sectionId, questionId)
  const options = useMemo(
    () =>
      [...(optionsQuery.data?.items ?? [])]
        .sort((a, b) => a.sortOrder - b.sortOrder)
        .map((o) => ({ text: o.text, isCorrect: o.isCorrect })),
    [optionsQuery.data],
  )
  const error = optionsQuery.isLoading ? null : firstMcqOptionError(options)
  const valid = optionsQuery.isLoading ? true : isMcqOptionsValid(options)

  useEffect(() => {
    onValidity?.(questionId, valid)
  }, [onValidity, questionId, valid])

  if (!error) return null
  return <p className="mt-1 text-xs text-[var(--destructive)]">{error}</p>
}

interface QuestionsStepProps {
  quizId: string
  sections: Section[]
  section: Section | null
  selectedSectionId: string | null
  onSelectSection: (sectionId: string) => void
  onAddSection: () => void
  onRenameSection: (section: Section) => void
  onDeleteSection: (section: Section) => Promise<void>
  sectionsLoading: boolean
  sectionsError: boolean
  onRetrySections: () => void
  onContinue: () => void
  addingSection?: boolean
  deletingSection?: boolean
}

export function QuestionsStep({
  quizId,
  sections,
  section,
  selectedSectionId,
  onSelectSection,
  onAddSection,
  onRenameSection,
  onDeleteSection,
  sectionsLoading,
  sectionsError,
  onRetrySections,
  onContinue,
  addingSection = false,
  deletingSection = false,
}: QuestionsStepProps) {
  const sectionId = section?.id
  const questionsQuery = useQuestions(quizId, sectionId, Boolean(sectionId))
  const { deleteQuestion } = useQuestionMutations(quizId, sectionId ?? 'pending')

  const questions = useMemo(
    () => [...(questionsQuery.data?.items ?? [])].sort((a, b) => a.sortOrder - b.sortOrder),
    [questionsQuery.data],
  )

  const [editorOpen, setEditorOpen] = useState(false)
  const [editing, setEditing] = useState<Question | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<Section | null>(null)
  const [validityByQuestion, setValidityByQuestion] = useState<Record<string, boolean>>({})

  const reportValidity = (questionId: string, valid: boolean) => {
    setValidityByQuestion((prev) => {
      if (prev[questionId] === valid) return prev
      return { ...prev, [questionId]: valid }
    })
  }

  const allQuestionsValid =
    questions.length > 0 &&
    questions.every((q) => validityByQuestion[q.id] !== false) &&
    !questionsQuery.isLoading

  const openCreate = async () => {
    if (!sectionId) return
    setCreating(true)
    try {
      const saved = await apiPost<Question>(
        `/quizzes/${quizId}/sections/${sectionId}/questions`,
        {
          questionType: 'Text',
          promptText: 'New question',
          basePoints: 1,
          timeLimitSeconds: 30,
          allowMultipleCorrect: false,
          sortOrder: questions.length,
        },
      )
      await questionsQuery.refetch()
      setEditing(saved)
      setEditorOpen(true)
      toastSuccess('Question created — you can attach media now')
    } catch (error) {
      toastError(error)
    } finally {
      setCreating(false)
    }
  }

  const openEdit = (question: Question) => {
    setEditing(question)
    setEditorOpen(true)
  }

  const requestDeleteSection = (target: Section) => {
    if (sections.length <= 1) {
      toastError(new Error('A quiz must contain at least one section'))
      return
    }
    setDeleteConfirm(target)
  }

  if (sectionsLoading) return <LoadingState label="Loading sections…" />
  if (sectionsError) {
    return <ErrorState message="Failed to load sections" onRetry={onRetrySections} />
  }
  if (!section) {
    return (
      <EmptyState
        title="No section found"
        description="Create a section to start adding questions."
        action={
          <Button
            type="button"
            onClick={async () => {
              try {
                await apiPost(`/quizzes/${quizId}/sections`, {
                  name: 'Section 1',
                  sortOrder: 0,
                })
                toastSuccess('Section created')
                onRetrySections()
              } catch (error) {
                toastError(error)
              }
            }}
          >
            Create Section 1
          </Button>
        }
      />
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <CardTitle>Questions</CardTitle>
            <CardDescription>
              Editing {section.name}. Add multiple choice or true/false questions.
            </CardDescription>
          </div>
          {sections.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              {sections.map((item) => (
                <div key={item.id} className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => onSelectSection(item.id)}
                    className={cn(
                      'rounded-full border px-3 py-1 text-sm font-medium transition-colors',
                      item.id === selectedSectionId
                        ? 'border-[var(--primary)] bg-[var(--primary)]/15 text-[var(--primary)]'
                        : 'border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--secondary)]',
                    )}
                  >
                    {item.name}
                  </button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-[var(--destructive)]"
                    aria-label={`Delete section ${item.name}`}
                    disabled={deletingSection}
                    onClick={() => requestDeleteSection(item)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={addingSection}
                onClick={onAddSection}
              >
                <Plus className="h-4 w-4" />
                Add Section
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Rename ${section.name}`}
                onClick={() => onRenameSection(section)}
              >
                <Pencil className="h-4 w-4" />
                Rename
              </Button>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                disabled={deletingSection}
                onClick={() => requestDeleteSection(section)}
              >
                <Trash2 className="h-4 w-4" />
                Delete Section
              </Button>
            </div>
          ) : null}
        </div>
        <Button onClick={() => void openCreate()} disabled={creating}>
          <Plus className="h-4 w-4" />
          {creating ? 'Creating…' : 'Add Question'}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {questionsQuery.isLoading ? <LoadingState label="Loading questions…" /> : null}
        {questionsQuery.isError ? (
          <ErrorState
            message="Failed to load questions"
            onRetry={() => void questionsQuery.refetch()}
          />
        ) : null}

        {!questionsQuery.isLoading && questions.length === 0 ? (
          <EmptyState
            title="No questions yet"
            description="Add your first question to continue toward publish."
            action={
              <Button onClick={() => void openCreate()} disabled={creating}>
                <Plus className="h-4 w-4" />
                {creating ? 'Creating…' : 'Add Question'}
              </Button>
            }
          />
        ) : null}

        <ul className="space-y-2">
          {questions.map((question, index) => (
            <li
              key={question.id}
              className="flex flex-col gap-3 rounded-lg border border-[var(--border)] bg-[var(--color-ink)]/40 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold text-[var(--muted-foreground)]">
                    Q{index + 1}
                  </span>
                  <QuestionTypeBadge
                    quizId={quizId}
                    sectionId={section.id}
                    question={question}
                  />
                  <span className="text-xs text-[var(--muted-foreground)]">
                    {question.basePoints} pt{question.basePoints === 1 ? '' : 's'}
                  </span>
                  {question.mediaFileId ? (
                    <Badge variant="outline" className="text-[10px]">
                      Media
                    </Badge>
                  ) : null}
                </div>
                <p className="truncate font-medium text-[#f0f4fa]">
                  {question.promptText || 'Untitled question'}
                </p>
                <QuestionMcqErrors
                  quizId={quizId}
                  sectionId={section.id}
                  questionId={question.id}
                  onValidity={reportValidity}
                />
              </div>
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Edit question"
                  onClick={() => openEdit(question)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-[var(--destructive)]"
                  aria-label="Delete question"
                  onClick={() => {
                    if (!window.confirm('Delete this question?')) return
                    void deleteQuestion
                      .mutateAsync(question.id)
                      .then(() => toastSuccess('Question deleted'))
                      .catch(toastError)
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </li>
          ))}
        </ul>

        <div className="flex justify-end pt-2">
          <Button onClick={onContinue} disabled={!allQuestionsValid}>
            Continue to Review
          </Button>
        </div>

        <QuestionEditorDialog
          open={editorOpen}
          onOpenChange={setEditorOpen}
          quizId={quizId}
          sectionId={section.id}
          question={editing}
          nextSortOrder={questions.length}
          onSaved={(saved) => {
            setEditing(saved)
            void questionsQuery.refetch()
          }}
        />

        <ConfirmDialog
          open={Boolean(deleteConfirm)}
          onOpenChange={(open) => {
            if (!open) setDeleteConfirm(null)
          }}
          title="Delete section?"
          description={
            deleteConfirm
              ? `Delete “${deleteConfirm.name}” and all of its questions? This cannot be undone.`
              : undefined
          }
          confirmLabel="Delete Section"
          variant="destructive"
          loading={deletingSection}
          onConfirm={async () => {
            if (!deleteConfirm) return
            try {
              await onDeleteSection(deleteConfirm)
              setDeleteConfirm(null)
            } catch {
              // Parent shows toast; keep dialog open on failure.
            }
          }}
        />
      </CardContent>
    </Card>
  )
}
