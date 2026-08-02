import type { QueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/hooks/queries/keys'
import type { LiveRoom } from '@/types/api'

/** Patch every React Query cache that depends on a live room snapshot. */
export async function syncLiveRoomCaches(
  queryClient: QueryClient,
  room: LiveRoom,
  options?: { removed?: boolean },
): Promise<void> {
  if (options?.removed) {
    queryClient.removeQueries({ queryKey: queryKeys.liveRooms.detail(room.id) })
  } else {
    queryClient.setQueryData(queryKeys.liveRooms.detail(room.id), room)
  }

  queryClient.setQueriesData(
    { queryKey: queryKeys.liveRooms.all },
    (existing: unknown) => {
      if (!existing || typeof existing !== 'object') return existing
      const data = existing as { items?: LiveRoom[]; total?: number }
      if (!Array.isArray(data.items)) return existing
      if (options?.removed) {
        const items = data.items.filter((item) => item.id !== room.id)
        return { ...data, items, total: Math.max(0, (data.total ?? items.length) - 0) }
      }
      const index = data.items.findIndex((item) => item.id === room.id)
      if (index === -1) {
        return { ...data, items: [room, ...data.items], total: (data.total ?? data.items.length) + 1 }
      }
      const items = [...data.items]
      items[index] = { ...items[index], ...room }
      return { ...data, items }
    },
  )

  await Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.liveRooms.all }),
    queryClient.invalidateQueries({ queryKey: queryKeys.liveRooms.detail(room.id) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.liveRooms.participants(room.id) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.liveRooms.results(room.id) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary }),
  ])
}
