import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2 } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useQuizMutations } from '@/hooks/queries/useQuizMutations'
import { toastError, toastSuccess } from '@/lib/toast-helpers'

const createFormSchema = z.object({
  title: z.string().min(1, 'Title is required').max(255),
  description: z.string().max(10_000).optional(),
})

type CreateFormValues = z.infer<typeof createFormSchema>

export function CreateQuizPage() {
  const navigate = useNavigate()
  const { createQuiz } = useQuizMutations()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CreateFormValues>({
    resolver: zodResolver(createFormSchema),
    defaultValues: { title: '', description: '' },
  })

  const onSubmit = handleSubmit(async (values) => {
    try {
      const quiz = await createQuiz.mutateAsync({
        title: values.title.trim(),
        description: values.description?.trim() || null,
      })
      toastSuccess('Quiz created')
      navigate(`/admin/quizzes/${quiz.id}`, { replace: true })
    } catch (error) {
      toastError(error)
    }
  })

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="Create quiz"
        description="Start a draft quiz. You can add sections and questions next."
        actions={
          <Button asChild variant="outline">
            <Link to="/admin/quizzes">Cancel</Link>
          </Button>
        }
      />

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={onSubmit} className="space-y-5" noValidate>
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" placeholder="Friday trivia night" {...register('title')} />
              {errors.title ? (
                <p className="text-xs text-[var(--destructive)]">{errors.title.message}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                rows={4}
                placeholder="Optional overview for hosts"
                {...register('description')}
              />
              {errors.description ? (
                <p className="text-xs text-[var(--destructive)]">{errors.description.message}</p>
              ) : null}
            </div>

            <div className="flex justify-end gap-2">
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Create quiz
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
