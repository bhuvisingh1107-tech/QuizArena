import { useCallback, useEffect, useReducer, useRef } from 'react'

import {
  computeReconnectDelay,
  getParticipantRouteForRoomState,
  initialParticipantLiveState,
  participantLiveReducer,
  type WsConnectionStatus,
} from '@/hooks/participantLiveReducer'
import { getSessionToken } from '@/lib/participant-session'
import type { WsMessage } from '@/types/api'

export interface UseParticipantWebSocketOptions {
  enabled?: boolean
}

export function useParticipantWebSocket({
  enabled = true,
}: UseParticipantWebSocketOptions = {}) {
  const [state, dispatch] = useReducer(participantLiveReducer, initialParticipantLiveState)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttempt = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const intentionalClose = useRef(false)

  const clearReconnectTimer = () => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }
  }

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
      if (
        state.submissionStatus === 'submitting' ||
        state.submissionStatus === 'submitted' ||
        state.submissionStatus === 'already_submitted'
      ) {
        return false
      }
      if (!optionIds.length) return false
      dispatch({ type: 'SUBMIT_START', optionIds })
      const ok = send('answer:submit', { optionIds })
      if (!ok) {
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
    [send, state.submissionStatus],
  )

  const selectOptions = useCallback((optionIds: string[]) => {
    dispatch({ type: 'SELECT_OPTIONS', optionIds })
  }, [])

  const disconnect = useCallback(() => {
    intentionalClose.current = true
    clearReconnectTimer()
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    dispatch({ type: 'STATUS', status: 'disconnected' satisfies WsConnectionStatus })
  }, [])

  useEffect(() => {
    const onOnline = () => dispatch({ type: 'SET_OFFLINE', offline: false })
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
      disconnect()
      dispatch({ type: 'RESET' })
      return
    }

    intentionalClose.current = false
    let cancelled = false

    const connect = () => {
      if (cancelled || intentionalClose.current) return

      const token = getSessionToken()
      if (!token) {
        dispatch({ type: 'ERROR', message: 'Missing participant session token' })
        return
      }

      const base =
        import.meta.env.VITE_WS_BASE_URL?.replace(/\/$/, '') || 'ws://localhost:8000/ws'
      const url = `${base}?role=participant&token=${encodeURIComponent(token)}`

      dispatch({ type: 'STATUS', status: 'connecting' })
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        reconnectAttempt.current = 0
        dispatch({ type: 'STATUS', status: 'connected' })
      }

      ws.onmessage = (event) => {
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
          dispatch({ type: 'EVENT', message })
        } catch {
          dispatch({ type: 'ERROR', message: 'Failed to parse WebSocket message' })
        }
      }

      ws.onerror = () => {
        dispatch({ type: 'STATUS', status: 'error' })
      }

      ws.onclose = () => {
        wsRef.current = null
        if (cancelled || intentionalClose.current) {
          dispatch({ type: 'STATUS', status: 'disconnected' })
          return
        }
        dispatch({ type: 'STATUS', status: 'disconnected' })
        const attempt = reconnectAttempt.current
        const delay = computeReconnectDelay(attempt)
        reconnectAttempt.current = attempt + 1
        clearReconnectTimer()
        reconnectTimer.current = setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      cancelled = true
      intentionalClose.current = true
      clearReconnectTimer()
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [enabled, disconnect])

  const suggestedRoute = getParticipantRouteForRoomState(state.room?.state)

  return {
    ...state,
    send,
    sendAnswer,
    selectOptions,
    disconnect,
    clearError: () => dispatch({ type: 'CLEAR_ERROR' }),
    suggestedRoute,
  }
}
