import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2 } from 'lucide-react'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

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
import type { Quiz, QuizCreateInput } from '@/types/api'

export const quizDetailsSchema = z.object({
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

export type QuizDetailsFormValues = z.infer<typeof quizDetailsSchema>

export function quizDetailsToInput(values: QuizDetailsFormValues): QuizCreateInput {
  return {
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
  }
}

export const DEFAULT_QUIZ_DETAILS: QuizDetailsFormValues = {
  title: '',
  description: '',
  questionAdvanceMode: 'manual',
  answerRevealBehavior: 'after_each',
  timeBonusEnabled: false,
  timeBonusMaxPoints: 0,
  streakBonusEnabled: false,
  questionOrderShuffle: false,
  answerOptionShuffle: false,
}

export function quizToDetailsValues(quiz: Quiz): QuizDetailsFormValues {
  return {
    title: quiz.title,
    description: quiz.description ?? '',
    questionAdvanceMode: quiz.config?.questionAdvanceMode ?? 'manual',
    answerRevealBehavior: quiz.config?.answerRevealBehavior ?? 'after_each',
    timeBonusEnabled: quiz.config?.timeBonusEnabled ?? false,
    timeBonusMaxPoints: quiz.config?.timeBonusMaxPoints ?? 0,
    streakBonusEnabled: quiz.config?.streakBonusEnabled ?? false,
    questionOrderShuffle: quiz.config?.questionOrderShuffle ?? false,
    answerOptionShuffle: quiz.config?.answerOptionShuffle ?? false,
  }
}

interface QuizDetailsStepProps {
  quiz?: Quiz | null
  submitting?: boolean
  onSave: (values: QuizDetailsFormValues) => Promise<void>
  submitLabel?: string
}

export function QuizDetailsStep({
  quiz,
  submitting = false,
  onSave,
  submitLabel = 'Save & Continue',
}: QuizDetailsStepProps) {
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<QuizDetailsFormValues>({
    resolver: zodResolver(quizDetailsSchema),
    defaultValues: quiz ? quizToDetailsValues(quiz) : DEFAULT_QUIZ_DETAILS,
  })

  useEffect(() => {
    if (quiz) reset(quizToDetailsValues(quiz))
  }, [quiz, reset])

  const busy = isSubmitting || submitting

  return (
    <Card>
      <CardHeader>
        <CardTitle>Quiz details</CardTitle>
        <CardDescription>Title, scoring, shuffle, and advance behavior.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={handleSubmit(async (values) => {
            await onSave(values)
          })}
          className="space-y-5"
          noValidate
        >
          <div className="space-y-2">
            <Label htmlFor="builder-title">Title</Label>
            <Input
              id="builder-title"
              placeholder="Friday trivia night"
              {...register('title')}
            />
            {errors.title ? (
              <p className="text-xs text-[var(--destructive)]">{errors.title.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="builder-description">Description</Label>
            <Textarea
              id="builder-description"
              rows={3}
              placeholder="Optional overview for hosts"
              {...register('description')}
            />
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-medium text-[#f0f4fa]">Scoring</h3>
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
              <label className="flex items-center justify-between rounded-md border border-[var(--border)] px-3 py-2 sm:col-span-2">
                <span className="text-sm">Streak bonus</span>
                <Switch
                  checked={watch('streakBonusEnabled')}
                  onCheckedChange={(checked) =>
                    setValue('streakBonusEnabled', checked, { shouldDirty: true })
                  }
                />
              </label>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-medium text-[#f0f4fa]">Shuffle</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex items-center justify-between rounded-md border border-[var(--border)] px-3 py-2">
                <span className="text-sm">Shuffle questions</span>
                <Switch
                  checked={watch('questionOrderShuffle')}
                  onCheckedChange={(checked) =>
                    setValue('questionOrderShuffle', checked, { shouldDirty: true })
                  }
                />
              </label>
              <label className="flex items-center justify-between rounded-md border border-[var(--border)] px-3 py-2">
                <span className="text-sm">Shuffle answer options</span>
                <Switch
                  checked={watch('answerOptionShuffle')}
                  onCheckedChange={(checked) =>
                    setValue('answerOptionShuffle', checked, { shouldDirty: true })
                  }
                />
              </label>
            </div>
          </div>

          <details className="rounded-md border border-[var(--border)] px-4 py-3">
            <summary className="cursor-pointer text-sm font-medium text-[#f0f4fa]">
              Advanced (optional)
            </summary>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
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
            </div>
          </details>

          <div className="flex justify-end">
            <Button type="submit" disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {submitLabel}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
