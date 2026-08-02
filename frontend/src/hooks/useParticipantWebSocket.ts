import { useCallback, useEffect, useReducer, useRef } from 'react'

import {
  computeReconnectDelay,
  getParticipantRouteForRoomState,
  initialParticipantLiveState,
  participantLiveReducer,
  type WsConnectionStatus,
} from '@/hooks/participantLiveReducer'
import { getWsBaseUrl } from '@/lib/env'
import { getSessionToken } from '@/lib/participant-session'
import {
  acquireWebSocket,
  makeWsKey,
  type WsConnectionHandle,
} from '@/lib/ws-connection'
import { wsDebug } from '@/lib/ws-debug'
import type { WsMessage } from '@/types/api'

const AUTH_FAILURE_CODES = new Set([
  'AUTH_ERROR',
  'ROOM_CLOSED',
  'FORBIDDEN',
  'UNAUTHORIZED',
  'INVALID_PARTICIPANT_TOKEN',
])

export interface UseParticipantWebSocketOptions {
  enabled?: boolean
  /** Prefer React-state token; falls back to sessionStorage. */
  sessionToken?: string | null
  onAuthFailed?: () => void
}

export function useParticipantWebSocket({
  enabled = true,
  sessionToken = null,
  onAuthFailed,
}: UseParticipantWebSocketOptions = {}) {
  const [state, dispatch] = useReducer(participantLiveReducer, initialParticipantLiveState)
  const handleRef = useRef<WsConnectionHandle | null>(null)
  const reconnectAttempt = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const intentionalClose = useRef(false)
  const authFailedRef = useRef(false)
  const submittingRef = useRef(false)
  const connectRef = useRef<(() => void) | null>(null)
  const onAuthFailedRef = useRef(onAuthFailed)
  const authFailedHandledRef = useRef(false)
  const enabledRef = useRef(enabled)
  const tokenRef = useRef(sessionToken)

  enabledRef.current = enabled
  tokenRef.current = sessionToken
  onAuthFailedRef.current = onAuthFailed

  useEffect(() => {
    submittingRef.current =
      state.submissionStatus === 'submitting' ||
      state.submissionStatus === 'submitted' ||
      state.submissionStatus === 'already_submitted'
  }, [state.submissionStatus])

  useEffect(() => {
    authFailedRef.current = state.authFailed
    if (state.authFailed && !authFailedHandledRef.current) {
      authFailedHandledRef.current = true
      intentionalClose.current = true
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      onAuthFailedRef.current?.()
    }
  }, [state.authFailed])

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }
  }, [])

  const releaseHandle = useCallback((immediate: boolean) => {
    const handle = handleRef.current
    handleRef.current = null
    handle?.release({ immediate })
  }, [])

  const handleAuthFailure = useCallback(
    (message?: string) => {
      if (authFailedRef.current) return
      authFailedRef.current = true
      authFailedHandledRef.current = true
      intentionalClose.current = true
      clearReconnectTimer()
      releaseHandle(true)
      dispatch({ type: 'AUTH_FAILED', message: message ?? 'Session expired' })
      onAuthFailedRef.current?.()
      wsDebug('participant', 'auth', { message })
    },
    [clearReconnectTimer, releaseHandle],
  )

  const send = useCallback((type: string, payload: Record<string, unknown> = {}) => {
    const handle = handleRef.current
    const message: WsMessage = {
      type,
      payload,
      timestamp: new Date().toISOString(),
    }
    if (!handle?.send(JSON.stringify(message))) {
      dispatch({ type: 'ERROR', message: 'WebSocket is not connected' })
      return false
    }
    return true
  }, [])

  const sendAnswer = useCallback(
    (optionIds: string[]) => {
      if (submittingRef.current) {
        return false
      }
      if (!optionIds.length) return false

      submittingRef.current = true
      dispatch({ type: 'SUBMIT_START', optionIds })
      const ok = send('answer:submit', { optionIds })
      if (!ok) {
        submittingRef.current = false
        dispatch({
          type: 'EVENT',
          message: {
            type: 'answer:rejected',
            payload: {
              code: 'NOT_CONNECTED',
              message: 'Not connected — try again when the connection is restored',
            },
            timestamp: new Date().toISOString(),
          },
        })
      }
      return ok
    },
    [send],
  )

  const selectOptions = useCallback((optionIds: string[]) => {
    dispatch({ type: 'SELECT_OPTIONS', optionIds })
  }, [])

  const disconnect = useCallback(() => {
    intentionalClose.current = true
    clearReconnectTimer()
    releaseHandle(true)
    dispatch({ type: 'STATUS', status: 'disconnected' satisfies WsConnectionStatus })
    wsDebug('participant', 'cleanup', { reason: 'disconnect()' })
  }, [clearReconnectTimer, releaseHandle])

  const reconnect = useCallback(() => {
    if (!enabledRef.current || authFailedRef.current) return
    intentionalClose.current = false
    reconnectAttempt.current = 0
    clearReconnectTimer()
    releaseHandle(true)
    dispatch({ type: 'CLEAR_ERROR' })
    wsDebug('participant', 'reconnect', { reason: 'manual' })
    connectRef.current?.()
  }, [clearReconnectTimer, releaseHandle])

  useEffect(() => {
    const onOnline = () => {
      dispatch({ type: 'SET_OFFLINE', offline: false })
      if (!enabledRef.current || authFailedRef.current) return
      intentionalClose.current = false
      reconnectAttempt.current = 0
      clearReconnectTimer()
      wsDebug('participant', 'reconnect', { reason: 'online' })
      connectRef.current?.()
    }
    const onOffline = () => dispatch({ type: 'SET_OFFLINE', offline: true })
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    dispatch({ type: 'SET_OFFLINE', offline: !navigator.onLine })
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [clearReconnectTimer])

  const resolvedToken = sessionToken?.trim() || null

  useEffect(() => {
    if (!enabled) {
      intentionalClose.current = true
      clearReconnectTimer()
      releaseHandle(true)
      dispatch({ type: 'RESET' })
      authFailedRef.current = false
      authFailedHandledRef.current = false
      wsDebug('participant', 'skip', { reason: 'disabled' })
      return
    }

    intentionalClose.current = false
    authFailedRef.current = false
    authFailedHandledRef.current = false

    const connect = () => {
      if (intentionalClose.current || authFailedRef.current || !enabledRef.current) {
        wsDebug('participant', 'skip', {
          reason: 'guard',
          intentionalClose: intentionalClose.current,
          authFailed: authFailedRef.current,
          enabled: enabledRef.current,
        })
        return
      }

      const token =
        (tokenRef.current && tokenRef.current.trim()) || getSessionToken()
      if (!token) {
        handleAuthFailure('Your session expired. Please join again.')
        return
      }

      // Drop prior retainer without grace so we don't keep two retainers on one key.
      releaseHandle(false)

      const base = getWsBaseUrl()
      const url = `${base}?role=participant&token=${encodeURIComponent(token)}`
      const key = makeWsKey('participant', { token })

      dispatch({ type: 'STATUS', status: 'connecting' })

      const handle = acquireWebSocket('participant', key, url, {
        onOpen: () => {
          if (handleRef.current !== handle) return
          reconnectAttempt.current = 0
          dispatch({ type: 'STATUS', status: 'connected' })
        },
        onMessage: (event, ws) => {
          if (handleRef.current !== handle) return
          try {
            const message = JSON.parse(String(event.data)) as WsMessage
            if (message.type === 'ping') {
              ws.send(
                JSON.stringify({
                  type: 'pong',
                  payload: message.payload ?? {},
                  timestamp: new Date().toISOString(),
                }),
              )
            }

            if (message.type === 'error') {
              const payload =
                message.payload && typeof message.payload === 'object'
                  ? (message.payload as Record<string, unknown>)
                  : {}
              const code = String(payload.code ?? '')
              if (AUTH_FAILURE_CODES.has(code)) {
                handleAuthFailure(String(payload.message ?? 'Authentication failed'))
                return
              }
            }

            dispatch({ type: 'EVENT', message })
          } catch {
            dispatch({ type: 'ERROR', message: 'Failed to parse WebSocket message' })
          }
        },
        onError: () => {
          if (handleRef.current !== handle) return
          dispatch({ type: 'STATUS', status: 'error' })
        },
        onClose: () => {
          if (handleRef.current !== handle) return
          handleRef.current = null
          if (intentionalClose.current || authFailedRef.current) {
            if (!authFailedRef.current) {
              dispatch({ type: 'STATUS', status: 'disconnected' })
            }
            return
          }
          dispatch({ type: 'STATUS', status: 'disconnected' })
          const attempt = reconnectAttempt.current
          const delay = computeReconnectDelay(attempt)
          reconnectAttempt.current = attempt + 1
          clearReconnectTimer()
          wsDebug('participant', 'reconnect', { attempt, delay })
          reconnectTimer.current = setTimeout(() => {
            connectRef.current?.()
          }, delay)
        },
      })

      handleRef.current = handle
    }

    connectRef.current = connect
    connect()

    return () => {
      // Soft release — StrictMode remount re-acquires within grace window.
      intentionalClose.current = true
      connectRef.current = null
      clearReconnectTimer()
      releaseHandle(false)
      wsDebug('participant', 'cleanup', { reason: 'effect-cleanup' })
    }
    // Token identity is part of the connection key; rebind when it changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handlers via refs
  }, [enabled, resolvedToken])

  // Leaving the room / disabling must hard-close after the soft cleanup above settles.
  useEffect(() => {
    if (enabled && resolvedToken) return
    const timer = window.setTimeout(() => {
      releaseHandle(true)
    }, 200)
    return () => window.clearTimeout(timer)
  }, [enabled, resolvedToken, releaseHandle])

  const suggestedRoute = getParticipantRouteForRoomState(state.room?.state)

  return {
    ...state,
    send,
    sendAnswer,
    selectOptions,
    disconnect,
    reconnect,
    clearError: () => dispatch({ type: 'CLEAR_ERROR' }),
    suggestedRoute,
  }
}
