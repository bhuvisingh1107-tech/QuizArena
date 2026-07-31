import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useParticipantSessionContext } from '@/contexts/ParticipantSessionContext'
import { participantGet, participantPost } from '@/lib/participant-api'
import type { JoinResponse, LeaveResponse } from '@/types/api'

export const participantQueryKeys = {
  me: ['participant', 'me'] as const,
}

export function useParticipantSession() {
  return useParticipantSessionContext()
}

export function useParticipantMeQuery(enabled = true) {
  const { hasSession } = useParticipantSessionContext()

  return useQuery({
    queryKey: participantQueryKeys.me,
    queryFn: () => participantGet<JoinResponse>('/participants/me'),
    enabled: enabled && hasSession,
  })
}

export function useParticipantReconnectMutation() {
  const { persistJoin } = useParticipantSessionContext()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => participantPost<JoinResponse>('/participants/reconnect'),
    onSuccess: (data) => {
      persistJoin(data)
      void queryClient.invalidateQueries({ queryKey: participantQueryKeys.me })
    },
  })
}

export function useParticipantLeaveMutation() {
  const { leave } = useParticipantSessionContext()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      await leave()
      return { left: true } as LeaveResponse
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: participantQueryKeys.me })
    },
  })
}
