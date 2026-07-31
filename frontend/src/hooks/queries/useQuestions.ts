import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiDelete, apiGet, apiPatch, apiPost } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type {
  Question,
  QuestionCreateInput,
  QuestionList,
  QuestionUpdateInput,
} from '@/types/api'

export function useQuestions(
  quizId: string | undefined,
  sectionId: string | undefined,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.questions.list(quizId ?? '', sectionId ?? ''),
    queryFn: () =>
      apiGet<QuestionList>(`/quizzes/${quizId}/sections/${sectionId}/questions`),
    enabled: Boolean(quizId && sectionId) && enabled,
  })
}

export function useQuestionMutations(quizId: string, sectionId: string) {
  const queryClient = useQueryClient()

  const invalidate = async () => {
    await queryClient.invalidateQueries({
      queryKey: queryKeys.questions.list(quizId, sectionId),
    })
  }

  const createQuestion = useMutation({
    mutationFn: (input: QuestionCreateInput) =>
      apiPost<Question>(`/quizzes/${quizId}/sections/${sectionId}/questions`, input),
    onSuccess: invalidate,
  })

  const updateQuestion = useMutation({
    mutationFn: ({
      questionId,
      input,
    }: {
      questionId: string
      input: QuestionUpdateInput
    }) =>
      apiPatch<Question>(
        `/quizzes/${quizId}/sections/${sectionId}/questions/${questionId}`,
        input,
      ),
    onSuccess: invalidate,
  })

  const deleteQuestion = useMutation({
    mutationFn: (questionId: string) =>
      apiDelete<{ id: string; deleted: boolean }>(
        `/quizzes/${quizId}/sections/${sectionId}/questions/${questionId}`,
      ),
    onSuccess: invalidate,
  })

  return { createQuestion, updateQuestion, deleteQuestion }
}
