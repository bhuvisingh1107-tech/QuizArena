import { Loader2, Radio } from 'lucide-react'
import { useMemo, useState } from 'react'

import { EmptyState } from '@/components/shared/EmptyState'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingState } from '@/components/shared/LoadingState'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useLiveRoomMutations } from '@/hooks/queries/useLiveRoomMutations'
import { useOptions } from '@/hooks/queries/useOptions'
import { useQuestions } from '@/hooks/queries/useQuestions'
import { useQuizMutations } from '@/hooks/queries/useQuizMutations'
import { ApiError } from '@/lib/api-client'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import type { Quiz, Section } from '@/types/api'
import { useNavigate } from 'react-router-dom'

interface ChecklistItem {
  field?: string
  message: string
}

function parseChecklist(details: unknown[]): ChecklistItem[] {
  return details.map((item) => {
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>
      return {
        field: typeof record.field === 'string' ? record.field : undefined,
        message:
          typeof record.message === 'string'
            ? record.message
            : JSON.stringify(item),
      }
    }
    return { message: String(item) }
  })
}

function QuestionPreview({
  quizId,
  sectionId,
  questionId,
  index,
  promptText,
  basePoints,
  explanation,
}: {
  quizId: string
  sectionId: string
  questionId: string
  index: number
  promptText?: string | null
  basePoints: number
  explanation?: string | null
}) {
  const optionsQuery = useOptions(quizId, sectionId, questionId)
  const options = useMemo(
    () => [...(optionsQuery.data?.items ?? [])].sort((a, b) => a.sortOrder - b.sortOrder),
    [optionsQuery.data],
  )

  return (
    <li className="rounded-lg border border-[var(--border)] bg-[var(--color-ink)]/40 px-4 py-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-[var(--muted-foreground)]">Q{index + 1}</span>
        <Badge variant="outline">{basePoints} pts</Badge>
      </div>
      <p className="font-medium text-[#f0f4fa]">{promptText || 'Untitled question'}</p>
      {explanation ? (
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">Explanation: {explanation}</p>
      ) : null}
      <ul className="mt-3 space-y-1">
        {options.map((opt) => (
          <li
            key={opt.id}
            className={
              opt.isCorrect
                ? 'text-sm text-[var(--color-success)]'
                : 'text-sm text-[var(--muted-foreground)]'
            }
          >
            {opt.isCorrect ? '✓ ' : '· '}
            {opt.text}
            {opt.isCorrect ? ' (correct)' : ''}
          </li>
        ))}
        {optionsQuery.isLoading ? (
          <li className="text-xs text-[var(--muted-foreground)]">Loading options…</li>
        ) : null}
      </ul>
    </li>
  )
}

function SectionQuestionsReview({ quizId, section }: { quizId: string; section: Section }) {
  const questionsQuery = useQuestions(quizId, section.id)
  const questions = useMemo(
    () => [...(questionsQuery.data?.items ?? [])].sort((a, b) => a.sortOrder - b.sortOrder),
    [questionsQuery.data],
  )

  return (
    <div className="space-y-3">
      <h4 className="text-base font-semibold text-[#f0f4fa]">
        {section.name}
        <span className="ml-2 text-sm font-normal text-[var(--muted-foreground)]">
          ({questions.length} question{questions.length === 1 ? '' : 's'})
        </span>
      </h4>
      {questionsQuery.isLoading ? <LoadingState label="Loading questions…" /> : null}
      {questionsQuery.isError ? (
        <ErrorState
          message={`Failed to load questions for ${section.name}`}
          onRetry={() => void questionsQuery.refetch()}
        />
      ) : null}
      {!questionsQuery.isLoading && questions.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">No questions in this section.</p>
      ) : null}
      {questions.length > 0 ? (
        <ul className="space-y-3">
          {questions.map((q, index) => (
            <QuestionPreview
              key={q.id}
              quizId={quizId}
              sectionId={section.id}
              questionId={q.id}
              index={index}
              promptText={q.promptText}
              basePoints={q.basePoints}
              explanation={q.explanation}
            />
          ))}
        </ul>
      ) : null}
    </div>
  )
}

interface ReviewStepProps {
  quiz: Quiz
  sections: Section[]
  onBack: (step: 1 | 2) => void
  onPublished?: () => void
}

