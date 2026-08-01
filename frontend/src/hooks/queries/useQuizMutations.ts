import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiDelete, apiGet, apiPatch, apiPost } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type {
  AnswerOption,
  AnswerOptionList,
  Question,
  QuestionList,
  Quiz,
  QuizCreateInput,
  QuizDeleteResult,
  QuizUpdateInput,
  Section,
  SectionList,
} from '@/types/api'

export function useQuizMutations() {
  const queryClient = useQueryClient()

  const invalidateQuizzes = async (quizId?: string) => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.quizzes.all })
    if (quizId) {
      await queryClient.invalidateQueries({ queryKey: queryKeys.quizzes.detail(quizId) })
    }
  }

  const createQuiz = useMutation({
    mutationFn: (input: QuizCreateInput) => apiPost<Quiz>('/quizzes', input),
    onSuccess: async () => {
      await invalidateQuizzes()
    },
  })

  const updateQuiz = useMutation({
    mutationFn: ({ quizId, input }: { quizId: string; input: QuizUpdateInput }) =>
      apiPatch<Quiz>(`/quizzes/${quizId}`, input),
    onSuccess: async (quiz) => {
      await invalidateQuizzes(quiz.id)
    },
  })

  const deleteQuiz = useMutation({
    mutationFn: ({ quizId, hard = false }: { quizId: string; hard?: boolean }) =>
      apiDelete<QuizDeleteResult>(`/quizzes/${quizId}`, { params: { hard } }),
    onSuccess: async (result) => {
      await invalidateQuizzes(result.id)
    },
  })

  const publishQuiz = useMutation({
    mutationFn: (quizId: string) => apiPost<Quiz>(`/quizzes/${quizId}/validate`),
    onSuccess: async (quiz) => {
      await invalidateQuizzes(quiz.id)
    },
  })

  const archiveQuiz = useMutation({
    mutationFn: (quizId: string) => apiPost<Quiz>(`/quizzes/${quizId}/archive`),
    onSuccess: async (quiz) => {
      await invalidateQuizzes(quiz.id)
    },
  })

  const restoreQuiz = useMutation({
    mutationFn: (quizId: string) => apiPost<Quiz>(`/quizzes/${quizId}/restore`),
    onSuccess: async (quiz) => {
      await invalidateQuizzes(quiz.id)
    },
  })

  const duplicateQuiz = useMutation({
    mutationFn: async (quizId: string) => {
      const source = await apiGet<Quiz>(`/quizzes/${quizId}`)
      const created = await apiPost<Quiz>('/quizzes', {
        title: `${source.title} (Copy)`,
        description: source.description ?? null,
        config: source.config ?? null,
      })

      const sections = await apiGet<SectionList>(`/quizzes/${quizId}/sections`)
      const orderedSections = [...sections.items].sort((a, b) => a.sortOrder - b.sortOrder)

      for (const section of orderedSections) {
        const newSection = await apiPost<Section>(`/quizzes/${created.id}/sections`, {
          name: section.name,
          sortOrder: section.sortOrder,
        })

        const questions = await apiGet<QuestionList>(
          `/quizzes/${quizId}/sections/${section.id}/questions`,
        )
        const orderedQuestions = [...questions.items].sort((a, b) => a.sortOrder - b.sortOrder)

        for (const question of orderedQuestions) {
          const newQuestion = await apiPost<Question>(
            `/quizzes/${created.id}/sections/${newSection.id}/questions`,
            {
              questionType: question.questionType,
              promptText: question.promptText ?? '',
              explanation: question.explanation ?? null,
              basePoints: question.basePoints,
              timeLimitSeconds: question.timeLimitSeconds ?? null,
              allowMultipleCorrect: question.allowMultipleCorrect,
              sortOrder: question.sortOrder,
            },
          )

          const options = await apiGet<AnswerOptionList>(
            `/quizzes/${quizId}/sections/${section.id}/questions/${question.id}/options`,
          )
          const orderedOptions = [...options.items].sort((a, b) => a.sortOrder - b.sortOrder)

          for (const option of orderedOptions) {
            await apiPost<AnswerOption>(
              `/quizzes/${created.id}/sections/${newSection.id}/questions/${newQuestion.id}/options`,
              {
                text: option.text,
                isCorrect: option.isCorrect,
                sortOrder: option.sortOrder,
              },
            )
          }

          if (question.mediaFileId) {
            await apiPost<{ mediaId: string; questionId: string; mediaFileId: string }>(
              `/media/${question.mediaFileId}/attach`,
              {
                quizId: created.id,
                sectionId: newSection.id,
                questionId: newQuestion.id,
              },
            )
          }
        }
      }

      return created
    },
    onSuccess: async () => {
      await invalidateQuizzes()
    },
  })

  return {
    createQuiz,
    updateQuiz,
    deleteQuiz,
    publishQuiz,
    archiveQuiz,
    restoreQuiz,
    duplicateQuiz,
  }
}
