import type {
  AnswerSubmitState,
  LeaderboardEntry,
  LobbySubState,
  ParticipantLiveOption,
  ParticipantLiveQuestion,
  ParticipantSelfSnapshot,
  Podium,
  RoomState,
  SessionQuestionState,
  SubmissionStatus,
  WsMessage,
} from '@/types/api'

export type WsConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export interface ParticipantLiveState {
  connectionStatus: WsConnectionStatus
  room: {
    id: string
    roomCode: string
    state: RoomState
    lobbySubState?: LobbySubState | null
    quizTitle: string
    codesExpired?: boolean
    currentQuestionIndex?: number | null
  } | null
  self: ParticipantSelfSnapshot | null
  question: ParticipantLiveQuestion | null
  options: ParticipantLiveOption[]
  submissionStatus: AnswerSubmitState
  submissionError: string | null
  selectedOptionIds: string[]
  leaderboard: LeaderboardEntry[]
  yourRank: number | null
  yourScore: number
  podium: Podium | null
  participantCount: number | null
  submittedCount: number | null
  resultsReady: boolean
  lastError: string | null
  isOffline: boolean
}

export type ParticipantLiveAction =
  | { type: 'STATUS'; status: WsConnectionStatus }
  | { type: 'ERROR'; message: string }
  | { type: 'CLEAR_ERROR' }
  | { type: 'RESET' }
  | { type: 'SET_OFFLINE'; offline: boolean }
  | { type: 'SELECT_OPTIONS'; optionIds: string[] }
  | { type: 'SUBMIT_START'; optionIds: string[] }
  | { type: 'EVENT'; message: WsMessage }

export const initialParticipantLiveState: ParticipantLiveState = {
  connectionStatus: 'disconnected',
  room: null,
  self: null,
  question: null,
  options: [],
  submissionStatus: 'idle',
  submissionError: null,
  selectedOptionIds: [],
  leaderboard: [],
  yourRank: null,
  yourScore: 0,
  podium: null,
  participantCount: null,
  submittedCount: null,
  resultsReady: false,
  lastError: null,
  isOffline: typeof navigator !== 'undefined' ? !navigator.onLine : false,
}

export function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

export function computeReconnectDelay(attempt: number, maxMs = 10_000): number {
  return Math.min(maxMs, 1000 * 2 ** Math.max(0, attempt))
}

export function getParticipantRouteForRoomState(
  state: RoomState | string | null | undefined,
): '/lobby' | '/quiz' | '/results' | null {
  if (!state) return null
  switch (state) {
    case 'Lobby':
    case 'Setup':
      return '/lobby'
    case 'Active':
    case 'Paused':
    case 'SectionBreak':
      return '/quiz'
    case 'Completed':
    case 'Closed':
      return '/results'
    default:
      return null
  }
}

export function computeAccuracyPercent(
  correct: number,
  incorrect: number,
): number {
  const answered = Math.max(0, correct) + Math.max(0, incorrect)
  if (answered === 0) return 0
  return Math.round((Math.max(0, correct) / answered) * 100)
}

function stripEmailsFromLeaderboard(entries: LeaderboardEntry[]): LeaderboardEntry[] {
  return entries.map(({ rank, participantId, displayName, score, streak }) => ({
    rank,
    participantId,
    displayName,
    score,
    streak,
  }))
}

function mapOptions(
  raw: unknown,
  { includeCorrect }: { includeCorrect: boolean },
): ParticipantLiveOption[] {
  if (!Array.isArray(raw)) return []
  return raw.map((item, index) => {
    const opt = asRecord(item)
    const mapped: ParticipantLiveOption = {
      id: String(opt.id ?? ''),
      text: String(opt.text ?? ''),
      sortOrder: typeof opt.sortOrder === 'number' ? opt.sortOrder : index,
    }
    if (includeCorrect && typeof opt.isCorrect === 'boolean') {
      mapped.isCorrect = opt.isCorrect
    }
    return mapped
  })
}

