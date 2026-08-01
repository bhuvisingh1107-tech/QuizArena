import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'

import { questionKindLabel, inferQuestionKind } from '@/components/quiz-builder/McqOptionsEditor'
import { QuestionEditorDialog } from '@/components/quiz-builder/QuestionEditorDialog'
import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useOptions } from '@/hooks/queries/useOptions'
import { useQuestionMutations, useQuestions } from '@/hooks/queries/useQuestions'
import { apiPost } from '@/lib/api-client'
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

interface QuestionsStepProps {
  quizId: string
  sections: Section[]
  section: Section | null
  selectedSectionId: string | null
  onSelectSection: (sectionId: string) => void
  onAddSection: () => void
  onRenameSection: (section: Section) => void
  sectionsLoading: boolean
  sectionsError: boolean
  onRetrySections: () => void
  onContinue: () => void
  addingSection?: boolean
}

export function QuestionsStep({
  quizId,
  sections,
  section,
  selectedSectionId,
  onSelectSection,
  onAddSection,
  onRenameSection,
  sectionsLoading,
  sectionsError,
  onRetrySections,
  onContinue,
  addingSection = false,
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

  const openCreate = () => {
    setEditing(null)
    setEditorOpen(true)
  }

  const openEdit = (question: Question) => {
    setEditing(question)
    setEditorOpen(true)
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
                <button
                  key={item.id}
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
            </div>
          ) : null}
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Add Question
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
              <Button onClick={openCreate}>
                <Plus className="h-4 w-4" />
                Add Question
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
          <Button onClick={onContinue} disabled={questions.length === 0}>
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
          onSaved={() => {
            void questionsQuery.refetch()
          }}
        />
      </CardContent>
    </Card>
  )
}
