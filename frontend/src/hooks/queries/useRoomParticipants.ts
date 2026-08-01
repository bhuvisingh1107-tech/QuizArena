import { useQuery } from '@tanstack/react-query'

import { apiGet } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type { AdminParticipantList } from '@/types/api'

export function useRoomParticipants(roomId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.liveRooms.participants(roomId ?? ''),
    queryFn: () => apiGet<AdminParticipantList>(`/live-rooms/${roomId}/participants`),
    enabled: Boolean(roomId) && enabled,
    refetchInterval: 15_000,
  })
}
