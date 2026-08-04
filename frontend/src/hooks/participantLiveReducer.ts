import type {
  AnswerSubmitState,
  LeaderboardEntry,
  LobbySubState,
  ParticipantLiveOption,
  ParticipantLiveQuestion,
  ParticipantSelfSnapshot,
  PersonalScoreFeedback,
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
    hostName?: string
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
  previousLeaderboardRanks: Record<string, number>
  yourRank: number | null
  yourScore: number
  podium: Podium | null
  participantCount: number | null
  submittedCount: number | null
  resultsReady: boolean
  lastFeedback: PersonalScoreFeedback | null
  cumulativeTimeBonus: number
  cumulativeStreakBonus: number
  showLeaderboardInterstitial: boolean
  lastError: string | null
  isOffline: boolean
  questionOpenedAt: string | null
  authFailed: boolean
}

export type ParticipantLiveAction =
  | { type: 'STATUS'; status: WsConnectionStatus }
  | { type: 'ERROR'; message: string }
  | { type: 'AUTH_FAILED'; message: string }
  | { type: 'CLEAR_ERROR' }
  | { type: 'RESET' }
  | { type: 'SET_OFFLINE'; offline: boolean }
  | { type: 'SELECT_OPTIONS'; optionIds: string[] }
  | { type: 'SUBMIT_START'; optionIds: string[] }
  | {
      type: 'SEED_SESSION'
      participantId: string
      displayName?: string
      roomId?: string
      roomState?: RoomState
      quizTitle?: string
      roomCode?: string
    }
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
  previousLeaderboardRanks: {},
  yourRank: null,
  yourScore: 0,
  podium: null,
  participantCount: null,
  submittedCount: null,
  resultsReady: false,
  lastFeedback: null,
  cumulativeTimeBonus: 0,
  cumulativeStreakBonus: 0,
  showLeaderboardInterstitial: false,
  lastError: null,
  isOffline: typeof navigator !== 'undefined' ? !navigator.onLine : false,
  questionOpenedAt: null,
  authFailed: false,
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

export type QuizPhase =
  | 'waiting'
  | 'answering'
  | 'closed'
  | 'scoring'
  | 'feedback'
  | 'leaderboard'
  | 'completed'

function canInferCorrectnessFromOptions(options: ParticipantLiveOption[]): boolean {
  return options.some((option) => option.isCorrect === true)
}

export function deriveQuizPhase(state: ParticipantLiveState): QuizPhase {
  if (
    state.resultsReady ||
    state.room?.state === 'Completed' ||
    state.room?.state === 'Closed'
  ) {
    return 'completed'
  }
  if (state.showLeaderboardInterstitial && state.leaderboard.length > 0) {
    return 'leaderboard'
  }
  if (!state.question) return 'waiting'
  const qState = state.question.state
  const options = state.options.length ? state.options : state.question.options
  const hasPersonalFeedback = state.lastFeedback?.questionId === state.question.id

  if (qState === 'Revealed' || qState === 'Scored') {
    if (hasPersonalFeedback) return 'feedback'
    if (canInferCorrectnessFromOptions(options)) return 'feedback'
    return 'scoring'
  }
  if (qState === 'Closed' || qState === 'BuzzerLocked') {
    return 'closed'
  }
  return 'answering'
}

function deriveTimerEndsAt(
  timerEndsAt: string | null | undefined,
  timeLimitSeconds: number | null | undefined,
  openedAt: string | null | undefined,
): string | null {
  if (timerEndsAt) return timerEndsAt
  if (timeLimitSeconds && openedAt) {
    const start = new Date(openedAt).getTime()
    if (!Number.isNaN(start)) {
      return new Date(start + timeLimitSeconds * 1000).toISOString()
    }
  }
  return null
}

function stripEmailsFromLeaderboard(
  entries: LeaderboardEntry[],
  opts: { includeCorrectness?: boolean } = {},
): LeaderboardEntry[] {
  const includeCorrectness = Boolean(opts.includeCorrectness)
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
      ...(includeCorrectness ? { lastIsCorrect } : {}),
    }),
  )
}

export function ranksFromLeaderboard(
  entries: LeaderboardEntry[],
): Record<string, number> {
  const map: Record<string, number> = {}
  for (const entry of entries) {
    map[entry.participantId] = entry.rank
  }
  return map
}

