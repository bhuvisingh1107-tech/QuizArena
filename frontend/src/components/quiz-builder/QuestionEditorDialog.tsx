import { Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  defaultMcqOptions,
  defaultTrueFalseOptions,
  inferQuestionKind,
  McqOptionsEditor,
  type BuilderQuestionKind,
  type DraftOption,
} from '@/components/quiz-builder/McqOptionsEditor'
import { QuestionMediaSection } from '@/components/quiz-builder/QuestionMediaSection'
import { Button } from '@/components/ui/button'
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
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { apiDelete, apiGet, apiPatch, apiPost } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import { firstMcqOptionError } from '@/lib/mcq-validation'
import { useQueryClient } from '@tanstack/react-query'
import { toastError, toastSuccess } from '@/lib/toast-helpers'
import { cn } from '@/lib/utils'
import type {
  AnswerOption,
  AnswerOptionList,
  Question,
  QuestionCreateInput,
  QuestionUpdateInput,
} from '@/types/api'

interface QuestionEditorDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  quizId: string
  sectionId: string
  question: Question | null
  nextSortOrder: number
  onSaved: (question: Question) => void
}

async function syncOptions(
  quizId: string,
  sectionId: string,
  questionId: string,
  desired: DraftOption[],
  existing: AnswerOption[],
) {
  const base = `/quizzes/${quizId}/sections/${sectionId}/questions/${questionId}/options`
  const keptIds = new Set(desired.map((o) => o.id).filter(Boolean) as string[])

  for (const opt of existing) {
    if (!keptIds.has(opt.id)) {
      await apiDelete(`${base}/${opt.id}`)
    }
  }

  for (const opt of desired) {
    if (opt.id) {
      const prev = existing.find((e) => e.id === opt.id)
      if (
        !prev ||
        prev.text !== opt.text ||
        prev.isCorrect !== opt.isCorrect ||
        prev.sortOrder !== opt.sortOrder
      ) {
        await apiPatch(`${base}/${opt.id}`, {
          text: opt.text,
          isCorrect: opt.isCorrect,
          sortOrder: opt.sortOrder,
        })
      }
    } else {
      await apiPost(base, {
        text: opt.text,
        isCorrect: opt.isCorrect,
        sortOrder: opt.sortOrder,
      })
    }
  }
}

