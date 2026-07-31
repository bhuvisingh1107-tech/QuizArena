import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiDelete, apiGet, apiPatch, apiPost } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type {
  AnswerOption,
  AnswerOptionCreateInput,
  AnswerOptionList,
  AnswerOptionUpdateInput,
} from '@/types/api'

function optionsPath(quizId: string, sectionId: string, questionId: string) {
  return `/quizzes/${quizId}/sections/${sectionId}/questions/${questionId}/options`
}

export function useOptions(
  quizId: string | undefined,
  sectionId: string | undefined,
  questionId: string | undefined,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.options.list(quizId ?? '', sectionId ?? '', questionId ?? ''),
    queryFn: () =>
      apiGet<AnswerOptionList>(optionsPath(quizId!, sectionId!, questionId!)),
    enabled: Boolean(quizId && sectionId && questionId) && enabled,
  })
}

export function useOptionMutations(quizId: string, sectionId: string, questionId: string) {
  const queryClient = useQueryClient()
  const base = optionsPath(quizId, sectionId, questionId)

  const invalidate = async () => {
    await queryClient.invalidateQueries({
      queryKey: queryKeys.options.list(quizId, sectionId, questionId),
    })
  }

  const createOption = useMutation({
    mutationFn: (input: AnswerOptionCreateInput) => apiPost<AnswerOption>(base, input),
    onSuccess: invalidate,
  })

  const updateOption = useMutation({
    mutationFn: ({
      optionId,
      input,
    }: {
      optionId: string
      input: AnswerOptionUpdateInput
    }) => apiPatch<AnswerOption>(`${base}/${optionId}`, input),
    onSuccess: invalidate,
  })

  const deleteOption = useMutation({
    mutationFn: (optionId: string) =>
      apiDelete<{ id: string; deleted: boolean }>(`${base}/${optionId}`),
    onSuccess: invalidate,
  })

  return { createOption, updateOption, deleteOption }
}
