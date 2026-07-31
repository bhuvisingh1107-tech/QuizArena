import { useMutation } from '@tanstack/react-query'

import { useParticipantSessionContext } from '@/contexts/ParticipantSessionContext'
import { participantPost } from '@/lib/participant-api'
import type { JoinRequest, JoinResponse } from '@/types/api'

export function useJoinMutation() {
  const { persistJoin } = useParticipantSessionContext()

  return useMutation({
    mutationFn: (body: JoinRequest) => participantPost<JoinResponse>('/join', body),
    onSuccess: (data) => {
      persistJoin(data)
    },
  })
}
