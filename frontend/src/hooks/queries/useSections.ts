import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiDelete, apiGet, apiPatch, apiPost } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type {
  Section,
  SectionCreateInput,
  SectionList,
  SectionUpdateInput,
} from '@/types/api'

export function useSections(quizId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.sections.list(quizId ?? ''),
    queryFn: () => apiGet<SectionList>(`/quizzes/${quizId}/sections`),
    enabled: Boolean(quizId) && enabled,
  })
}

export function useSectionMutations(quizId: string) {
  const queryClient = useQueryClient()

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.sections.list(quizId) })
  }

  const createSection = useMutation({
    mutationFn: (input: SectionCreateInput) =>
      apiPost<Section>(`/quizzes/${quizId}/sections`, input),
    onSuccess: invalidate,
  })

  const updateSection = useMutation({
    mutationFn: ({
      sectionId,
      input,
    }: {
      sectionId: string
      input: SectionUpdateInput
    }) => apiPatch<Section>(`/quizzes/${quizId}/sections/${sectionId}`, input),
    onSuccess: invalidate,
  })

  const deleteSection = useMutation({
    mutationFn: (sectionId: string) =>
      apiDelete<{ id: string; deleted: boolean }>(`/quizzes/${quizId}/sections/${sectionId}`),
    onSuccess: invalidate,
  })

  return { createSection, updateSection, deleteSection }
}