function parsePersonalFeedback(data: Record<string, unknown>): PersonalScoreFeedback {
  return {
    questionId: String(data.questionId ?? ''),
    questionIndex:
      typeof data.questionIndex === 'number' ? data.questionIndex : 0,
    isCorrect: Boolean(data.isCorrect),
    isUnanswered: Boolean(data.isUnanswered),
    basePoints: typeof data.basePoints === 'number' ? data.basePoints : 0,
    timeBonus: typeof data.timeBonus === 'number' ? data.timeBonus : 0,
    streakBonus: typeof data.streakBonus === 'number' ? data.streakBonus : 0,
    pointsEarned: typeof data.pointsEarned === 'number' ? data.pointsEarned : 0,
    totalScore: typeof data.totalScore === 'number' ? data.totalScore : 0,
    streak: typeof data.streak === 'number' ? data.streak : 0,
  }
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
      (nested.timerEndsAt as string | null | undefined) ??
      (payload.timerEndsAt as string | null | undefined) ??
      existing?.timerEndsAt ??
      null,
    basePoints:
      typeof nested.basePoints === 'number' ? nested.basePoints : existing?.basePoints,
    allowMultipleCorrect:
      typeof nested.allowMultipleCorrect === 'boolean'
        ? nested.allowMultipleCorrect
        : existing?.allowMultipleCorrect,
    mediaFileId:
      (nested.mediaFileId as string | null | undefined) ?? existing?.mediaFileId ?? null,
    imageUrl:
      (nested.imageUrl as string | null | undefined) ?? existing?.imageUrl ?? null,
    explanation:
      (nested.explanation as string | null | undefined) ??
      existing?.explanation ??
      null,
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
    hostName: String(patch.hostName ?? existing?.hostName ?? 'Host'),
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

function parseLeaderboard(
  data: Record<string, unknown>,
  opts: { includeCorrectness?: boolean } = {},
): LeaderboardEntry[] | null {
  if (Array.isArray(data.entries)) {
    return stripEmailsFromLeaderboard(data.entries as LeaderboardEntry[], opts)
  }
  if (Array.isArray(data.leaderboard)) {
    return stripEmailsFromLeaderboard(data.leaderboard as LeaderboardEntry[], opts)
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

function applyTerminalRoom(
  state: ParticipantLiveState,
  data: Record<string, unknown>,
  terminalState: 'Completed' | 'Closed',
): ParticipantLiveState {
  const roomPatch = data.room ? asRecord(data.room) : { ...data, state: terminalState }
  if (!roomPatch.state) roomPatch.state = terminalState
  if (!roomPatch.id && !roomPatch.roomId && state.room) {
    roomPatch.id = state.room.id
    roomPatch.roomCode = state.room.roomCode
    roomPatch.quizTitle = state.room.quizTitle
  }
  const mapped = mapRoom(state.room, roomPatch)
  const room = mapped
    ? { ...mapped, state: terminalState }
    : state.room
      ? { ...state.room, state: terminalState }
      : {
          id: String(data.roomId ?? roomPatch.roomId ?? 'room'),
          roomCode: String(roomPatch.roomCode ?? ''),
          state: terminalState,
          quizTitle: String(roomPatch.quizTitle ?? ''),
        }
  const leaderboard = parseLeaderboard(data) ?? state.leaderboard
  const podium = parsePodium(data) ?? state.podium
  const selfId = state.self?.id
  const own = selfId ? leaderboard.find((e) => e.participantId === selfId) : undefined
  return {
    ...state,
    room,
    podium,
    leaderboard,
    resultsReady: true,
    showLeaderboardInterstitial: false,
    question: null,
    options: [],
    questionOpenedAt: null,
    yourRank: own?.rank ?? state.yourRank,
    yourScore: own?.score ?? state.yourScore,
    previousLeaderboardRanks: ranksFromLeaderboard(state.leaderboard),
    participantCount:
      typeof data.participantCount === 'number'
        ? data.participantCount
        : state.participantCount,
  }
}

export function participantLiveReducer(
  state: ParticipantLiveState,
  action: ParticipantLiveAction,
): ParticipantLiveState {
  switch (action.type) {
    case 'STATUS':
      if (state.connectionStatus === action.status) return state
      return { ...state, connectionStatus: action.status }
    case 'ERROR':
      return { ...state, lastError: action.message, connectionStatus: 'error' }
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
      return {
        ...initialParticipantLiveState,
        isOffline: state.isOffline,
      }
    case 'SET_OFFLINE':
      return { ...state, isOffline: action.offline }
    case 'SEED_SESSION': {
      const self =
        state.self ??
        ({
          id: action.participantId,
          displayName: action.displayName ?? 'You',
          totalScore: 0,
          streak: 0,
        } as ParticipantSelfSnapshot)
      const room =
        state.room ??
        (action.roomId && action.roomState
          ? {
              id: action.roomId,
              roomCode: action.roomCode ?? '',
              state: action.roomState,
              quizTitle: action.quizTitle ?? '',
            }
          : state.room)
      return {
        ...state,
        self: state.self
          ? state.self
          : { ...self, id: action.participantId },
        room,
        resultsReady:
          action.roomState === 'Completed' ||
          action.roomState === 'Closed' ||
          state.resultsReady,
      }
    }
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
          const qData = data.question ? asRecord(data.question) : null
          const nestedQ = qData?.question ? asRecord(qData.question) : qData
          const revealState =
            (nestedQ?.state as string | undefined) ??
            (qData?.state as string | undefined)
          const reveal =
            revealState === 'Revealed' || revealState === 'Scored'
          const question = qData
            ? mapQuestion(
                asRecord(data.question),
                state.question,
                {
                  reveal,
                },
              )
            : null
          const openedAt =
            (data.questionOpenedAt as string | undefined) ??
            (qData?.questionOpenedAt as string | undefined) ??
            state.questionOpenedAt
          const resolvedOpenedAt =
            question &&
            (question.state === 'Open' ||
              question.state === 'BuzzerOpen' ||
              question.state === 'BuzzerLocked')
              ? openedAt
              : null
          if (question) {
            const timerFromPayload =
              (asRecord(data.timer).endsAt as string | undefined) ??
              (qData?.timerEndsAt as string | undefined) ??
              (data.timerEndsAt as string | undefined) ??
              question.timerEndsAt
            question.timerEndsAt = deriveTimerEndsAt(
              timerFromPayload,
              question.timeLimitSeconds,
              resolvedOpenedAt,
            )
          }
          const rawSubmission =
            (data.submission as SubmissionStatus) ??
            (asRecord(data.participant).submission as SubmissionStatus) ??
            null
          let submissionPatch = applySubmissionStatus(state, rawSubmission)
          if (state.submissionStatus === 'submitting' && !rawSubmission) {
            submissionPatch = {
              submissionStatus: 'idle',
              submissionError: null,
            }
          } else if (
            state.submissionStatus === 'submitting' &&
            rawSubmission &&
            !asRecord(rawSubmission).hasSubmitted
          ) {
            submissionPatch = {
              submissionStatus: 'idle',
              submissionError: null,
              selectedOptionIds: state.selectedOptionIds,
            }
          }
          const leaderboard =
            parseLeaderboard(data, { includeCorrectness: reveal }) ??
            state.leaderboard
          const podium = parsePodium(data) ?? state.podium
          const resultsReady =
            room?.state === 'Completed' ||
            room?.state === 'Closed' ||
            state.resultsReady
          const yourRank =
            typeof self?.rank === 'number' ? self.rank : state.yourRank
          const yourScore = self?.totalScore ?? state.yourScore
          const participantCount =
            typeof data.participantCount === 'number'
              ? data.participantCount
              : state.participantCount

          return {
            ...state,
            connectionStatus: 'connected',
            room,
            self,
            question: resultsReady ? null : question,
            options: resultsReady ? [] : (question?.options ?? []),
            questionOpenedAt: resultsReady ? null : resolvedOpenedAt,
            leaderboard,
            podium,
            resultsReady,
            showLeaderboardInterstitial: resultsReady
              ? false
              : state.showLeaderboardInterstitial,
            previousLeaderboardRanks: ranksFromLeaderboard(state.leaderboard),
            yourRank,
            yourScore,
            participantCount,
            lastError: null,
            ...submissionPatch,
          }
        }

        case 'participant:count':
          return {
            ...state,
            participantCount:
              typeof data.participantCount === 'number'
                ? data.participantCount
                : state.participantCount,
          }

        case 'score:personal': {
          const feedback = parsePersonalFeedback(data)
          return {
            ...state,
            lastFeedback: feedback,
            yourScore: feedback.totalScore,
            cumulativeTimeBonus: state.cumulativeTimeBonus + feedback.timeBonus,
            cumulativeStreakBonus: state.cumulativeStreakBonus + feedback.streakBonus,
            self: state.self
              ? {
                  ...state.self,
                  totalScore: feedback.totalScore,
                  streak: feedback.streak,
                }
              : state.self,
          }
        }

        case 'room:paused':
        case 'room:resumed': {
          const room = mapRoom(state.room, data.room ? asRecord(data.room) : data)
          const timerEndsAt =
            (data.timerEndsAt as string | undefined) ??
            (asRecord(data.room).timerEndsAt as string | undefined)
          const question =
            state.question && typeof timerEndsAt === 'string'
              ? { ...state.question, timerEndsAt }
              : state.question
          return {
            ...state,
            room,
            question,
            participantCount:
              typeof data.participantCount === 'number'
                ? data.participantCount
                : state.participantCount,
          }
        }

        case 'room:state_changed':
        case 'room:lobbyOpened':
        case 'room:lobbyClosed':
        case 'room:sessionStarted':
        case 'section:continued':
        case 'section:started': {
          const patch = data.room ? asRecord(data.room) : data
          const nextState = String(patch.state ?? '')
          if (nextState === 'Completed' || nextState === 'Closed') {
            return applyTerminalRoom(
              state,
              patch,
              nextState === 'Closed' ? 'Closed' : 'Completed',
            )
          }
          return {
            ...state,
            room: mapRoom(state.room, patch),
            participantCount:
              typeof data.participantCount === 'number'
                ? data.participantCount
                : state.participantCount,
          }
        }

        case 'room:closed':
          return applyTerminalRoom(state, data, 'Closed')

        case 'section:break': {
          const roomPatch = data.room
            ? asRecord(data.room)
            : { ...data, state: 'SectionBreak' }
          if (!roomPatch.state) roomPatch.state = 'SectionBreak'
          return {
            ...state,
            room: mapRoom(state.room, roomPatch),
            showLeaderboardInterstitial: false,
            leaderboard: parseLeaderboard(data) ?? state.leaderboard,
            participantCount:
              typeof data.participantCount === 'number'
                ? data.participantCount
                : state.participantCount,
          }
        }

        case 'room:completed':
        case 'quiz:completed':
          return applyTerminalRoom(state, data, 'Completed')

        case 'results:ready':
          return {
            ...state,
            resultsReady: true,
            showLeaderboardInterstitial: false,
            podium: parsePodium(data) ?? state.podium,
            leaderboard: parseLeaderboard(data) ?? state.leaderboard,
          }

        case 'question:started': {
          const openedAt = action.message.timestamp
          const question = mapQuestion(data, null, { reveal: false })
          if (question) {
            question.state = question.state ?? 'Open'
            question.timerEndsAt = deriveTimerEndsAt(
              (data.timerEndsAt as string | undefined) ??
                (asRecord(data.question).timerEndsAt as string | undefined) ??
                question.timerEndsAt,
              question.timeLimitSeconds,
              openedAt,
            )
          }
          return {
            ...state,
            question,
            options: question?.options ?? [],
            questionOpenedAt: openedAt,
            submissionStatus: 'idle',
            submissionError: null,
            selectedOptionIds: [],
            submittedCount: 0,
            lastFeedback: null,
            showLeaderboardInterstitial: false,
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
          const leaderboard =
            parseLeaderboard(data, { includeCorrectness: state.reveal }) ??
            state.leaderboard
          const selfId = state.self?.id
          const own = selfId
            ? leaderboard.find((e) => e.participantId === selfId)
            : undefined
          return {
            ...state,
            leaderboard,
            previousLeaderboardRanks: ranksFromLeaderboard(state.leaderboard),
            yourRank: own?.rank ?? state.yourRank,
            yourScore: own?.score ?? state.yourScore,
            // Persistent side/top panel — no full-screen interstitial mid-quiz.
            showLeaderboardInterstitial: false,
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

        case 'error': {
          const code = String(data.code ?? '')
          if (
            code === 'AUTH_ERROR' ||
            code === 'ROOM_CLOSED' ||
            code === 'FORBIDDEN' ||
            code === 'UNAUTHORIZED' ||
            code === 'INVALID_PARTICIPANT_TOKEN'
          ) {
            return {
              ...state,
              authFailed: true,
              lastError: String(data.message ?? 'Authentication failed'),
              connectionStatus: 'error',
            }
          }
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
