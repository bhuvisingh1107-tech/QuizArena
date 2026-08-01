import { useCallback, useEffect, useReducer, useRef } from 'react'

import {
  computeReconnectDelay,
  displayLiveReducer,
  initialDisplayLiveState,
  type WsConnectionStatus,
} from '@/hooks/displayLiveReducer'
import { getWsBaseUrl } from '@/lib/env'
import type { WsMessage } from '@/types/api'

export interface UseDisplayWebSocketOptions {
  secretToken: string | undefined
  enabled?: boolean
}

function detachSocket(ws: WebSocket | null) {
  if (!ws) return
  ws.onopen = null
  ws.onmessage = null
  ws.onerror = null
  ws.onclose = null
}

export function useDisplayWebSocket({
  secretToken,
  enabled = true,
}: UseDisplayWebSocketOptions) {
  const [state, dispatch] = useReducer(displayLiveReducer, initialDisplayLiveState)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttempt = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const intentionalClose = useRef(false)
  const authFailedRef = useRef(false)
  const connectRef = useRef<(() => void) | null>(null)
  const enabledRef = useRef(enabled)
  const secretTokenRef = useRef(secretToken)

  enabledRef.current = enabled
  secretTokenRef.current = secretToken

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }
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
    if (!enabledRef.current || authFailedRef.current || !secretTokenRef.current?.trim()) return
    intentionalClose.current = false
    reconnectAttempt.current = 0
    clearReconnectTimer()
    dispatch({ type: 'CLEAR_ERROR' })
    connectRef.current?.()
  }, [clearReconnectTimer])

  useEffect(() => {
    const onOnline = () => {
      if (!enabledRef.current || authFailedRef.current) return
      intentionalClose.current = false
      reconnectAttempt.current = 0
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      connectRef.current?.()
    }
    window.addEventListener('online', onOnline)
    return () => window.removeEventListener('online', onOnline)
  }, [])

  useEffect(() => {
    authFailedRef.current = state.authFailed
  }, [state.authFailed])

  useEffect(() => {
    if (!enabled) {
      disconnect()
      dispatch({ type: 'RESET' })
      return
    }

    if (!secretToken?.trim()) {
      dispatch({
        type: 'AUTH_FAILED',
        message: 'Missing display token. Check the presentation link.',
      })
      return
    }

    intentionalClose.current = false
    authFailedRef.current = false
    const token = secretToken.trim()

    const connect = () => {
      if (intentionalClose.current || authFailedRef.current || !enabledRef.current) return

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
      const url = `${base}?role=display&token=${encodeURIComponent(token)}`

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
            if (
              code === 'AUTH_ERROR' ||
              code === 'ROOM_CLOSED' ||
              code === 'FORBIDDEN' ||
              code === 'UNAUTHORIZED'
            ) {
              authFailedRef.current = true
              intentionalClose.current = true
              clearReconnectTimer()
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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- bind only on token/enabled
  }, [enabled, secretToken])

  return {
    ...state,
    disconnect,
    reconnect,
    clearError: () => dispatch({ type: 'CLEAR_ERROR' }),
  }
}
