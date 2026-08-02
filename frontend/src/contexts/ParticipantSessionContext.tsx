import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { participantGet, participantPost, ApiError } from '@/lib/participant-api'
import {
  clearParticipantSession,
  getParticipantSession,
  setParticipantSession,
  type ParticipantSession,
} from '@/lib/participant-session'
import type { JoinRequest, JoinResponse } from '@/types/api'

interface ParticipantSessionContextValue {
  session: ParticipantSession | null
  isLoading: boolean
  hasSession: boolean
  persistJoin: (response: JoinResponse) => void
  clearSession: () => void
  refreshSession: () => Promise<JoinResponse | null>
  leave: () => Promise<void>
}

const ParticipantSessionContext = createContext<ParticipantSessionContextValue | null>(
  null,
)

function sessionFromJoin(response: JoinResponse): ParticipantSession {
  return {
    sessionToken: response.sessionToken,
    roomCode: response.room.roomCode,
    roomId: response.room.id,
    displayName: response.participant.displayName,
    email: response.participant.email,
    quizTitle: response.room.quizTitle,
    participantId: response.participant.id,
  }
}

export function ParticipantSessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<ParticipantSession | null>(() =>
    getParticipantSession(),
  )
  const [isLoading, setIsLoading] = useState(() => Boolean(getParticipantSession()))

  const persistJoin = useCallback((response: JoinResponse) => {
    const next = sessionFromJoin(response)
    setParticipantSession(next)
    setSession(next)
  }, [])

  const clearSession = useCallback(() => {
    clearParticipantSession()
    setSession(null)
  }, [])

  const refreshSession = useCallback(async () => {
    const token = getParticipantSession()?.sessionToken
    if (!token) {
      setSession(null)
      return null
    }
    try {
      const me = await participantGet<JoinResponse>('/participants/me')
      const next = sessionFromJoin(me)
      setParticipantSession(next)
      setSession(next)
      return me
    } catch (error) {
      // Only wipe the session on hard auth failures. Transient network errors
      // must not disconnect an already-joined participant mid-navigation.
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        clearParticipantSession()
        setSession(null)
      }
      return null
    }
  }, [])

  const leave = useCallback(async () => {
    try {
      if (getParticipantSession()?.sessionToken) {
        await participantPost<{ id: string; left: boolean }>('/participants/leave')
      }
    } catch {
      // Always clear local session
    } finally {
      clearParticipantSession()
      setSession(null)
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function restore() {
      const existing = getParticipantSession()
      if (!existing) {
        if (!cancelled) {
          setSession(null)
          setIsLoading(false)
        }
        return
      }

      try {
        const restored = await participantPost<JoinResponse>('/participants/reconnect')
        if (cancelled) return
        const next = sessionFromJoin(restored)
        setParticipantSession(next)
        setSession(next)
      } catch {
        // Fall back to /me; only clear on confirmed auth failure.
        try {
          const me = await participantGet<JoinResponse>('/participants/me')
          if (cancelled) return
          const next = sessionFromJoin(me)
          setParticipantSession(next)
          setSession(next)
        } catch (error) {
          if (cancelled) return
          if (
            error instanceof ApiError &&
            (error.status === 401 || error.status === 403 || error.status === 404)
          ) {
            clearParticipantSession()
            setSession(null)
          }
          // Keep stored session on transient errors so WS can still connect.
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void restore()
    return () => {
      cancelled = true
    }
  }, [])

  // Keep React session in sync when the axios interceptor clears storage (401).
  useEffect(() => {
    const onCleared = () => {
      setSession(null)
    }
    window.addEventListener('qa:participant-session-cleared', onCleared)
    return () => window.removeEventListener('qa:participant-session-cleared', onCleared)
  }, [])

  const value = useMemo<ParticipantSessionContextValue>(
    () => ({
      session,
      isLoading,
      hasSession: Boolean(session?.sessionToken),
      persistJoin,
      clearSession,
      refreshSession,
      leave,
    }),
    [session, isLoading, persistJoin, clearSession, refreshSession, leave],
  )

  return (
    <ParticipantSessionContext.Provider value={value}>
      {children}
    </ParticipantSessionContext.Provider>
  )
}

export function useParticipantSessionContext(): ParticipantSessionContextValue {
  const ctx = useContext(ParticipantSessionContext)
  if (!ctx) {
    throw new Error(
      'useParticipantSessionContext must be used within ParticipantSessionProvider',
    )
  }
  return ctx
}

export type { JoinRequest }
