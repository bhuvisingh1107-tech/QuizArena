import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { ExternalLink, Loader2, RefreshCw, Save, Trash2 } from 'lucide-react'

import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { queryKeys } from '@/hooks/queries/keys'
import { useAiGenerationMutations, useAiJobQuery } from '@/hooks/queries/useAiGeneration'
import { firstMcqOptionError } from '@/lib/mcq-validation'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import type { AiGeneratedQuestion, AiJobStatus, AiOption } from '@/types/ai-generation'
import { cn } from '@/lib/utils'

const ACTIVE = new Set(['queued', 'uploading', 'extracting', 'analyzing', 'generating'])

const STATUS_LABEL: Record<AiJobStatus, string> = {
  queued: 'Queued',
  uploading: 'Uploading',
  extracting: 'Extracting',
  analyzing: 'Analyzing',
  generating: 'Generating',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

export function AiReviewPage() {
  const { jobId = '' } = useParams()
  const navigate = useNavigate()
  const mutations = useAiGenerationMutations()
  const queryClient = useQueryClient()
  const { data: job, isLoading, error, refetch } = useAiJobQuery(jobId, { poll: true })
  const notifiedComplete = useRef(false)

  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(null)

  const allQuestions = useMemo(
    () =>
      job?.sections.flatMap((s) =>
        s.questions.map((q) => ({ sectionId: s.id, sectionName: s.name, question: q })),
      ) ?? [],
    [job],
  )

  useEffect(() => {
    if (!selectedQuestionId && allQuestions[0]) {
      setSelectedQuestionId(allQuestions[0].question.id)
    }
  }, [allQuestions, selectedQuestionId])

  useEffect(() => {
    if (job?.status === 'completed' && !notifiedComplete.current) {
      notifiedComplete.current = true
      void queryClient.invalidateQueries({ queryKey: queryKeys.quizzes.all })
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary })
      if (job.resultQuizId) {
        toastSuccess('Quiz saved to My Quizzes')
      }
    }
    if (job && ACTIVE.has(job.status)) {
      notifiedComplete.current = false
    }
  }, [job?.status, job?.resultQuizId, queryClient])

  const selected = allQuestions.find((q) => q.question.id === selectedQuestionId)

  const mcqIssues = useMemo(() => {
    return allQuestions
      .map(({ question }) => {
        const message = firstMcqOptionError(
          (question.options ?? []).map((o) => ({
            text: o.text,
            isCorrect: o.isCorrect,
          })),
        )
        return message
          ? { questionId: question.id, promptText: question.promptText, message }
          : null
      })
      .filter((item): item is { questionId: string; promptText: string; message: string } =>
        Boolean(item),
      )
  }, [allQuestions])

  const hasInvalidMcq = mcqIssues.length > 0
  const canSaveQuiz = !hasInvalidMcq

  const onSave = async () => {
    if (hasInvalidMcq) {
      toastError(new Error(mcqIssues[0]?.message ?? 'Fix invalid MCQ questions before saving'))
      return
    }
    try {
      const result = await mutations.save.mutateAsync(jobId)
      toastSuccess('Quiz updated in My Quizzes')
      navigate(`/admin/quizzes/${result.quizId}?step=2`)
    } catch (err) {
      toastError(err)
    }
  }

  const onCancel = async () => {
    try {
      await mutations.cancel.mutateAsync(jobId)
      toastSuccess('Job cancelled')
      await refetch()
    } catch (err) {
      toastError(err)
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center gap-2 text-[var(--muted-foreground)]">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading generation job…
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="space-y-4">
        <PageHeader title="AI generation" description="Job not found." />
        <Button asChild variant="outline">
          <Link to="/admin/quizzes/ai">Back</Link>
        </Button>
      </div>
    )
  }

  const inProgress = ACTIVE.has(job.status)

  return (
    <div className="space-y-6">
      <PageHeader
        title={job.title || job.topic || 'AI quiz draft'}
        description={
          inProgress
            ? job.progressMessage || 'Generating…'
            : job.status === 'completed'
              ? job.resultQuizId
                ? 'Quiz is in My Quizzes. Review or open the builder.'
                : 'Review sections and questions, then save.'
              : job.errorMessage || `Status: ${STATUS_LABEL[job.status]}`
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link to="/admin/quizzes/ai">New generation</Link>
            </Button>
            {inProgress ? (
              <Button variant="outline" onClick={() => void onCancel()} disabled={mutations.cancel.isPending}>
                Cancel
              </Button>
            ) : null}
            {job.status === 'completed' ? (
              <>
                {job.resultQuizId ? (
                  <Button asChild variant="accent">
                    <Link to={`/admin/quizzes/${job.resultQuizId}?step=2`}>
                      <ExternalLink className="h-4 w-4" />
                      Open in My Quizzes
                    </Link>
                  </Button>
                ) : null}
                <Button
                  variant="outline"
                  disabled={mutations.regenerateQuiz.isPending}
                  onClick={() => {
                    void mutations.regenerateQuiz
                      .mutateAsync(jobId)
                      .then(() => {
                        toastSuccess('Full regeneration started')
                        return refetch()
                      })
                      .catch(toastError)
                  }}
                >
                  <RefreshCw className="h-4 w-4" />
                  Regenerate quiz
                </Button>
                <Button
                  onClick={() => void onSave()}
                  disabled={mutations.save.isPending || !canSaveQuiz}
                >
                  <Save className="h-4 w-4" />
                  {job.resultQuizId ? 'Re-save quiz' : 'Save quiz'}
                </Button>
              </>
            ) : null}
          </div>
        }
      />

      {job.status === 'completed' && hasInvalidMcq ? (
        <Card>
          <CardContent className="space-y-2 pt-6 text-sm text-[var(--destructive)]">
            <p className="font-medium">Fix invalid MCQs before saving:</p>
            <ul className="list-disc space-y-1 pl-5">
              {mcqIssues.map((issue) => (
                <li key={issue.questionId}>
                  {issue.promptText || 'Untitled'}: {issue.message}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {inProgress || job.status === 'failed' ? (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-[var(--heading)]">
                {STATUS_LABEL[job.status]}
                {job.progressMessage ? ` · ${job.progressMessage}` : ''}
              </span>
              <span className="font-medium">{job.progressPercent}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-[var(--secondary)]">
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-500',
                  job.status === 'failed' ? 'bg-red-500' : 'bg-[var(--primary)]',
                )}
                style={{ width: `${Math.max(4, job.progressPercent)}%` }}
              />
            </div>
            {job.status === 'failed' ? (
              <p className="whitespace-pre-wrap break-words text-sm text-red-600">
                {job.errorMessage || 'Generation failed'}
              </p>
            ) : (
              <p className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
                <Loader2 className="h-4 w-4 animate-spin" />
                Working — this page updates automatically.
              </p>
            )}
          </CardContent>
        </Card>
      ) : null}

      {job.sources.length > 0 ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Sources</CardTitle>
            <CardDescription>Attribution for this generation.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {job.sources.map((src) => (
              <div key={src.id} className="text-sm">
                <span className="font-medium text-[var(--heading)]">{src.title}</span>
                <span className="text-[var(--muted-foreground)]"> · {src.locator}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {job.status === 'completed' && job.sections.length > 0 ? (
        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          <Card className="h-fit">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Detected sections</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {job.sections.map((section) => (
                <div key={section.id} className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-[var(--heading)]">{section.name}</p>
                      <p className="text-xs text-[var(--muted-foreground)]">
                        {section.questions.length} questions
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      title="Regenerate section"
                      disabled={mutations.regenerateSection.isPending}
                      onClick={() => {
                        void mutations.regenerateSection
                          .mutateAsync(section.id)
                          .then(() => {
                            toastSuccess('Section regenerated')
                            return refetch()
                          })
                          .catch(toastError)
                      }}
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  <div className="space-y-1">
                    {section.questions.map((q, idx) => (
                      <button
                        key={q.id}
                        type="button"
                        onClick={() => setSelectedQuestionId(q.id)}
                        className={cn(
                          'w-full rounded-md px-2 py-1.5 text-left text-sm transition',
                          selectedQuestionId === q.id
                            ? 'bg-[var(--primary)]/15 text-[var(--heading)]'
                            : 'hover:bg-[var(--secondary)] text-[var(--muted-foreground)]',
                        )}
                      >
                        Q{idx + 1}. {q.promptText.slice(0, 48)}
                        {q.promptText.length > 48 ? '…' : ''}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {selected ? (
            <QuestionEditor
              key={selected.question.id}
              sectionName={selected.sectionName}
              question={selected.question}
              busy={
                mutations.patchQuestion.isPending ||
                mutations.deleteQuestion.isPending ||
                mutations.regenerateQuestion.isPending
              }
              onSave={async (patch) => {
                try {
                  await mutations.patchQuestion.mutateAsync({
                    questionId: selected.question.id,
                    body: patch,
                  })
                  toastSuccess('Question updated')
                  await refetch()
                } catch (err) {
                  toastError(err)
                }
              }}
              onDelete={async () => {
                try {
                  await mutations.deleteQuestion.mutateAsync(selected.question.id)
                  setSelectedQuestionId(null)
                  toastSuccess('Question deleted')
                  await refetch()
                } catch (err) {
                  toastError(err)
                }
              }}
              onRegenerate={async () => {
                try {
                  await mutations.regenerateQuestion.mutateAsync(selected.question.id)
                  toastSuccess('Question regenerated')
                  await refetch()
                } catch (err) {
                  toastError(err)
                }
              }}
            />
          ) : null}
        </div>
      ) : null}

      {job.status === 'completed' && job.sections.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-[var(--muted-foreground)]">
            No questions were generated. Start a new job or check source material.
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}

function QuestionEditor({
  sectionName,
  question,
  busy,
  onSave,
  onDelete,
  onRegenerate,
}: {
  sectionName: string
  question: AiGeneratedQuestion
  busy: boolean
  onSave: (patch: {
    promptText: string
    explanation: string
    estimatedTimeSeconds: number
    options: AiOption[]
  }) => Promise<void>
  onDelete: () => Promise<void>
  onRegenerate: () => Promise<void>
}) {
  const [promptText, setPromptText] = useState(question.promptText)
  const [explanation, setExplanation] = useState(question.explanation || '')
  const [estimatedTimeSeconds, setEstimatedTimeSeconds] = useState(question.estimatedTimeSeconds)
  const [options, setOptions] = useState<AiOption[]>(question.options)
  const optionsError = firstMcqOptionError(
    options.map((o) => ({ text: o.text, isCorrect: o.isCorrect })),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Edit question</CardTitle>
        <CardDescription>
          {sectionName} · {question.difficulty} · {question.kind}
          {question.topicLabel ? ` · ${question.topicLabel}` : ''}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="prompt">Question</Label>
          <Textarea id="prompt" value={promptText} onChange={(e) => setPromptText(e.target.value)} rows={3} />
        </div>

        <div className="space-y-2">
          <Label>Options</Label>
          <div className="space-y-2">
            {options.map((opt, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <input
                  type="radio"
                  name={`correct-${question.id}`}
                  checked={opt.isCorrect}
                  aria-label={`Mark option ${idx + 1} correct`}
                  onChange={() => {
                    setOptions(
                      options.map((item, i) => ({
                        ...item,
                        isCorrect: i === idx,
                      })),
                    )
                  }}
                />
                <Input
                  value={opt.text}
                  onChange={(e) => {
                    const next = [...options]
                    next[idx] = { ...next[idx], text: e.target.value }
                    setOptions(next)
                  }}
                />
              </div>
            ))}
          </div>
          {optionsError ? (
            <p className="text-xs text-[var(--destructive)]">{optionsError}</p>
          ) : (
            <p className="text-xs text-[var(--muted-foreground)]">
              Select exactly one correct answer. MCQs need exactly 4 filled options.
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="explanation">Explanation</Label>
          <Textarea
            id="explanation"
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
            rows={3}
          />
        </div>

        {question.sourceLocator ? (
          <p className="text-xs text-[var(--muted-foreground)]">Source: {question.sourceLocator}</p>
        ) : null}

        <div className="space-y-2">
          <Label htmlFor="time">Estimated time (seconds)</Label>
          <Input
            id="time"
            type="number"
            min={5}
            max={300}
            value={estimatedTimeSeconds}
            onChange={(e) => setEstimatedTimeSeconds(Number(e.target.value) || 30)}
          />
        </div>

        <div className="flex flex-wrap gap-2 pt-2">
          <Button
            disabled={busy || Boolean(optionsError)}
            onClick={() =>
              void onSave({
                promptText,
                explanation,
                estimatedTimeSeconds,
                options,
              })
            }
          >
            Save changes
          </Button>
          <Button variant="outline" disabled={busy} onClick={() => void onRegenerate()}>
            <RefreshCw className="h-4 w-4" />
            Regenerate
          </Button>
          <Button variant="destructive" disabled={busy} onClick={() => void onDelete()}>
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