export function QuestionEditorDialog({
  open,
  onOpenChange,
  quizId,
  sectionId,
  question,
  nextSortOrder,
  onSaved,
}: QuestionEditorDialogProps) {
  const queryClient = useQueryClient()
  const isEdit = Boolean(question)

  const [kind, setKind] = useState<BuilderQuestionKind>('mcq')
  const [promptText, setPromptText] = useState('')
  const [explanation, setExplanation] = useState('')
  const [basePoints, setBasePoints] = useState(1)
  const [timeLimitSeconds, setTimeLimitSeconds] = useState<string>('')
  const [options, setOptions] = useState<DraftOption[]>(defaultMcqOptions())
  const [mediaFileId, setMediaFileId] = useState<string | null>(null)
  const [questionId, setQuestionId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [promptError, setPromptError] = useState<string | null>(null)
  const [optionsError, setOptionsError] = useState<string | null>(null)
  const [loadingOptions, setLoadingOptions] = useState(false)

  useEffect(() => {
    if (!open) return

    let cancelled = false

    const load = async () => {
      setPromptError(null)
      setOptionsError(null)

      if (!question) {
        setKind('mcq')
        setPromptText('')
        setExplanation('')
        setBasePoints(1)
        setTimeLimitSeconds('')
        setOptions(defaultMcqOptions())
        setMediaFileId(null)
        setQuestionId(null)
        return
      }

      setQuestionId(question.id)
      setPromptText(question.promptText ?? '')
      setExplanation(question.explanation ?? '')
      setBasePoints(question.basePoints)
      setTimeLimitSeconds(
        question.timeLimitSeconds != null ? String(question.timeLimitSeconds) : '',
      )
      setMediaFileId(question.mediaFileId ?? null)
      setLoadingOptions(true)

      try {
        const list = await apiGet<AnswerOptionList>(
          `/quizzes/${quizId}/sections/${sectionId}/questions/${question.id}/options`,
        )
        if (cancelled) return
        const ordered = [...list.items].sort((a, b) => a.sortOrder - b.sortOrder)
        const inferred = inferQuestionKind(ordered)
        setKind(inferred)
        if (inferred === 'true_false') {
          const correct = ordered.find((o) => o.isCorrect)?.text === 'False' ? 'False' : 'True'
          setOptions(
            defaultTrueFalseOptions(correct).map((draft, i) => ({
              ...draft,
              id: ordered[i]?.id,
            })),
          )
        } else {
          const drafts: DraftOption[] = [0, 1, 2, 3].map((i) => {
            const existing = ordered[i]
            return existing
              ? {
                  id: existing.id,
                  text: existing.text,
                  isCorrect: existing.isCorrect,
                  sortOrder: i,
                }
              : { text: '', isCorrect: false, sortOrder: i }
          })
          const correctIndexes = drafts
            .map((d, i) => (d.isCorrect ? i : -1))
            .filter((i) => i >= 0)
          if (correctIndexes.length !== 1 && drafts[0]) {
            drafts.forEach((d, i) => {
              d.isCorrect = i === (correctIndexes[0] ?? 0)
            })
          }
          setOptions(drafts)
        }
      } catch (error) {
        if (!cancelled) toastError(error)
      } finally {
        if (!cancelled) setLoadingOptions(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [open, question, quizId, sectionId])

  const switchKind = (next: BuilderQuestionKind) => {
    setKind(next)
    setOptionsError(null)
    if (next === 'true_false') {
      setOptions(defaultTrueFalseOptions())
    } else {
      setOptions(defaultMcqOptions())
    }
  }

  const validate = (): boolean => {
    const trimmed = promptText.trim()
    if (!trimmed) {
      setPromptError('Question text is required')
      return false
    }
    setPromptError(null)

    const optionError = firstMcqOptionError(
      options.map((o) => ({ text: o.text, isCorrect: o.isCorrect })),
    )
    if (optionError) {
      setOptionsError(optionError)
      return false
    }
    setOptionsError(null)
    return true
  }

  const save = async () => {
    if (!validate()) return
    setSaving(true)
    const wasExisting = Boolean(questionId)
    try {
      const timeLimit =
        timeLimitSeconds.trim() === '' ? null : Math.max(1, Number(timeLimitSeconds))

      const payloadBase = {
        questionType: 'Text' as const,
        promptText: promptText.trim(),
        explanation: explanation.trim() || null,
        basePoints: Math.max(1, basePoints),
        timeLimitSeconds: Number.isFinite(timeLimit) ? timeLimit : null,
        // Builder MCQs are always single-correct.
        allowMultipleCorrect: false,
      }

      let saved: Question
      if (questionId) {
        const input: QuestionUpdateInput = payloadBase
        saved = await apiPatch<Question>(
          `/quizzes/${quizId}/sections/${sectionId}/questions/${questionId}`,
          input,
        )
      } else {
        const input: QuestionCreateInput = {
          ...payloadBase,
          sortOrder: nextSortOrder,
        }
        saved = await apiPost<Question>(
          `/quizzes/${quizId}/sections/${sectionId}/questions`,
          input,
        )
        setQuestionId(saved.id)
      }

      const existing = wasExisting
        ? (
            await apiGet<AnswerOptionList>(
              `/quizzes/${quizId}/sections/${sectionId}/questions/${saved.id}/options`,
            )
          ).items
        : []

      // MCQ always persists all 4 slots; true/false keeps both.
      const desired: DraftOption[] = options.map((o, i) => ({
        ...o,
        text: o.text.trim(),
        sortOrder: i,
        isCorrect: Boolean(o.isCorrect),
      }))

      await syncOptions(quizId, sectionId, saved.id, desired, existing)

      const refreshed = await apiGet<AnswerOptionList>(
        `/quizzes/${quizId}/sections/${sectionId}/questions/${saved.id}/options`,
      )
      const ordered = [...refreshed.items].sort((a, b) => a.sortOrder - b.sortOrder)
      setOptions(
        desired.map((draft, i) => ({
          ...draft,
          id: ordered[i]?.id ?? draft.id,
          text: ordered[i]?.text ?? draft.text,
          isCorrect: ordered[i]?.isCorrect ?? draft.isCorrect,
          sortOrder: i,
        })),
      )
      setMediaFileId(saved.mediaFileId ?? mediaFileId)

      await queryClient.invalidateQueries({
        queryKey: queryKeys.questions.list(quizId, sectionId),
      })
      await queryClient.invalidateQueries({
        queryKey: queryKeys.options.list(quizId, sectionId, saved.id),
      })

      toastSuccess(wasExisting ? 'Question updated' : 'Question created')
      onSaved(saved)
      if (wasExisting) {
        onOpenChange(false)
      }
      // Keep dialog open after first create so media can be attached immediately.
    } catch (error) {
      toastError(error)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit question' : 'Add question'}</DialogTitle>
          <DialogDescription>
            Multiple choice and true/false are supported. Short answer is not available in v1.
          </DialogDescription>
        </DialogHeader>

        {loadingOptions ? (
          <div className="flex items-center gap-2 py-8 text-sm text-[var(--muted-foreground)]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading question…
          </div>
        ) : (
          <div className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="q-prompt">Question text</Label>
              <Textarea
                id="q-prompt"
                rows={3}
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                placeholder="What is the capital of France?"
              />
              {promptError ? (
                <p className="text-xs text-[var(--destructive)]">{promptError}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="q-explanation">Explanation (optional)</Label>
              <Textarea
                id="q-explanation"
                rows={2}
                value={explanation}
                onChange={(e) => setExplanation(e.target.value)}
                placeholder="Shown after reveal when configured"
              />
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-[#f0f4fa]">Question type</p>
              <div className="flex flex-wrap gap-2">
                {(
                  [
                    { id: 'mcq' as const, label: 'Multiple Choice' },
                    { id: 'true_false' as const, label: 'True/False' },
                  ] as const
                ).map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => switchKind(item.id)}
                    className={cn(
                      'rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
                      kind === item.id
                        ? 'border-[var(--primary)] bg-[var(--primary)]/15 text-[var(--primary)]'
                        : 'border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--secondary)]',
                    )}
                  >
                    {item.label}
                  </button>
                ))}
                <button
                  type="button"
                  disabled
                  className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--muted-foreground)] opacity-60"
                  title="Not available in v1"
                >
                  Short Answer · Not in v1
                </button>
              </div>
            </div>

            <McqOptionsEditor
              kind={kind}
              options={options}
              allowMultipleCorrect={false}
              onChange={setOptions}
              error={optionsError}
            />

            <QuestionMediaSection
              quizId={quizId}
              sectionId={sectionId}
              questionId={questionId}
              mediaFileId={mediaFileId}
              onAttached={(id) => setMediaFileId(id)}
              onCleared={() => setMediaFileId(null)}
            />

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="q-points">Points</Label>
                <Input
                  id="q-points"
                  type="number"
                  min={1}
                  value={basePoints}
                  onChange={(e) => setBasePoints(Math.max(1, Number(e.target.value) || 1))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="q-time">Time limit (seconds, optional)</Label>
                <Input
                  id="q-time"
                  type="number"
                  min={1}
                  placeholder="No limit"
                  value={timeLimitSeconds}
                  onChange={(e) => setTimeLimitSeconds(e.target.value)}
                />
              </div>
            </div>

            <label className="flex items-center justify-between rounded-md border border-[var(--border)] px-3 py-2 opacity-80">
              <div>
                <span className="text-sm">Required</span>
                <p className="text-xs text-[var(--muted-foreground)]">
                  All questions are required in live play
                </p>
              </div>
              <Switch checked disabled />
            </label>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void save()} disabled={saving || loadingOptions}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Save question
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
