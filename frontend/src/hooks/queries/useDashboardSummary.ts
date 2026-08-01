import { useQuery } from '@tanstack/react-query'

import { apiGet } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type { DashboardSummary } from '@/types/api'

export function useDashboardSummary(enabled = true) {
  return useQuery({
    queryKey: queryKeys.dashboard.summary,
    queryFn: () => apiGet<DashboardSummary>('/dashboard/summary'),
    enabled,
  })
}
