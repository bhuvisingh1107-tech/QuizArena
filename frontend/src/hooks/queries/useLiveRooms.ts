import { useQuery } from '@tanstack/react-query'

import { apiGet } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type { PaginatedLiveRooms, RoomState } from '@/types/api'

export interface UseLiveRoomsParams {
  offset?: number
  limit?: number
  state?: RoomState
  enabled?: boolean
}

export function useLiveRooms(params: UseLiveRoomsParams = {}) {
  const { offset = 0, limit = 20, state, enabled = true } = params

  return useQuery({
    queryKey: queryKeys.liveRooms.list({ offset, limit, state }),
    queryFn: () =>
      apiGet<PaginatedLiveRooms>('/live-rooms', {
        params: {
          offset,
          limit,
          ...(state ? { state } : {}),
        },
      }),
    enabled,
  })
}
