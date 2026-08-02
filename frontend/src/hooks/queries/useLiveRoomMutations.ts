import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiDelete, apiPatch, apiPost } from '@/lib/api-client'
import { syncLiveRoomCaches } from '@/lib/live-room-cache'
import { queryKeys } from '@/hooks/queries/keys'
import type {
  LiveRoom,
  LiveRoomCreateInput,
  LiveRoomDeleteResult,
  RoomConfigInput,
} from '@/types/api'

export function useLiveRoomMutations() {
  const queryClient = useQueryClient()

  const afterRoomChange = async (room: LiveRoom) => {
    await syncLiveRoomCaches(queryClient, room)
  }

  const createRoom = useMutation({
    mutationFn: (input: LiveRoomCreateInput) => apiPost<LiveRoom>('/live-rooms', input),
    onSuccess: async (room) => {
      await afterRoomChange(room)
    },
  })

  const updateConfig = useMutation({
    mutationFn: ({ roomId, config }: { roomId: string; config: RoomConfigInput }) =>
      apiPatch<LiveRoom>(`/live-rooms/${roomId}/config`, config),
    onSuccess: async (room) => {
      await afterRoomChange(room)
    },
  })

  const openLobby = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/open-lobby`),
    onSuccess: async (room) => {
      await afterRoomChange(room)
    },
  })

  const toggleLobby = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/toggle-lobby`),
    onSuccess: async (room) => {
      await afterRoomChange(room)
    },
  })

  const startSession = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/start`),
    onSuccess: async (room) => {
      await afterRoomChange(room)
    },
  })

  const pauseSession = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/pause`),
    onSuccess: async (room) => {
      await afterRoomChange(room)
    },
  })

  const resumeSession = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/resume`),
    onSuccess: async (room) => {
      await afterRoomChange(room)
    },
  })

  const endSession = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/end`),
    onSuccess: async (room) => {
      await afterRoomChange(room)
    },
  })

  const closeRoom = useMutation({
    mutationFn: (roomId: string) => apiPost<LiveRoom>(`/live-rooms/${roomId}/close`),
    onSuccess: async (room) => {
      await afterRoomChange(room)
    },
  })

  const deleteRoom = useMutation({
    mutationFn: (roomId: string) =>
      apiDelete<LiveRoomDeleteResult>(`/live-rooms/${roomId}`),
    onSuccess: async (result) => {
      await syncLiveRoomCaches(
        queryClient,
        { id: result.id } as LiveRoom,
        { removed: true },
      )
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary })
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
