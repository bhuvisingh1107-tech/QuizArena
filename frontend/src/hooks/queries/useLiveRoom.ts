import { useQuery } from '@tanstack/react-query'

import { apiGet } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type { LiveRoom } from '@/types/api'

export function useLiveRoom(roomId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.liveRooms.detail(roomId ?? ''),
    queryFn: () => apiGet<LiveRoom>(`/live-rooms/${roomId}`),
    enabled: Boolean(roomId) && enabled,
  })
}
