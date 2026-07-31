import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiDelete, apiPatch, apiPost } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type {
  LiveRoom,
  LiveRoomCreateInput,
  LiveRoomDeleteResult,
  RoomConfigInput,
} from '@/types/api'

export function useLiveRoomMutations() {
  const queryClient = useQueryClient()

  const invalidate = async (roomId?: string) => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.liveRooms.all })
    if (roomId) {
      await queryClient.invalidateQueries({ queryKey: queryKeys.liveRooms.detail(roomId) })
    }
  }

  const createRoom = useMutation({
    mutationFn: (input: LiveRoomCreateInput) => apiPost<LiveRoom>('/live-rooms', input),
    onSuccess: async () => {
      await invalidate()
    },
  })

  const updateConfig = useMutation({
    mutationFn: ({ roomId, config }: { roomId: string; config: RoomConfigInput }) =>
      apiPatch<LiveRoom>(`/live-rooms/${roomId}/config`, config),
    onSuccess: async (room) => {
      await invalidate(room.id)
    },
  })

  const openLobby = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/open-lobby`),
    onSuccess: async (room) => {
      await invalidate(room.id)
    },
  })

  const toggleLobby = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/toggle-lobby`),
    onSuccess: async (room) => {
      await invalidate(room.id)
    },
  })

  const startSession = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/start`),
    onSuccess: async (room) => {
      await invalidate(room.id)
    },
  })

  const pauseSession = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/pause`),
    onSuccess: async (room) => {
      await invalidate(room.id)
    },
  })

  const resumeSession = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/resume`),
    onSuccess: async (room) => {
      await invalidate(room.id)
    },
  })

  const endSession = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/end`),
    onSuccess: async (room) => {
      await invalidate(room.id)
    },
  })

  const closeRoom = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/close`),
    onSuccess: async (room) => {
      await invalidate(room.id)
    },
  })

  const deleteRoom = useMutation({
    mutationFn: (roomId: string) =>
      apiDelete<LiveRoomDeleteResult>(`/live-rooms/${roomId}`),
    onSuccess: async (result) => {
      await invalidate(result.id)
    },
  })

  return {
    createRoom,
    updateConfig,
    openLobby,
    toggleLobby,
    startSession,
    pauseSession,
    resumeSession,
    endSession,
    closeRoom,
    deleteRoom,
  }
}
