import { useQuery } from '@tanstack/react-query'

import { apiGet } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type { PaginatedQuizzes, QuizStatus } from '@/types/api'

export interface UseQuizzesParams {
  offset?: number
  limit?: number
  status?: QuizStatus
  search?: string
  enabled?: boolean
}

export function useQuizzes(params: UseQuizzesParams = {}) {
  const { offset = 0, limit = 20, status, search, enabled = true } = params

  return useQuery({
    queryKey: queryKeys.quizzes.list({ offset, limit, status, search }),
    queryFn: () =>
      apiGet<PaginatedQuizzes>('/quizzes', {
        params: {
          offset,
          limit,
          ...(status ? { status } : {}),
          ...(search ? { search } : {}),
        },
      }),
    enabled,
  })
}
