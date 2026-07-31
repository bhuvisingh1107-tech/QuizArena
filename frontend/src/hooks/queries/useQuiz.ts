import { useQuery } from '@tanstack/react-query'

import { apiGet } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type { Quiz } from '@/types/api'

export function useQuiz(quizId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.quizzes.detail(quizId ?? ''),
    queryFn: () => apiGet<Quiz>(`/quizzes/${quizId}`),
    enabled: Boolean(quizId) && enabled,
  })
}
