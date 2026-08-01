import { createContext, useContext, type ReactNode } from 'react'

import { useParticipantSessionContext } from '@/contexts/ParticipantSessionContext'
import { useParticipantWebSocket } from '@/hooks/useParticipantWebSocket'

type ParticipantLiveValue = ReturnType<typeof useParticipantWebSocket>

const ParticipantLiveContext = createContext<ParticipantLiveValue | null>(null)

export function ParticipantLiveProvider({ children }: { children: ReactNode }) {
  const { hasSession, clearSession } = useParticipantSessionContext()
  const live = useParticipantWebSocket({
    enabled: hasSession,
    onAuthFailed: clearSession,
  })

  return (
    <ParticipantLiveContext.Provider value={live}>{children}</ParticipantLiveContext.Provider>
  )
}

export function useParticipantLive(): ParticipantLiveValue {
  const ctx = useContext(ParticipantLiveContext)
  if (!ctx) {
    throw new Error('useParticipantLive must be used within ParticipantLiveProvider')
  }
  return ctx
}
