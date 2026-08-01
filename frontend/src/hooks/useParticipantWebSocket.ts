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
  onAuthFailed?: () => void
}

function detachSocket(ws: WebSocket | null) {
  if (!ws) return
  ws.onopen = null
  ws.onmessage = null
  ws.onerror = null
  ws.onclose = null
}

export function useParticipantWebSocket({
  enabled = true,
  onAuthFailed,
}: UseParticipantWebSocketOptions = {}) {
  const [state, dispatch] = useReducer(participantLiveReducer, initialParticipantLiveState)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttempt = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const intentionalClose = useRef(false)
  const authFailedRef = useRef(false)
  const submittingRef = useRef(false)
  const connectRef = useRef<(() => void) | null>(null)
  const onAuthFailedRef = useRef(onAuthFailed)
  const authFailedHandledRef = useRef(false)
  const enabledRef = useRef(enabled)

  enabledRef.current = enabled

  useEffect(() => {
    onAuthFailedRef.current = onAuthFailed
  }, [onAuthFailed])

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

  const handleAuthFailure = useCallback(
    (message?: string) => {
      if (authFailedRef.current) return
      authFailedRef.current = true
      authFailedHandledRef.current = true
      intentionalClose.current = true
      clearReconnectTimer()
      const ws = wsRef.current
      if (ws) {
        detachSocket(ws)
        try {
          ws.close()
        } catch {
          // ignore
        }
        wsRef.current = null
      }
      dispatch({ type: 'AUTH_FAILED', message: message ?? 'Session expired' })
      onAuthFailedRef.current?.()
    },
    [clearReconnectTimer],
  )

  const send = useCallback((type: string, payload: Record<string, unknown> = {}) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      dispatch({ type: 'ERROR', message: 'WebSocket is not connected' })
      return false
    }
    const message: WsMessage = {
      type,
      payload,
      timestamp: new Date().toISOString(),
    }
    ws.send(JSON.stringify(message))
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
    const ws = wsRef.current
    if (ws) {
      detachSocket(ws)
      try {
        ws.close()
      } catch {
        // ignore
      }
      wsRef.current = null
    }
    dispatch({ type: 'STATUS', status: 'disconnected' satisfies WsConnectionStatus })
  }, [clearReconnectTimer])

  const reconnect = useCallback(() => {
    if (!enabledRef.current || authFailedRef.current) return
    intentionalClose.current = false
    reconnectAttempt.current = 0
    clearReconnectTimer()
    dispatch({ type: 'CLEAR_ERROR' })
    connectRef.current?.()
  }, [clearReconnectTimer])

  useEffect(() => {
    const onOnline = () => {
      dispatch({ type: 'SET_OFFLINE', offline: false })
      if (!enabledRef.current || authFailedRef.current) return
      intentionalClose.current = false
      reconnectAttempt.current = 0
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
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
  }, [])

  useEffect(() => {
    if (!enabled) {
      intentionalClose.current = true
      clearReconnectTimer()
      const existing = wsRef.current
      if (existing) {
        detachSocket(existing)
        try {
          existing.close()
        } catch {
          // ignore
        }
        wsRef.current = null
      }
      dispatch({ type: 'RESET' })
      authFailedRef.current = false
      authFailedHandledRef.current = false
      return
    }

    intentionalClose.current = false
    authFailedRef.current = false
    authFailedHandledRef.current = false

    const connect = () => {
      if (intentionalClose.current || authFailedRef.current || !enabledRef.current) return

      const token = getSessionToken()
      if (!token) {
        handleAuthFailure('Your session expired. Please join again.')
        return
      }

      const previous = wsRef.current
      if (previous) {
        detachSocket(previous)
        try {
          previous.close()
        } catch {
          // ignore
        }
        wsRef.current = null
      }

      const base = getWsBaseUrl()
      const url = `${base}?role=participant&token=${encodeURIComponent(token)}`

      dispatch({ type: 'STATUS', status: 'connecting' })
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (wsRef.current !== ws) return
        reconnectAttempt.current = 0
        dispatch({ type: 'STATUS', status: 'connected' })
      }

      ws.onmessage = (event) => {
        if (wsRef.current !== ws) return
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
      }

      ws.onerror = () => {
        if (wsRef.current !== ws) return
        dispatch({ type: 'STATUS', status: 'error' })
      }

      ws.onclose = () => {
        if (wsRef.current !== ws) return
        wsRef.current = null
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
        reconnectTimer.current = setTimeout(() => {
          connectRef.current?.()
        }, delay)
      }
    }

    connectRef.current = connect
    connect()

    return () => {
      intentionalClose.current = true
      connectRef.current = null
      clearReconnectTimer()
      const ws = wsRef.current
      if (ws) {
        detachSocket(ws)
        try {
          ws.close()
        } catch {
          // ignore
        }
        wsRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- bind only on enabled; handlers via refs
  }, [enabled])

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
