import { createContext, useCallback, useContext, useRef, type ReactNode } from 'react'

import { useParticipantSessionContext } from '@/contexts/ParticipantSessionContext'
import { useParticipantWebSocket } from '@/hooks/useParticipantWebSocket'

type ParticipantLiveValue = ReturnType<typeof useParticipantWebSocket>

const ParticipantLiveContext = createContext<ParticipantLiveValue | null>(null)

export function ParticipantLiveProvider({ children }: { children: ReactNode }) {
  const { hasSession, clearSession } = useParticipantSessionContext()
  // Keep a stable callback identity so the WS hook never treats auth cleanup as a
  // reason to rebind its connection effect.
  const clearSessionRef = useRef(clearSession)
  clearSessionRef.current = clearSession
  const onAuthFailed = useCallback(() => {
    clearSessionRef.current()
  }, [])

  const live = useParticipantWebSocket({
    enabled: hasSession,
    onAuthFailed,
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
