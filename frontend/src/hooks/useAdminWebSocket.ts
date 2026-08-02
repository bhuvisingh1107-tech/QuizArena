import { useCallback, useEffect, useReducer, useRef } from 'react'

import { getToken } from '@/lib/auth-token'
import { getWsBaseUrl } from '@/lib/env'
import {
  acquireWebSocket,
  makeWsKey,
  type WsConnectionHandle,
} from '@/lib/ws-connection'
import { wsDebug } from '@/lib/ws-debug'
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
  participantCount: number
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
  | { type: 'APPLY_ROOM'; room: LiveRoom }
  | { type: 'EVENT'; message: WsMessage }

const initialState: AdminLiveState = {
  connectionStatus: 'disconnected',
  room: null,
  participants: {},
  participantCount: 0,
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

function parseLeaderboard(data: Record<string, unknown>): LeaderboardEntry[] | null {
  if (Array.isArray(data.entries)) return data.entries as LeaderboardEntry[]
  if (Array.isArray(data.leaderboard)) return data.leaderboard as LeaderboardEntry[]
  return null
}

function parsePodiumEntries(data: Record<string, unknown>): Podium['entries'] | null {
  const podiumPayload = data.podium ? asRecord(data.podium) : data
  if (Array.isArray(podiumPayload.entries)) return podiumPayload.entries as Podium['entries']
  if (Array.isArray(data.entries)) return data.entries as Podium['entries']
  return null
}

function applyTimerEndsAt(
  question: LiveQuestionSnapshot | null,
  data: Record<string, unknown>,
): LiveQuestionSnapshot | null {
  if (!question) return question
  const timerEndsAt =
    (data.timerEndsAt as string | undefined) ??
    (asRecord(data.room).timerEndsAt as string | undefined)
  if (typeof timerEndsAt !== 'string') return question
  return { ...question, timerEndsAt }
}

function liveReducer(state: AdminLiveState, action: LiveAction): AdminLiveState {
  switch (action.type) {
    case 'STATUS':
      if (state.connectionStatus === action.status) return state
      return { ...state, connectionStatus: action.status }
    case 'ERROR':
      return { ...state, lastError: action.message, connectionStatus: 'error' }
    case 'CLEAR_ERROR':
      return { ...state, lastError: null }
    case 'RESET':
      return { ...initialState }
    case 'APPLY_ROOM': {
      // REST mutation success — never regress behind a more advanced live state.
      if (!state.room) {
        return { ...state, room: action.room }
      }
      const rank: Record<string, number> = {
        Setup: 0,
        Lobby: 1,
        Active: 2,
        Paused: 2,
        SectionBreak: 2,
        Completed: 3,
        Closed: 4,
      }
      const existingRank = rank[state.room.state] ?? 0
      const incomingRank = rank[action.room.state] ?? 0
      if (incomingRank < existingRank) return state
      return {
        ...state,
        room: { ...state.room, ...action.room },
      }
    }
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
          const questionRaw = data.question ? asRecord(data.question) : null
          const nestedQ = questionRaw?.question
            ? asRecord(questionRaw.question)
            : questionRaw
          const question = nestedQ
            ? ({
                ...(nestedQ as unknown as LiveQuestionSnapshot),
                id: String(nestedQ.id ?? ''),
                index:
                  typeof questionRaw?.questionIndex === 'number'
                    ? questionRaw.questionIndex
                    : typeof nestedQ.questionIndex === 'number'
                      ? nestedQ.questionIndex
                      : typeof nestedQ.index === 'number'
                        ? nestedQ.index
                        : 0,
                state: (nestedQ.state as LiveQuestionSnapshot['state']) ?? undefined,
                promptText:
                  (nestedQ.promptText as string | null | undefined) ?? null,
                timerEndsAt:
                  (nestedQ.timerEndsAt as string | null | undefined) ??
                  (questionRaw?.timerEndsAt as string | null | undefined) ??
                  (asRecord(data.timer).endsAt as string | null | undefined) ??
                  null,
              } as LiveQuestionSnapshot)
            : null
          const leaderboard = parseLeaderboard(data) ?? state.leaderboard
          const podiumEntries = parsePodiumEntries(data)
          const submission =
            typeof asRecord(data.submission).count === 'number'
              ? (asRecord(data.submission).count as number)
              : state.submissionCount
          const participantCount =
            typeof data.participantCount === 'number'
              ? data.participantCount
              : Object.keys(participants).length || state.participantCount

          return {
            ...state,
            connectionStatus: 'connected',
            room,
            participants: Object.keys(participants).length ? participants : state.participants,
            participantCount,
            currentQuestion: question,
            leaderboard,
            podium: podiumEntries?.length ? { entries: podiumEntries } : state.podium,
            submissionCount: submission,
            lastError: null,
          }
        }

        case 'room:state_changed':
        case 'room:lobbyOpened':
        case 'room:lobbyClosed':
        case 'room:sessionStarted':
        case 'room:closed':
          return {
            ...state,
            room: mergeRoom(state.room, data.room ? asRecord(data.room) : data),
          }

        case 'room:paused':
        case 'room:resumed':
          return {
            ...state,
            room: mergeRoom(state.room, data.room ? asRecord(data.room) : data),
            currentQuestion: applyTimerEndsAt(state.currentQuestion, data),
          }

        case 'room:completed':
        case 'quiz:completed': {
          const podiumEntries = parsePodiumEntries(data)
          const leaderboard = parseLeaderboard(data) ?? state.leaderboard
          const roomPatch = data.room ? asRecord(data.room) : { ...data, state: 'Completed' }
          if (!roomPatch.state) roomPatch.state = 'Completed'
          return {
            ...state,
            room: mergeRoom(state.room, roomPatch),
            podium: podiumEntries?.length ? { entries: podiumEntries } : state.podium,
            leaderboard,
            currentQuestion: null,
          }
        }

        case 'section:break': {
          const roomPatch = data.room
            ? asRecord(data.room)
            : { ...data, state: 'SectionBreak' }
          if (!roomPatch.state) roomPatch.state = 'SectionBreak'
          return {
            ...state,
            room: mergeRoom(state.room, roomPatch),
            leaderboard: parseLeaderboard(data) ?? state.leaderboard,
          }
        }

        case 'section:continued':
        case 'section:started': {
          const roomPatch = data.room
            ? asRecord(data.room)
            : type === 'section:continued'
              ? { ...data, state: 'Active' }
              : data
          return {
            ...state,
            room: mergeRoom(state.room, roomPatch),
          }
        }

        case 'participant:count': {
          const count =
            typeof data.participantCount === 'number'
              ? data.participantCount
              : typeof data.count === 'number'
                ? data.count
                : state.participantCount
          return { ...state, participantCount: count }
        }

        case 'participant:joined':
        case 'participant:reconnected': {
          const participant = mapParticipant(
            asRecord(data.participant ?? data),
          )
          if (!participant) return state
          const participants = { ...state.participants, [participant.id]: participant }
          const count =
            typeof data.participantCount === 'number'
              ? data.participantCount
              : Object.values(participants).filter((p) => p.connected !== false).length
          return {
            ...state,
            participants,
            participantCount: count,
          }
        }

        case 'participant:left':
        case 'participant:disconnected': {
          const id = String(
            asRecord(data.participant).id ?? data.participantId ?? data.id ?? '',
          )
          if (!id || !state.participants[id]) {
            if (typeof data.participantCount === 'number') {
              return { ...state, participantCount: data.participantCount }
            }
            return state
          }
          const next = { ...state.participants }
          next[id] = {
            ...next[id],
            connected: false,
            state: type === 'participant:left' ? 'SessionEnded' : 'Disconnected',
          }
          const count =
            typeof data.participantCount === 'number'
              ? data.participantCount
              : Object.values(next).filter((p) => p.connected !== false).length
          return { ...state, participants: next, participantCount: count }
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
              timerEndsAt:
                (q.timerEndsAt as string | null | undefined) ??
                (data.timerEndsAt as string | null | undefined) ??
                null,
            },
            submissionCount: 0,
            room: mergeRoom(state.room, {
              state: 'Active',
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
            participantCount:
              typeof data.participantCount === 'number'
                ? data.participantCount
                : state.participantCount,
          }

        case 'leaderboard:updated':
          return {
            ...state,
            leaderboard: parseLeaderboard(data) ?? state.leaderboard,
          }

        case 'error': {
          const code = String(data.code ?? '')
          if (
            code === 'AUTH_ERROR' ||
            code === 'UNAUTHORIZED' ||
            code === 'FORBIDDEN' ||
            code === 'TOKEN_EXPIRED'
          ) {
            return {
              ...state,
              lastError: String(data.message ?? 'Authentication failed'),
              connectionStatus: 'error',
            }
          }
          return {
            ...state,
            lastError: String(data.message ?? 'WebSocket error'),
          }
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
  const handleRef = useRef<WsConnectionHandle | null>(null)
  const reconnectAttempt = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const intentionalClose = useRef(false)
  const enabledRef = useRef(enabled)
  const roomIdRef = useRef(roomId)
  const connectRef = useRef<(() => void) | null>(null)

  enabledRef.current = enabled
  roomIdRef.current = roomId

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

  const disconnect = useCallback(() => {
    intentionalClose.current = true
    clearReconnectTimer()
    releaseHandle(true)
    dispatch({ type: 'STATUS', status: 'disconnected' })
    wsDebug('admin', 'cleanup', { reason: 'disconnect()' })
  }, [clearReconnectTimer, releaseHandle])

  const reconnect = useCallback(() => {
    intentionalClose.current = false
    reconnectAttempt.current = 0
    clearReconnectTimer()
    releaseHandle(true)
    dispatch({ type: 'CLEAR_ERROR' })
    wsDebug('admin', 'reconnect', { reason: 'manual' })
    connectRef.current?.()
  }, [clearReconnectTimer, releaseHandle])

  useEffect(() => {
    if (!enabled || !roomId) {
      intentionalClose.current = true
      clearReconnectTimer()
      releaseHandle(true)
      dispatch({ type: 'RESET' })
      wsDebug('admin', 'skip', { reason: 'disabled', roomId })
      return
    }

    intentionalClose.current = false

    const connect = () => {
      const currentRoomId = roomIdRef.current
      if (!enabledRef.current || !currentRoomId || intentionalClose.current) {
        wsDebug('admin', 'skip', { reason: 'guard' })
        return
      }

      const token = getToken()
      if (!token) {
        dispatch({ type: 'ERROR', message: 'Missing auth token for WebSocket' })
        return
      }

      releaseHandle(false)

      const base = getWsBaseUrl()
      const url = `${base}?role=admin&token=${encodeURIComponent(token)}&roomId=${encodeURIComponent(currentRoomId)}`
      const key = makeWsKey('admin', { token, roomId: currentRoomId })

      dispatch({ type: 'STATUS', status: 'connecting' })

      const handle = acquireWebSocket('admin', key, url, {
        onOpen: () => {
          if (handleRef.current !== handle) return
          reconnectAttempt.current = 0
          dispatch({ type: 'STATUS', status: 'connected' })
        },
        onMessage: (event, ws) => {
          if (handleRef.current !== handle) return
          // Heal stale disconnected banners without re-rendering on every frame.
          if (handle.readyState() === WebSocket.OPEN) {
            dispatch({ type: 'STATUS', status: 'connected' })
          }
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
                code === 'UNAUTHORIZED' ||
                code === 'FORBIDDEN' ||
                code === 'TOKEN_EXPIRED'
              ) {
                intentionalClose.current = true
                clearReconnectTimer()
                wsDebug('admin', 'auth', { code })
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
          if (intentionalClose.current) {
            dispatch({ type: 'STATUS', status: 'disconnected' })
            return
          }
          dispatch({ type: 'STATUS', status: 'disconnected' })
          const attempt = reconnectAttempt.current
          const delay = Math.min(30_000, 1000 * 2 ** attempt)
          reconnectAttempt.current = attempt + 1
          clearReconnectTimer()
          wsDebug('admin', 'reconnect', { attempt, delay })
          reconnectTimer.current = setTimeout(() => {
            connectRef.current?.()
          }, delay)
        },
      })

      handleRef.current = handle
      if (handle.readyState() === WebSocket.OPEN) {
        reconnectAttempt.current = 0
        dispatch({ type: 'STATUS', status: 'connected' })
      } else if (handle.readyState() === WebSocket.CONNECTING) {
        dispatch({ type: 'STATUS', status: 'connecting' })
      }
    }

    connectRef.current = connect
    connect()

    const syncTimer = window.setInterval(() => {
      const handle = handleRef.current
      if (!handle || !enabledRef.current || intentionalClose.current) return
      if (handle.readyState() === WebSocket.OPEN) {
        dispatch({ type: 'STATUS', status: 'connected' })
      }
    }, 1000)

    const onOnline = () => {
      if (!enabledRef.current || !roomIdRef.current) return
      intentionalClose.current = false
      reconnectAttempt.current = 0
      clearReconnectTimer()
      wsDebug('admin', 'reconnect', { reason: 'online' })
      connectRef.current?.()
    }
    window.addEventListener('online', onOnline)

    return () => {
      window.removeEventListener('online', onOnline)
      window.clearInterval(syncTimer)
      // Soft StrictMode cleanup — keep intentionalClose false so remount can report connected.
      connectRef.current = null
      clearReconnectTimer()
      releaseHandle(false)
      wsDebug('admin', 'cleanup', { reason: 'effect-cleanup' })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- bind on room/enabled only
  }, [roomId, enabled])

  useEffect(() => {
    if (enabled && roomId) return
    const timer = window.setTimeout(() => releaseHandle(true), 200)
    return () => window.clearTimeout(timer)
  }, [enabled, roomId, releaseHandle])

  return {
    ...state,
    send,
    disconnect,
    reconnect,
    applyRoomSnapshot: (room: LiveRoom) => dispatch({ type: 'APPLY_ROOM', room }),
    clearError: () => dispatch({ type: 'CLEAR_ERROR' }),
  }
}