function mapQuestion(
  payload: Record<string, unknown>,
  existing: ParticipantLiveQuestion | null,
  { reveal }: { reveal: boolean },
): ParticipantLiveQuestion | null {
  const nested = payload.question ? asRecord(payload.question) : payload
  const id = String(nested.id ?? existing?.id ?? '')
  if (!id && !existing) return null

  const section = asRecord(payload.section ?? nested.section)
  const index =
    typeof payload.questionIndex === 'number'
      ? payload.questionIndex
      : typeof nested.questionIndex === 'number'
        ? nested.questionIndex
        : typeof nested.index === 'number'
          ? nested.index
          : (existing?.index ?? 0)

  const options = mapOptions(nested.options, { includeCorrect: reveal })
  const resolvedOptions =
    options.length > 0
      ? options
      : reveal && existing?.options.length
        ? existing.options.map((opt) => {
            const match = mapOptions(nested.options, { includeCorrect: true }).find(
              (o) => o.id === opt.id,
            )
            return match ?? opt
          })
        : (existing?.options ?? [])

  // On reveal, merge isCorrect onto existing options when nested has them
  let finalOptions = resolvedOptions
  if (reveal && Array.isArray(nested.options) && existing?.options.length) {
    const correctMap = new Map(
      mapOptions(nested.options, { includeCorrect: true }).map((o) => [o.id, o]),
    )
    finalOptions = (options.length ? options : existing.options).map((opt) => {
      const updated = correctMap.get(opt.id)
      return updated
        ? { ...opt, isCorrect: updated.isCorrect }
        : opt
    })
  }

  return {
    id: id || (existing?.id ?? ''),
    index,
    promptText:
      (nested.promptText as string | null | undefined) ?? existing?.promptText ?? null,
    questionType:
      (nested.questionType as ParticipantLiveQuestion['questionType']) ??
      existing?.questionType,
    state:
      (nested.state as SessionQuestionState | undefined) ??
      (reveal ? 'Revealed' : existing?.state),
    timeLimitSeconds:
      typeof nested.timeLimitSeconds === 'number'
        ? nested.timeLimitSeconds
        : (existing?.timeLimitSeconds ?? null),
    timerEndsAt:
      (nested.timerEndsAt as string | null | undefined) ?? existing?.timerEndsAt ?? null,
    basePoints:
      typeof nested.basePoints === 'number' ? nested.basePoints : existing?.basePoints,
    allowMultipleCorrect:
      typeof nested.allowMultipleCorrect === 'boolean'
        ? nested.allowMultipleCorrect
        : existing?.allowMultipleCorrect,
    mediaFileId:
      (nested.mediaFileId as string | null | undefined) ?? existing?.mediaFileId ?? null,
    sectionId: String(section.id ?? nested.sectionId ?? existing?.sectionId ?? '') || null,
    sectionName:
      (section.name as string | undefined) ?? existing?.sectionName ?? null,
    totalQuestions:
      typeof payload.totalQuestions === 'number'
        ? payload.totalQuestions
        : (existing?.totalQuestions ?? null),
    options: finalOptions,
    isAcceptingAnswers:
      typeof nested.isAcceptingAnswers === 'boolean'
        ? nested.isAcceptingAnswers
        : existing?.isAcceptingAnswers,
  }
}

function mapSelf(
  raw: Record<string, unknown>,
  existing: ParticipantSelfSnapshot | null,
): ParticipantSelfSnapshot | null {
  const id = String(raw.id ?? raw.participantId ?? existing?.id ?? '')
  if (!id) return existing
  const score =
    typeof raw.totalScore === 'number'
      ? raw.totalScore
      : typeof raw.score === 'number'
        ? raw.score
        : (existing?.totalScore ?? 0)
  return {
    id,
    displayName: String(raw.displayName ?? existing?.displayName ?? 'You'),
    state: (raw.state as ParticipantSelfSnapshot['state']) ?? existing?.state,
    connectionStatus:
      (raw.connectionStatus as string | undefined) ?? existing?.connectionStatus,
    totalScore: score,
    streak: typeof raw.streak === 'number' ? raw.streak : (existing?.streak ?? 0),
    rank:
      typeof raw.rank === 'number'
        ? raw.rank
        : raw.rank === null
          ? null
          : (existing?.rank ?? null),
    totalCorrect:
      typeof raw.totalCorrect === 'number' ? raw.totalCorrect : existing?.totalCorrect,
    totalIncorrect:
      typeof raw.totalIncorrect === 'number'
        ? raw.totalIncorrect
        : existing?.totalIncorrect,
    unansweredCount:
      typeof raw.unansweredCount === 'number'
        ? raw.unansweredCount
        : existing?.unansweredCount,
    email: (raw.email as string | undefined) ?? existing?.email,
  }
}