export function ReviewStep({ quiz, sections, onBack, onPublished }: ReviewStepProps) {
  const navigate = useNavigate()
  const { publishQuiz } = useQuizMutations()
  const { createRoom } = useLiveRoomMutations()
  const [checklist, setChecklist] = useState<ChecklistItem[]>([])
  const [publishing, setPublishing] = useState(false)

  const config = quiz.config
  const hasSections = sections.length > 0

  const onPublish = async () => {
    setPublishing(true)
    setChecklist([])
    try {
      await publishQuiz.mutateAsync(quiz.id)
      toastSuccess('Quiz published', 'Status is now Ready')
      onPublished?.()
    } catch (error) {
      if (error instanceof ApiError && error.status === 422 && error.details.length) {
        setChecklist(parseChecklist(error.details))
        toastError(error)
      } else {
        toastError(error)
      }
    } finally {
      setPublishing(false)
    }
  }

  const hostLiveRoom = async () => {
    try {
      const room = await createRoom.mutateAsync({ quizId: quiz.id })
      toastSuccess('Live room created')
      navigate(`/admin/live-rooms/${room.id}`)
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Review & publish</CardTitle>
            <CardDescription>Confirm details, then validate to mark the quiz Ready.</CardDescription>
          </div>
          <StatusBadge status={quiz.status} />
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <h3 className="text-sm font-medium text-[var(--muted-foreground)]">Title</h3>
            <p className="text-lg font-semibold text-[#f0f4fa]">{quiz.title}</p>
            {quiz.description ? (
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">{quiz.description}</p>
            ) : (
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">No description</p>
            )}
          </div>

          <div>
            <h3 className="mb-2 text-sm font-medium text-[var(--muted-foreground)]">
              Configuration
            </h3>
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-[var(--muted-foreground)]">Time bonus</dt>
                <dd>
                  {config?.timeBonusEnabled
                    ? `On (max ${config.timeBonusMaxPoints})`
                    : 'Off'}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--muted-foreground)]">Streak bonus</dt>
                <dd>{config?.streakBonusEnabled ? 'On' : 'Off'}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted-foreground)]">Shuffle questions</dt>
                <dd>{config?.questionOrderShuffle ? 'On' : 'Off'}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted-foreground)]">Shuffle options</dt>
                <dd>{config?.answerOptionShuffle ? 'On' : 'Off'}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted-foreground)]">Answer reveal</dt>
                <dd>{config?.answerRevealBehavior ?? 'after_each'}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted-foreground)]">Question advance</dt>
                <dd>{config?.questionAdvanceMode ?? 'manual'}</dd>
              </div>
            </dl>
          </div>

          <div>
            <h3 className="mb-2 text-sm font-medium text-[var(--muted-foreground)]">
              Questions by section
            </h3>
            {!hasSections ? (
              <EmptyState title="No sections" description="Cannot load questions without sections." />
            ) : (
              <div className="space-y-6">
                {sections.map((section) => (
                  <SectionQuestionsReview key={section.id} quizId={quiz.id} section={section} />
                ))}
              </div>
            )}
          </div>

          {checklist.length > 0 ? (
            <Alert variant="destructive">
              <AlertTitle>Ready checklist failed</AlertTitle>
              <AlertDescription>
                <ul className="mt-2 list-disc space-y-1 pl-4">
                  {checklist.map((item, i) => (
                    <li key={`${item.field ?? 'err'}-${i}`}>
                      {item.field ? (
                        <span className="font-mono text-xs opacity-80">{item.field}: </span>
                      ) : null}
                      {item.message}
                    </li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => onBack(1)}>
              Edit details
            </Button>
            <Button variant="outline" onClick={() => onBack(2)}>
              Edit questions
            </Button>
            <Button onClick={() => void onPublish()} disabled={publishing}>
              {publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Publish
            </Button>
            {quiz.status === 'Ready' ? (
              <Button variant="secondary" onClick={() => void hostLiveRoom()}>
                <Radio className="h-4 w-4" />
                Host live room
              </Button>
            ) : null}
            <Button variant="ghost" onClick={() => navigate('/admin/quizzes')}>
              Back to quizzes
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
