import type {
  LeaderboardEntry,
  LobbySubState,
  Podium,
  QuestionType,
  RoomState,
  SessionQuestionState,
  WsMessage,
} from '@/types/api'

export type WsConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export type DisplayViewMode =
  | 'waiting'
  | 'question'
  | 'time_up'
  | 'reveal'
  | 'section_break'
  | 'leaderboard'
  | 'podium'
  | 'completed'

export interface DisplayLiveOption {
  id: string
  text: string
  sortOrder: number
  isCorrect?: boolean
}

export interface DisplayLiveQuestion {
  id: string
  index: number
  totalQuestions?: number | null
  promptText?: string | null
  sectionName?: string | null
  mediaFileId?: string | null
  /** WS path/URL for question media (no bytes). Prefer over reconstructing from mediaFileId. */
  imageUrl?: string | null
  questionType?: QuestionType
  state?: SessionQuestionState
  basePoints?: number
  allowMultipleCorrect?: boolean
  timeLimitSeconds?: number | null
  timerEndsAt?: string | null
  options: DisplayLiveOption[]
}

export interface DisplayLiveRoom {
  id: string
  roomCode: string
  state: RoomState
  lobbySubState?: LobbySubState | null
  quizTitle: string
  currentQuestionIndex?: number | null
  codesExpired?: boolean
}

export interface DisplaySection {
  id: string
  name: string
  sortOrder?: number
}

export interface DisplayOptionDistribution {
  optionId: string
  text: string
  selectedCount: number
  percent: number
  isCorrect: boolean
}

export interface DisplaySectionStats {
  questionCount: number
  participantCount: number
  averageAccuracy: number
}

export interface DisplayQuestionHighlight {
  questionId: string
  questionIndex: number
  promptText?: string | null
  accuracyPercent: number
  missPercent?: number
}

export interface DisplayFastestAnswer {
  participantId: string
  displayName: string
  responseTimeMs: number
  questionId: string
  promptText?: string | null
}

export interface DisplayWinner {
  participantId: string
  displayName: string
  score: number
  rank: number
}

export interface DisplaySessionHighlights {
  averageScore?: number | null
  winner?: DisplayWinner | null
  hardestQuestion?: DisplayQuestionHighlight | null
  mostMissedQuestion?: DisplayQuestionHighlight | null
  fastestAnswer?: DisplayFastestAnswer | null
}

export interface DisplayLiveState {
  connectionStatus: WsConnectionStatus
  room: DisplayLiveRoom | null
  question: DisplayLiveQuestion | null
  viewMode: DisplayViewMode
  leaderboard: LeaderboardEntry[]
  previousRanks: Record<string, number>
  top3: LeaderboardEntry[]
  podium: Podium | null
  section: DisplaySection | null
  sectionStats: DisplaySectionStats | null
  sessionHighlights: DisplaySessionHighlights | null
  participantCount: number
  submittedCount: number
  optionDistribution: DisplayOptionDistribution[]
  explanation: string | null
  answeredCount: number | null
  accuracyPercent: number | null
  questionOpenedAt: number | null
  showLeaderboardAfterScore: boolean
  resultsReady: boolean
  lastError: string | null
  authFailed: boolean
}

export type DisplayLiveAction =
  | { type: 'STATUS'; status: WsConnectionStatus }
  | { type: 'ERROR'; message: string; authFailed?: boolean }
  | { type: 'CLEAR_ERROR' }
  | { type: 'RESET' }
  | { type: 'AUTH_FAILED'; message: string }
  | { type: 'EVENT'; message: WsMessage }

export const initialDisplayLiveState: DisplayLiveState = {
  connectionStatus: 'disconnected',
  room: null,
  question: null,
  viewMode: 'waiting',
  leaderboard: [],
  previousRanks: {},
  top3: [],
  podium: null,
  section: null,
  sectionStats: null,
  sessionHighlights: null,
  participantCount: 0,
  submittedCount: 0,
  optionDistribution: [],
  explanation: null,
  answeredCount: null,
  accuracyPercent: null,
  questionOpenedAt: null,
  showLeaderboardAfterScore: false,
  resultsReady: false,
  lastError: null,
  authFailed: false,
}

export function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

export function computeReconnectDelay(attempt: number, maxMs = 10_000): number {
  return Math.min(maxMs, 1000 * 2 ** Math.max(0, attempt))
}

