import { useCallback, useEffect, useReducer, useRef } from 'react'

import {
  computeReconnectDelay,
  displayLiveReducer,
  initialDisplayLiveState,
  type WsConnectionStatus,
} from '@/hooks/displayLiveReducer'
import { getWsBaseUrl } from '@/lib/env'
import {
  acquireWebSocket,
  makeWsKey,
  type WsConnectionHandle,
} from '@/lib/ws-connection'
import { wsDebug } from '@/lib/ws-debug'
import type { WsMessage } from '@/types/api'

export interface UseDisplayWebSocketOptions {
  secretToken: string | undefined
  enabled?: boolean
}

export function useDisplayWebSocket({
  secretToken,
  enabled = true,
}: UseDisplayWebSocketOptions) {
  const [state, dispatch] = useReducer(displayLiveReducer, initialDisplayLiveState)
  const handleRef = useRef<WsConnectionHandle | null>(null)
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

  const releaseHandle = useCallback((immediate: boolean) => {
    const handle = handleRef.current
    handleRef.current = null
    handle?.release({ immediate })
  }, [])

  const disconnect = useCallback(() => {
    intentionalClose.current = true
    clearReconnectTimer()
    releaseHandle(true)
    dispatch({ type: 'STATUS', status: 'disconnected' satisfies WsConnectionStatus })
    wsDebug('display', 'cleanup', { reason: 'disconnect()' })
  }, [clearReconnectTimer, releaseHandle])

  const reconnect = useCallback(() => {
    if (!enabledRef.current || authFailedRef.current || !secretTokenRef.current?.trim()) {
      return
    }
    intentionalClose.current = false
    reconnectAttempt.current = 0
    clearReconnectTimer()
    releaseHandle(true)
    dispatch({ type: 'CLEAR_ERROR' })
    wsDebug('display', 'reconnect', { reason: 'manual' })
    connectRef.current?.()
  }, [clearReconnectTimer, releaseHandle])

  useEffect(() => {
    const onOnline = () => {
      if (!enabledRef.current || authFailedRef.current) return
      intentionalClose.current = false
      reconnectAttempt.current = 0
      clearReconnectTimer()
      wsDebug('display', 'reconnect', { reason: 'online' })
      connectRef.current?.()
    }
    window.addEventListener('online', onOnline)
    return () => window.removeEventListener('online', onOnline)
  }, [clearReconnectTimer])

  useEffect(() => {
    authFailedRef.current = state.authFailed
  }, [state.authFailed])

  const trimmedToken = secretToken?.trim() || ''

  useEffect(() => {
    if (!enabled) {
      intentionalClose.current = true
      clearReconnectTimer()
      releaseHandle(true)
      dispatch({ type: 'RESET' })
      wsDebug('display', 'skip', { reason: 'disabled' })
      return
    }

    if (!trimmedToken) {
      dispatch({
        type: 'AUTH_FAILED',
        message: 'Missing display token. Check the presentation link.',
      })
      wsDebug('display', 'auth', { reason: 'missing-token' })
      return
    }

    intentionalClose.current = false
    authFailedRef.current = false

    const connect = () => {
      if (intentionalClose.current || authFailedRef.current || !enabledRef.current) {
        wsDebug('display', 'skip', { reason: 'guard' })
        return
      }

      const token = secretTokenRef.current?.trim()
      if (!token) return

      releaseHandle(false)

      const base = getWsBaseUrl()
      const url = `${base}?role=display&token=${encodeURIComponent(token)}`
      const key = makeWsKey('display', { token })

      dispatch({ type: 'STATUS', status: 'connecting' })

      const handle = acquireWebSocket('display', key, url, {
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
              if (
                code === 'AUTH_ERROR' ||
                code === 'ROOM_CLOSED' ||
                code === 'FORBIDDEN' ||
                code === 'UNAUTHORIZED'
              ) {
                authFailedRef.current = true
                intentionalClose.current = true
                clearReconnectTimer()
                wsDebug('display', 'auth', { code })
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
          wsDebug('display', 'reconnect', { attempt, delay })
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
      intentionalClose.current = true
      connectRef.current = null
      clearReconnectTimer()
      releaseHandle(false)
      wsDebug('display', 'cleanup', { reason: 'effect-cleanup' })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- bind on token/enabled
  }, [enabled, trimmedToken])

  useEffect(() => {
    if (enabled && trimmedToken) return
    const timer = window.setTimeout(() => releaseHandle(true), 200)
    return () => window.clearTimeout(timer)
  }, [enabled, trimmedToken, releaseHandle])

  return {
    ...state,
    disconnect,
    reconnect,
    clearError: () => dispatch({ type: 'CLEAR_ERROR' }),
  }
}
