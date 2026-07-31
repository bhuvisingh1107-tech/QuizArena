import { useCallback, useEffect, useReducer, useRef } from 'react'

import { getToken } from '@/lib/auth-token'
import type {
  LeaderboardEntry,
  LiveParticipant,
  LiveQuestionSnapshot,
  LiveRoom,
  Podium,
  WsMessage,
} from '@/types/api'

export type WsConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export interface AdminLiveState {
  connectionStatus: WsConnectionStatus
  room: LiveRoom | null
  participants: Record<string, LiveParticipant>
  currentQuestion: LiveQuestionSnapshot | null
  submissionCount: number
  leaderboard: LeaderboardEntry[]
  podium: Podium | null
  lastError: string | null
}

type LiveAction =
  | { type: 'STATUS'; status: WsConnectionStatus }
  | { type: 'ERROR'; message: string }
  | { type: 'CLEAR_ERROR' }
  | { type: 'RESET' }
  | { type: 'EVENT'; message: WsMessage }

const initialState: AdminLiveState = {
  connectionStatus: 'disconnected',
  room: null,
  participants: {},
  currentQuestion: null,
  submissionCount: 0,
  leaderboard: [],
  podium: null,
  lastError: null,
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function mapParticipant(raw: Record<string, unknown>): LiveParticipant | null {
  const id = String(raw.id ?? raw.participantId ?? '')
  if (!id) return null
  const connectionStatus = raw.connectionStatus
  const connected =
    typeof raw.connected === 'boolean'
      ? raw.connected
      : typeof connectionStatus === 'string'
        ? connectionStatus === 'connected'
        : undefined
  const score =
    typeof raw.totalScore === 'number'
      ? raw.totalScore
      : typeof raw.score === 'number'
        ? raw.score
        : undefined
  return {
    id,
    displayName: String(raw.displayName ?? raw.name ?? 'Participant'),
    email: (raw.email as string | null | undefined) ?? null,
    state: (raw.state as LiveParticipant['state']) ?? 'InLobby',
    score,
    connected,
  }
}

function mergeRoom(existing: LiveRoom | null, patch: Record<string, unknown>): LiveRoom | null {
  if (!existing && !(patch.id || patch.roomId)) return existing
  const base = existing ?? (patch as unknown as LiveRoom)
  const id = String(patch.id ?? patch.roomId ?? base.id)
  return {
    ...base,
    ...patch,
    id,
    roomCode: String(patch.roomCode ?? base.roomCode ?? ''),
    state: (patch.state as LiveRoom['state']) ?? base.state,
    lobbySubState:
      (patch.lobbySubState as LiveRoom['lobbySubState']) ?? base.lobbySubState ?? null,
    currentQuestionIndex:
      typeof patch.currentQuestionIndex === 'number'
        ? patch.currentQuestionIndex
        : (base.currentQuestionIndex ?? null),
    quizTitleSnapshot: String(
      patch.quizTitleSnapshot ?? patch.quizTitle ?? base.quizTitleSnapshot ?? '',
    ),
  } as LiveRoom
}

function liveReducer(state: AdminLiveState, action: LiveAction): AdminLiveState {
  switch (action.type) {
    case 'STATUS':
      return { ...state, connectionStatus: action.status }
    case 'ERROR':
      return { ...state, lastError: action.message, connectionStatus: 'error' }
    case 'CLEAR_ERROR':
      return { ...state, lastError: null }
    case 'RESET':
      return { ...initialState }
    case 'EVENT': {
      const { type, payload } = action.message
      const data = asRecord(payload)

      switch (type) {
        case 'connection:ack':
          return { ...state, connectionStatus: 'connected', lastError: null }

        case 'resync': {
          const room = data.room ? mergeRoom(state.room, asRecord(data.room)) : state.room
          const participantsList = Array.isArray(data.participants)
            ? data.participants
            : Array.isArray(asRecord(data.room).participants)
              ? (asRecord(data.room).participants as unknown[])
              : []
          const participants: Record<string, LiveParticipant> = {}
          for (const item of participantsList) {
            const mapped = mapParticipant(asRecord(item))
            if (mapped) participants[mapped.id] = mapped
          }
          const question = data.question
            ? (asRecord(data.question) as unknown as LiveQuestionSnapshot)
            : null
          const leaderboard = Array.isArray(data.leaderboard)
            ? (data.leaderboard as LeaderboardEntry[])
            : state.leaderboard
          const submission =
            typeof asRecord(data.submission).count === 'number'
              ? (asRecord(data.submission).count as number)
              : state.submissionCount

          return {
            ...state,
            connectionStatus: 'connected',
            room,
            participants: Object.keys(participants).length ? participants : state.participants,
            currentQuestion: question,
            leaderboard,
            submissionCount: submission,
            lastError: null,
          }
        }

        case 'room:state_changed':
        case 'room:lobbyOpened':
        case 'room:lobbyClosed':
        case 'room:sessionStarted':
        case 'room:paused':
        case 'room:resumed':
        case 'room:closed':
          return {
            ...state,
            room: mergeRoom(state.room, data.room ? asRecord(data.room) : data),
          }

        case 'room:completed':
        case 'quiz:completed': {
          const podiumPayload = data.podium ?? data
          const entries = Array.isArray(asRecord(podiumPayload).entries)
            ? (asRecord(podiumPayload).entries as Podium['entries'])
            : Array.isArray(data.entries)
              ? (data.entries as Podium['entries'])
              : []
          return {
            ...state,
            room: mergeRoom(state.room, data.room ? asRecord(data.room) : data),
            podium: entries.length ? { entries } : state.podium,
          }
        }

        case 'participant:joined':
        case 'participant:reconnected': {
          const participant = mapParticipant(
            asRecord(data.participant ?? data),
          )
          if (!participant) return state
          return {
            ...state,
            participants: { ...state.participants, [participant.id]: participant },
          }
        }

        case 'participant:left':
        case 'participant:disconnected': {
          const id = String(
            asRecord(data.participant).id ?? data.participantId ?? data.id ?? '',
          )
          if (!id || !state.participants[id]) return state
          const next = { ...state.participants }
          next[id] = {
            ...next[id],
            connected: false,
            state: type === 'participant:left' ? 'SessionEnded' : 'Disconnected',
          }
          return { ...state, participants: next }
        }

        case 'question:started': {
          const q = asRecord(data.question ?? data)
          const index =
            typeof data.questionIndex === 'number'
              ? data.questionIndex
              : typeof q.questionIndex === 'number'
                ? q.questionIndex
                : typeof q.index === 'number'
                  ? q.index
                  : 0
          return {
            ...state,
            currentQuestion: {
              ...(q as unknown as LiveQuestionSnapshot),
              id: String(q.id ?? ''),
              index,
              state: (q.state as LiveQuestionSnapshot['state']) ?? 'Open',
              promptText: (q.promptText as string | null | undefined) ?? null,
            },
            submissionCount: 0,
            room: mergeRoom(state.room, {
              currentQuestionIndex: index,
            }),
          }
        }

        case 'question:closed':
        case 'question:reveal':
        case 'question:scored': {
          const q = data.question ? asRecord(data.question) : null
          return {
            ...state,
            currentQuestion: q
              ? {
                  ...(q as unknown as LiveQuestionSnapshot),
                  id: String(q.id ?? state.currentQuestion?.id ?? ''),
                  index:
                    typeof data.questionIndex === 'number'
                      ? data.questionIndex
                      : (state.currentQuestion?.index ?? 0),
                  state: (q.state as LiveQuestionSnapshot['state']) ??
                    (type === 'question:closed'
                      ? 'Closed'
                      : type === 'question:reveal'
                        ? 'Revealed'
                        : 'Scored'),
                }
              : state.currentQuestion
                ? {
                    ...state.currentQuestion,
                    state:
                      type === 'question:closed'
                        ? 'Closed'
                        : type === 'question:reveal'
                          ? 'Revealed'
                          : 'Scored',
                  }
                : null,
          }
        }

        case 'answer:submission_count':
        case 'answer:received':
          return {
            ...state,
            submissionCount:
              typeof data.submittedCount === 'number'
                ? data.submittedCount
                : typeof data.count === 'number'
                  ? data.count
                  : typeof data.submissionCount === 'number'
                    ? data.submissionCount
                    : state.submissionCount,
          }

        case 'leaderboard:updated':
          return {
            ...state,
            leaderboard: Array.isArray(data.entries)
              ? (data.entries as LeaderboardEntry[])
              : Array.isArray(data.leaderboard)
                ? (data.leaderboard as LeaderboardEntry[])
                : state.leaderboard,
          }

        case 'error':
          return {
            ...state,
            lastError: String(data.message ?? 'WebSocket error'),
          }

        case 'ping':
        case 'pong':
          return state

        default:
          if (data.room) {
            return { ...state, room: mergeRoom(state.room, asRecord(data.room)) }
          }
          return state
      }
    }
    default:
      return state
  }
}

export interface UseAdminWebSocketOptions {
  roomId: string | undefined
  enabled?: boolean
}

export function useAdminWebSocket({ roomId, enabled = true }: UseAdminWebSocketOptions) {
  const [state, dispatch] = useReducer(liveReducer, initialState)
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

  const disconnect = useCallback(() => {
    intentionalClose.current = true
    clearReconnectTimer()
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    dispatch({ type: 'STATUS', status: 'disconnected' })
  }, [])

  useEffect(() => {
    if (!enabled || !roomId) {
      disconnect()
      dispatch({ type: 'RESET' })
      return
    }

    intentionalClose.current = false
    let cancelled = false

    const connect = () => {
      if (cancelled || intentionalClose.current) return

      const token = getToken()
      if (!token) {
        dispatch({ type: 'ERROR', message: 'Missing auth token for WebSocket' })
        return
      }

      const base =
        import.meta.env.VITE_WS_BASE_URL?.replace(/\/$/, '') || 'ws://localhost:8000/ws'
      const url = `${base}?role=admin&token=${encodeURIComponent(token)}&roomId=${encodeURIComponent(roomId)}`

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
        const delay = Math.min(30_000, 1000 * 2 ** attempt)
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
  }, [roomId, enabled, disconnect])

  return {
    ...state,
    send,
    disconnect,
    clearError: () => dispatch({ type: 'CLEAR_ERROR' }),
  }
}