function mapRoom(
  existing: ParticipantLiveState['room'],
  patch: Record<string, unknown>,
): ParticipantLiveState['room'] {
  const id = String(patch.id ?? patch.roomId ?? existing?.id ?? '')
  if (!id && !existing) return existing
  return {
    id: id || (existing?.id ?? ''),
    roomCode: String(patch.roomCode ?? existing?.roomCode ?? ''),
    state: (patch.state as RoomState) ?? existing?.state ?? 'Lobby',
    lobbySubState:
      (patch.lobbySubState as LobbySubState | null | undefined) ??
      existing?.lobbySubState ??
      null,
    quizTitle: String(
      patch.quizTitle ?? patch.quizTitleSnapshot ?? existing?.quizTitle ?? '',
    ),
    codesExpired:
      typeof patch.codesExpired === 'boolean'
        ? patch.codesExpired
        : existing?.codesExpired,
    currentQuestionIndex:
      typeof patch.currentQuestionIndex === 'number'
        ? patch.currentQuestionIndex
        : (existing?.currentQuestionIndex ?? null),
  }
}

function applySubmissionStatus(
  state: ParticipantLiveState,
  submission: SubmissionStatus | Record<string, unknown> | null | undefined,
): Partial<ParticipantLiveState> {
  if (!submission) return {}
  const data = asRecord(submission)
  const hasSubmitted = Boolean(data.hasSubmitted)
  const selected = Array.isArray(data.selectedOptionIds)
    ? (data.selectedOptionIds as string[])
    : []
  if (hasSubmitted) {
    return {
      submissionStatus: 'submitted',
      selectedOptionIds: selected.length ? selected : state.selectedOptionIds,
      submissionError: null,
    }
  }
  return {
    submissionStatus: selected.length ? 'selecting' : 'idle',
    selectedOptionIds: selected,
  }
}

function parseLeaderboard(data: Record<string, unknown>): LeaderboardEntry[] | null {
  if (Array.isArray(data.entries)) {
    return stripEmailsFromLeaderboard(data.entries as LeaderboardEntry[])
  }
  if (Array.isArray(data.leaderboard)) {
    return stripEmailsFromLeaderboard(data.leaderboard as LeaderboardEntry[])
  }
  return null
}

function parsePodium(data: Record<string, unknown>): Podium | null {
  const podiumPayload = data.podium ?? data
  const entries = Array.isArray(asRecord(podiumPayload).entries)
    ? (asRecord(podiumPayload).entries as Podium['entries'])
    : Array.isArray(data.entries)
      ? (data.entries as Podium['entries'])
      : []
  return entries.length ? { entries } : null
}