function stripEmailsFromLeaderboard(entries: LeaderboardEntry[]): LeaderboardEntry[] {
  return entries.map(
    ({
      rank,
      participantId,
      displayName,
      score,
      streak,
      timeBonus,
      lastTimeBonus,
      lastIsCorrect,
    }) => ({
      rank,
      participantId,
      displayName,
      score,
      streak,
      timeBonus,
      lastTimeBonus,
      lastIsCorrect,
    }),
  )
}

function mapOptions(
  raw: unknown,
  { includeCorrect }: { includeCorrect: boolean },
): DisplayLiveOption[] {
  if (!Array.isArray(raw)) return []
  return raw.map((item, index) => {
    const opt = asRecord(item)
    const mapped: DisplayLiveOption = {
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

function mapSection(
  raw: unknown,
  existing: DisplaySection | null,
): DisplaySection | null {
  if (!raw || typeof raw !== 'object') return existing
  const data = asRecord(raw)
  const id = String(data.id ?? existing?.id ?? '')
  if (!id && !existing) return null
  return {
    id: id || (existing?.id ?? ''),
    name: String(data.name ?? existing?.name ?? ''),
    sortOrder:
      typeof data.sortOrder === 'number' ? data.sortOrder : existing?.sortOrder,
  }
}

function mapQuestion(
  payload: Record<string, unknown>,
  existing: DisplayLiveQuestion | null,
  { reveal }: { reveal: boolean },
): DisplayLiveQuestion | null {
  const nested = payload.question ? asRecord(payload.question) : payload
  const id = String(nested.id ?? existing?.id ?? '')
  if (!id && !existing) {
    const hasAnyContent =
      nested.promptText != null ||
      Array.isArray(nested.options) ||
      typeof nested.questionIndex === 'number' ||
      typeof nested.index === 'number'
    if (!hasAnyContent) return null
  }

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
  let finalOptions = options.length > 0 ? options : (existing?.options ?? [])

  if (reveal && Array.isArray(nested.options) && existing?.options.length) {
    const correctMap = new Map(
      mapOptions(nested.options, { includeCorrect: true }).map((o) => [o.id, o]),
    )
    finalOptions = (options.length ? options : existing.options).map((opt) => {
      const updated = correctMap.get(opt.id)
      return updated ? { ...opt, isCorrect: updated.isCorrect } : opt
    })
  }

  if (!reveal) {
    finalOptions = finalOptions.map(({ id: optId, text, sortOrder }) => ({
      id: optId,
      text,
      sortOrder,
    }))
  }

  return {
    id: id || (existing?.id ?? ''),
    index,
    promptText:
      (nested.promptText as string | null | undefined) ?? existing?.promptText ?? null,
    questionType:
      (nested.questionType as QuestionType | undefined) ?? existing?.questionType,
    state:
      (nested.state as SessionQuestionState | undefined) ??
      (reveal ? 'Revealed' : existing?.state),
    basePoints:
      typeof nested.basePoints === 'number' ? nested.basePoints : existing?.basePoints,
    allowMultipleCorrect:
      typeof nested.allowMultipleCorrect === 'boolean'
        ? nested.allowMultipleCorrect
        : existing?.allowMultipleCorrect,
    timeLimitSeconds:
      typeof nested.timeLimitSeconds === 'number'
        ? nested.timeLimitSeconds
        : (existing?.timeLimitSeconds ?? null),
    timerEndsAt:
      (nested.timerEndsAt as string | null | undefined) ??
      (payload.timerEndsAt as string | null | undefined) ??
      existing?.timerEndsAt ??
      null,
    mediaFileId:
      (nested.mediaFileId as string | null | undefined) ?? existing?.mediaFileId ?? null,
    imageUrl:
      (nested.imageUrl as string | null | undefined) ?? existing?.imageUrl ?? null,
    sectionName:
      (section.name as string | undefined) ??
      (nested.sectionName as string | undefined) ??
      existing?.sectionName ??
      null,
    totalQuestions:
      typeof payload.totalQuestions === 'number'
        ? payload.totalQuestions
        : typeof nested.totalQuestions === 'number'
          ? nested.totalQuestions
          : (existing?.totalQuestions ?? null),
    options: finalOptions,
  }
}

function mapRoom(
  existing: DisplayLiveRoom | null,
  patch: Record<string, unknown>,
): DisplayLiveRoom | null {
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

function parseLeaderboard(data: Record<string, unknown>): LeaderboardEntry[] | null {
  if (Array.isArray(data.entries)) {
    return stripEmailsFromLeaderboard(data.entries as LeaderboardEntry[])
  }
  if (Array.isArray(data.leaderboard)) {
    return stripEmailsFromLeaderboard(data.leaderboard as LeaderboardEntry[])
  }
  return null
}

function parseTop3(data: Record<string, unknown>): LeaderboardEntry[] | null {
  if (Array.isArray(data.top3)) {
    return stripEmailsFromLeaderboard(data.top3 as LeaderboardEntry[])
  }
  const podium = asRecord(data.podium)
  if (Array.isArray(podium.entries)) {
    return stripEmailsFromLeaderboard(podium.entries as LeaderboardEntry[])
  }
  const board = parseLeaderboard(data)
  return board ? board.slice(0, 3) : null
}

function parseOptionDistribution(
  data: Record<string, unknown>,
): DisplayOptionDistribution[] {
  if (!Array.isArray(data.optionDistribution)) return []
  return data.optionDistribution.map((item) => {
    const row = asRecord(item)
    return {
      optionId: String(row.optionId ?? ''),
      text: String(row.text ?? ''),
      selectedCount:
        typeof row.selectedCount === 'number' ? row.selectedCount : 0,
      percent: typeof row.percent === 'number' ? row.percent : 0,
      isCorrect: row.isCorrect === true,
    }
  })
}

function parseSectionStats(data: Record<string, unknown>): DisplaySectionStats | null {
  const stats = asRecord(data.sectionStats)
  if (!Object.keys(stats).length) return null
  return {
    questionCount:
      typeof stats.questionCount === 'number' ? stats.questionCount : 0,
    participantCount:
      typeof stats.participantCount === 'number' ? stats.participantCount : 0,
    averageAccuracy:
      typeof stats.averageAccuracy === 'number' ? stats.averageAccuracy : 0,
  }
}

function parseQuestionHighlight(raw: unknown): DisplayQuestionHighlight | null {
  if (!raw || typeof raw !== 'object') return null
  const data = asRecord(raw)
  if (!data.questionId) return null
  return {
    questionId: String(data.questionId),
    questionIndex:
      typeof data.questionIndex === 'number' ? data.questionIndex : 0,
    promptText: (data.promptText as string | null | undefined) ?? null,
    accuracyPercent:
      typeof data.accuracyPercent === 'number' ? data.accuracyPercent : 0,
    missPercent:
      typeof data.missPercent === 'number' ? data.missPercent : undefined,
  }
}

function parseFastestAnswer(raw: unknown): DisplayFastestAnswer | null {
  if (!raw || typeof raw !== 'object') return null
  const data = asRecord(raw)
  if (!data.participantId) return null
  return {
    participantId: String(data.participantId),
    displayName: String(data.displayName ?? 'Player'),
    responseTimeMs:
      typeof data.responseTimeMs === 'number' ? data.responseTimeMs : 0,
    questionId: String(data.questionId ?? ''),
    promptText: (data.promptText as string | null | undefined) ?? null,
  }
}

function parseWinner(raw: unknown): DisplayWinner | null {
  if (!raw || typeof raw !== 'object') return null
  const data = asRecord(raw)
  if (!data.participantId) return null
  return {
    participantId: String(data.participantId),
    displayName: String(data.displayName ?? 'Winner'),
    score: typeof data.score === 'number' ? data.score : 0,
    rank: typeof data.rank === 'number' ? data.rank : 1,
  }
}

function parseSessionHighlights(data: Record<string, unknown>): DisplaySessionHighlights {
  return {
    averageScore:
      typeof data.averageScore === 'number' ? data.averageScore : null,
    winner: parseWinner(data.winner),
    hardestQuestion: parseQuestionHighlight(data.hardestQuestion),
    mostMissedQuestion: parseQuestionHighlight(data.mostMissedQuestion),
    fastestAnswer: parseFastestAnswer(data.fastestAnswer),
  }
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

function ranksFromLeaderboard(entries: LeaderboardEntry[]): Record<string, number> {
  const ranks: Record<string, number> = {}
  for (const entry of entries) {
    ranks[entry.participantId] = entry.rank
  }
  return ranks
}

function parseParticipantCount(
  data: Record<string, unknown>,
  fallback: number,
): number {
  if (typeof data.participantCount === 'number') return data.participantCount
  return fallback
}

function parseSubmittedCount(
  data: Record<string, unknown>,
  fallback: number,
): number {
  if (typeof data.submittedCount === 'number') return data.submittedCount
  if (typeof data.count === 'number') return data.count
  return fallback
}

function isAuthFailureCode(code: string): boolean {
  return (
    code === 'AUTH_ERROR' ||
    code === 'ROOM_CLOSED' ||
    code === 'FORBIDDEN' ||
    code === 'UNAUTHORIZED'
  )
}

export function deriveViewMode(input: {
  room: DisplayLiveRoom | null
  question: DisplayLiveQuestion | null
  podium: Podium | null
  resultsReady: boolean
  preferLeaderboard?: boolean
}): DisplayViewMode {
  const roomState = input.room?.state
  const qState = input.question?.state

  if (roomState === 'Completed' || roomState === 'Closed' || input.resultsReady) {
    if (input.podium?.entries?.length) return 'podium'
    return 'completed'
  }

  if (roomState === 'SectionBreak') {
    return 'section_break'
  }

  if (!roomState || roomState === 'Setup' || roomState === 'Lobby') {
    return 'waiting'
  }

  if (roomState === 'Active' || roomState === 'Paused') {
    if (!input.question) return 'waiting'

    if (qState === 'Closed') {
      return 'time_up'
    }

    if (qState === 'Revealed' || qState === 'Scored') {
      // Keep reveal on the main stage; live standings live in the side panel.
      return 'reveal'
    }

    if (
      qState === 'Open' ||
      qState === 'BuzzerOpen' ||
      qState === 'BuzzerLocked' ||
      qState === 'Pending'
    ) {
      return 'question'
    }

    return 'waiting'
  }

  return 'waiting'
}

function withViewMode(
  state: DisplayLiveState,
  patch: Partial<DisplayLiveState>,
  preferLeaderboard = false,
): DisplayLiveState {
  const next = { ...state, ...patch }
  next.viewMode = deriveViewMode({
    room: next.room,
    question: next.question,
    podium: next.podium,
    resultsReady: next.resultsReady,
    preferLeaderboard: preferLeaderboard || next.showLeaderboardAfterScore,
  })
  return next
}

function questionResetPatch(): Partial<DisplayLiveState> {
  return {
    submittedCount: 0,
    optionDistribution: [],
    explanation: null,
    answeredCount: null,
    accuracyPercent: null,
    showLeaderboardAfterScore: false,
  }
}

export function displayLiveReducer(
  state: DisplayLiveState,
  action: DisplayLiveAction,
): DisplayLiveState {
  switch (action.type) {
    case 'STATUS':
      if (state.connectionStatus === action.status) return state
      return { ...state, connectionStatus: action.status }
    case 'ERROR':
      return {
        ...state,
        lastError: action.message,
        connectionStatus: 'error',
        authFailed: action.authFailed === true ? true : state.authFailed,
      }
    case 'AUTH_FAILED':
      return {
        ...state,
        authFailed: true,
        lastError: action.message,
        connectionStatus: 'error',
      }
    case 'CLEAR_ERROR':
      return { ...state, lastError: null }
    case 'RESET':
      return { ...initialDisplayLiveState }
    case 'EVENT': {
      const { type, payload } = action.message
      const data = asRecord(payload)

      switch (type) {
        case 'connection:ack':
          return {
            ...state,
            connectionStatus: 'connected',
            lastError: null,
            authFailed: false,
          }

        case 'resync': {
          const room = data.room
            ? mapRoom(state.room, asRecord(data.room))
            : state.room
          let question: DisplayLiveQuestion | null = state.question
          if (data.question && typeof data.question === 'object') {
            const qData = asRecord(data.question)
            const nested = qData.question ? asRecord(qData.question) : qData
            const qState =
              (nested.state as SessionQuestionState | undefined) ??
              (qData.state as SessionQuestionState | undefined)
            const reveal = qState === 'Revealed' || qState === 'Scored'
            // Pass the question wrapper (or nested) so mapQuestion can unwrap once.
            const mapped = mapQuestion(qData, state.question, { reveal })
            question = mapped ?? state.question
            if (question) {
              const timerFromPayload =
                (qData.timerEndsAt as string | undefined) ??
                (nested.timerEndsAt as string | undefined) ??
                (asRecord(data.timer).endsAt as string | undefined)
              if (timerFromPayload) {
                question = { ...question, timerEndsAt: timerFromPayload }
              }
            }
          } else if (data.question === null) {
            question = null
          }
          const section = data.section
            ? mapSection(data.section, state.section)
            : state.section
          const leaderboard = parseLeaderboard(data) ?? state.leaderboard
          const podium = parsePodium(data) ?? state.podium
          const resultsReady =
            room?.state === 'Completed' ||
            room?.state === 'Closed' ||
            state.resultsReady
          const participantCount = parseParticipantCount(data, state.participantCount)
          const qPayload =
            data.question && typeof data.question === 'object'
              ? asRecord(data.question)
              : null
          const qState = question?.state
          const isQuestionOpen =
            qState === 'Open' ||
            qState === 'BuzzerOpen' ||
            qState === 'BuzzerLocked' ||
            qState === 'Pending'
          let questionOpenedAt: number | null = null
          if (question && isQuestionOpen) {
            if (typeof data.questionOpenedAt === 'string') {
              questionOpenedAt = new Date(data.questionOpenedAt).getTime()
            } else if (qPayload && typeof qPayload.questionOpenedAt === 'string') {
              questionOpenedAt = new Date(qPayload.questionOpenedAt).getTime()
            } else {
              const timerEndsAt =
                (data.timerEndsAt as string | undefined) ??
                (qPayload?.timerEndsAt as string | undefined)
              const limit = question.timeLimitSeconds
              if (timerEndsAt && limit) {
                const end = new Date(timerEndsAt).getTime()
                if (!Number.isNaN(end)) {
                  questionOpenedAt = end - limit * 1000
                }
              }
            }
          }

          return withViewMode(state, {
            connectionStatus: 'connected',
            room,
            question,
            section,
            leaderboard,
            top3: parseTop3(data) ?? state.top3,
            previousRanks: ranksFromLeaderboard(state.leaderboard),
            podium,
            participantCount,
            resultsReady,
            questionOpenedAt: isQuestionOpen ? questionOpenedAt : null,
            lastError: null,
            authFailed: false,
          })
        }

        case 'participant:count':
          return {
            ...state,
            participantCount: parseParticipantCount(data, state.participantCount),
          }

        case 'answer:submission_count':
        case 'answer:received':
          return {
            ...state,
            submittedCount: parseSubmittedCount(data, state.submittedCount),
            participantCount: parseParticipantCount(data, state.participantCount),
          }

        case 'room:paused':
        case 'room:resumed': {
          const room = mapRoom(state.room, data.room ? asRecord(data.room) : data)
          let question = state.question
          const timerEndsAt =
            (data.timerEndsAt as string | undefined) ??
            (asRecord(data.room).timerEndsAt as string | undefined)
          if (question && typeof timerEndsAt === 'string') {
            question = { ...question, timerEndsAt }
            const limit = question.timeLimitSeconds
            let questionOpenedAt = state.questionOpenedAt
            if (limit) {
              const end = new Date(timerEndsAt).getTime()
              if (!Number.isNaN(end)) {
                questionOpenedAt = end - limit * 1000
              }
            }
            return withViewMode(state, {
              room,
              question,
              questionOpenedAt,
              participantCount: parseParticipantCount(data, state.participantCount),
            })
          }
          return withViewMode(state, {
            room,
            participantCount: parseParticipantCount(data, state.participantCount),
          })
        }

        case 'room:state_changed':
        case 'room:lobbyOpened':
        case 'room:lobbyClosed':
        case 'room:sessionStarted': {
          const room = mapRoom(state.room, data.room ? asRecord(data.room) : data)
          return withViewMode(state, {
            room,
            participantCount: parseParticipantCount(data, state.participantCount),
          })
        }

        case 'room:closed': {
          const room = mapRoom(state.room, data.room ? asRecord(data.room) : data)
          return withViewMode(state, {
            room,
            authFailed: true,
            lastError: String(data.message ?? 'Room is closed'),
          })
        }

        case 'section:started': {
          const section = mapSection(data.section ?? data, state.section)
          const room = mapRoom(state.room, data.room ? asRecord(data.room) : data)
          return withViewMode(state, { section, room })
        }

        case 'section:break': {
          const section = mapSection(data.section ?? data, state.section)
          const roomPatch = data.room ? asRecord(data.room) : { ...data, state: 'SectionBreak' }
          if (!roomPatch.state) roomPatch.state = 'SectionBreak'
          const room = mapRoom(state.room, roomPatch)
          const leaderboard = parseLeaderboard(data) ?? state.leaderboard
          const top3 = parseTop3(data) ?? leaderboard.slice(0, 3)
          return withViewMode(state, {
            section,
            room,
            leaderboard,
            top3,
            sectionStats: parseSectionStats(data),
            previousRanks: ranksFromLeaderboard(state.leaderboard),
            question: state.question
              ? { ...state.question, state: state.question.state ?? 'Scored' }
              : state.question,
          })
        }

        case 'section:continued': {
          const section = mapSection(data.section ?? data, state.section)
          const roomPatch = data.room
            ? asRecord(data.room)
            : { ...data, state: 'Active' as RoomState }
          if (!asRecord(roomPatch).state) {
            ;(roomPatch as Record<string, unknown>).state = 'Active'
          }
          const room = mapRoom(state.room, roomPatch)
          return withViewMode(state, {
            section,
            room,
            question: null,
            sectionStats: null,
            ...questionResetPatch(),
          })
        }

        case 'room:completed':
        case 'quiz:completed': {
          const podium = parsePodium(data) ?? state.podium
          const room = mapRoom(state.room, {
            ...(data.room ? asRecord(data.room) : data),
            state: 'Completed',
          })
          const leaderboard = parseLeaderboard(data) ?? state.leaderboard
          return withViewMode(state, {
            room,
            podium,
            leaderboard,
            top3: parseTop3(data) ?? leaderboard.slice(0, 3),
            sessionHighlights: parseSessionHighlights(data),
            previousRanks: ranksFromLeaderboard(state.leaderboard),
            participantCount: parseParticipantCount(data, state.participantCount),
            resultsReady: true,
          })
        }

        case 'results:ready':
          return withViewMode(state, {
            resultsReady: true,
            podium: parsePodium(data) ?? state.podium,
            leaderboard: parseLeaderboard(data) ?? state.leaderboard,
            sessionHighlights: parseSessionHighlights(data),
            previousRanks: ranksFromLeaderboard(state.leaderboard),
          })

        case 'question:started': {
          const question = mapQuestion(data, null, { reveal: false })
          if (question) {
            question.state = question.state ?? 'Open'
          }
          const section = data.section
            ? mapSection(data.section, state.section)
            : state.section
          const openedAt = action.message.timestamp
            ? new Date(action.message.timestamp).getTime()
            : Date.now()
          return withViewMode(state, {
            question,
            section,
            questionOpenedAt: openedAt,
            ...questionResetPatch(),
            room: mapRoom(state.room, {
              state: state.room?.state === 'Paused' ? 'Paused' : 'Active',
              currentQuestionIndex: question?.index ?? data.questionIndex,
            }),
          })
        }

        case 'question:closed': {
          const question = mapQuestion(data, state.question, { reveal: false })
          if (question) question.state = 'Closed'
          return withViewMode(state, { question })
        }

        case 'question:reveal':
        case 'question:scored': {
          const question = mapQuestion(data, state.question, { reveal: true })
          if (question) {
            question.state = type === 'question:reveal' ? 'Revealed' : 'Scored'
          }
          return withViewMode(state, {
            question,
            optionDistribution: parseOptionDistribution(data),
            explanation:
              typeof data.explanation === 'string' ? data.explanation : null,
            answeredCount:
              typeof data.answeredCount === 'number' ? data.answeredCount : null,
            accuracyPercent:
              typeof data.accuracyPercent === 'number' ? data.accuracyPercent : null,
            showLeaderboardAfterScore: false,
          })
        }

        case 'leaderboard:updated': {
          const leaderboard = parseLeaderboard(data) ?? state.leaderboard
          return withViewMode(state, {
            leaderboard,
            previousRanks: ranksFromLeaderboard(state.leaderboard),
            // Side panel updates in place — do not swap the main stage away from the question/reveal.
            showLeaderboardAfterScore: false,
          })
        }

        case 'error': {
          const code = String(data.code ?? '')
          const message = String(data.message ?? 'WebSocket error')
          if (isAuthFailureCode(code)) {
            return {
              ...state,
              authFailed: true,
              lastError: message,
              connectionStatus: 'error',
            }
          }
          return {
            ...state,
            lastError: message,
          }
        }

        case 'ping':
        case 'pong':
          return state

        default:
          if (data.room) {
            return withViewMode(state, {
              room: mapRoom(state.room, asRecord(data.room)),
            })
          }
          return state
      }
    }
    default:
      return state
  }
}