export function participantLiveReducer(
  state: ParticipantLiveState,
  action: ParticipantLiveAction,
): ParticipantLiveState {
  switch (action.type) {
    case 'STATUS':
      return { ...state, connectionStatus: action.status }
    case 'ERROR':
      return { ...state, lastError: action.message, connectionStatus: 'error' }
    case 'CLEAR_ERROR':
      return { ...state, lastError: null }
    case 'RESET':
      return {
        ...initialParticipantLiveState,
        isOffline: state.isOffline,
      }
    case 'SET_OFFLINE':
      return { ...state, isOffline: action.offline }
    case 'SELECT_OPTIONS': {
      if (
        state.submissionStatus === 'submitting' ||
        state.submissionStatus === 'submitted' ||
        state.submissionStatus === 'already_submitted'
      ) {
        return state
      }
      const qState = state.question?.state
      if (qState === 'Closed' || qState === 'Revealed' || qState === 'Scored') {
        return state
      }
      return {
        ...state,
        selectedOptionIds: action.optionIds,
        submissionStatus: action.optionIds.length ? 'selecting' : 'idle',
        submissionError: null,
      }
    }
    case 'SUBMIT_START': {
      if (
        state.submissionStatus === 'submitting' ||
        state.submissionStatus === 'submitted' ||
        state.submissionStatus === 'already_submitted'
      ) {
        return state
      }
      return {
        ...state,
        selectedOptionIds: action.optionIds,
        submissionStatus: 'submitting',
        submissionError: null,
      }
    }
    case 'EVENT': {
      const { type, payload } = action.message
      const data = asRecord(payload)

      switch (type) {
        case 'connection:ack':
          return { ...state, connectionStatus: 'connected', lastError: null }

        case 'resync': {
          const room = data.room
            ? mapRoom(state.room, asRecord(data.room))
            : state.room
          const self = data.participant
            ? mapSelf(asRecord(data.participant), state.self)
            : state.self
          const question = data.question
            ? mapQuestion(asRecord(data.question), state.question, { reveal: false })
            : null
          const submissionPatch = applySubmissionStatus(
            state,
            (data.submission as SubmissionStatus) ??
              (asRecord(data.participant).submission as SubmissionStatus) ??
              null,
          )
          const leaderboard = parseLeaderboard(data) ?? state.leaderboard
          const yourRank =
            typeof self?.rank === 'number' ? self.rank : state.yourRank
          const yourScore = self?.totalScore ?? state.yourScore

          return {
            ...state,
            connectionStatus: 'connected',
            room,
            self,
            question,
            options: question?.options ?? [],
            leaderboard,
            yourRank,
            yourScore,
            lastError: null,
            ...submissionPatch,
          }
        }

        case 'room:state_changed':
        case 'room:lobbyOpened':
        case 'room:lobbyClosed':
        case 'room:sessionStarted':
        case 'room:paused':
        case 'room:resumed':
        case 'room:closed':
        case 'section:break':
        case 'section:continued':
        case 'section:started':
          return {
            ...state,
            room: mapRoom(state.room, data.room ? asRecord(data.room) : data),
            participantCount:
              typeof data.participantCount === 'number'
                ? data.participantCount
                : state.participantCount,
          }

        case 'room:completed':
        case 'quiz:completed': {
          const podium = parsePodium(data) ?? state.podium
          return {
            ...state,
            room: mapRoom(state.room, data.room ? asRecord(data.room) : data),
            podium,
            resultsReady: true,
          }
        }

        case 'results:ready':
          return {
            ...state,
            resultsReady: true,
            podium: parsePodium(data) ?? state.podium,
            leaderboard: parseLeaderboard(data) ?? state.leaderboard,
          }

        case 'question:started': {
          const question = mapQuestion(data, null, { reveal: false })
          if (question) {
            question.state = question.state ?? 'Open'
          }
          return {
            ...state,
            question,
            options: question?.options ?? [],
            submissionStatus: 'idle',
            submissionError: null,
            selectedOptionIds: [],
            submittedCount: 0,
            room: mapRoom(state.room, {
              currentQuestionIndex: question?.index ?? data.questionIndex,
            }),
          }
        }

        case 'question:closed': {
          const question = mapQuestion(data, state.question, { reveal: false })
          if (question) question.state = 'Closed'
          return {
            ...state,
            question,
            options: question?.options ?? state.options,
          }
        }

        case 'question:reveal':
        case 'question:scored': {
          const question = mapQuestion(data, state.question, { reveal: true })
          if (question) {
            question.state = type === 'question:reveal' ? 'Revealed' : 'Scored'
          }
          return {
            ...state,
            question,
            options: question?.options ?? state.options,
          }
        }

        case 'answer:accepted': {
          const selected = Array.isArray(data.selectedOptionIds)
            ? (data.selectedOptionIds as string[])
            : state.selectedOptionIds
          return {
            ...state,
            submissionStatus: 'submitted',
            selectedOptionIds: selected,
            submissionError: null,
          }
        }

        case 'answer:rejected': {
          const code = String(data.code ?? '')
          if (code === 'ALREADY_SUBMITTED') {
            return {
              ...state,
              submissionStatus: 'already_submitted',
              submissionError: String(data.message ?? 'Already submitted'),
            }
          }
          return {
            ...state,
            submissionStatus: 'rejected',
            submissionError: String(data.message ?? 'Answer rejected'),
          }
        }

        case 'answer:submission_count':
        case 'answer:received':
          return {
            ...state,
            submittedCount:
              typeof data.submittedCount === 'number'
                ? data.submittedCount
                : typeof data.count === 'number'
                  ? data.count
                  : state.submittedCount,
            participantCount:
              typeof data.participantCount === 'number'
                ? data.participantCount
                : state.participantCount,
          }

        case 'leaderboard:updated': {
          const leaderboard = parseLeaderboard(data) ?? state.leaderboard
          const selfId = state.self?.id
          const own = selfId
            ? leaderboard.find((e) => e.participantId === selfId)
            : undefined
          return {
            ...state,
            leaderboard,
            yourRank: own?.rank ?? state.yourRank,
            yourScore: own?.score ?? state.yourScore,
            self: state.self
              ? {
                  ...state.self,
                  rank: own?.rank ?? state.self.rank,
                  totalScore: own?.score ?? state.self.totalScore,
                  streak: own?.streak ?? state.self.streak,
                }
              : state.self,
          }
        }

        case 'error':
          return {
            ...state,
            lastError: String(data.message ?? 'WebSocket error'),
            submissionStatus:
              state.submissionStatus === 'submitting' ? 'rejected' : state.submissionStatus,
            submissionError:
              state.submissionStatus === 'submitting'
                ? String(data.message ?? 'WebSocket error')
                : state.submissionError,
          }

        case 'ping':
        case 'pong':
          return state

        default:
          if (data.room) {
            return { ...state, room: mapRoom(state.room, asRecord(data.room)) }
          }
          return state
      }
    }
    default:
      return state
  }
}
