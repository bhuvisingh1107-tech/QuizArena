/** Shared API types matching backend camelCase aliases. */

export type QuizStatus = 'Draft' | 'Ready' | 'InUse' | 'Archived' | 'Deleted'

export type QuestionType = 'Text' | 'Image' | 'Audio' | 'Buzzer'

export type QuestionAdvanceMode = 'manual' | 'automatic'

export type AnswerRevealBehavior = 'after_each' | 'session_end'

export type RoomState =
  | 'Setup'
  | 'Lobby'
  | 'Active'
  | 'Paused'
  | 'SectionBreak'
  | 'Completed'
  | 'Closed'

export type LobbySubState = 'LobbyOpen' | 'LobbyClosed'

export type MediaCategory =
  | 'question_image'
  | 'question_audio'
  | 'quiz_branding'
  | 'platform_branding'

export type AdminRole = 'admin'

export type ParticipantState =
  | 'Joining'
  | 'InLobby'
  | 'Active'
  | 'Answering'
  | 'Buzzing'
  | 'BuzzUnlocked'
  | 'Answered'
  | 'Waiting'
  | 'Disconnected'
  | 'Reconnecting'
  | 'Kicked'
  | 'Banned'
  | 'SessionEnded'

export type SessionQuestionState =
  | 'Pending'
  | 'Open'
  | 'BuzzerOpen'
  | 'BuzzerLocked'
  | 'Closed'
  | 'Revealed'
  | 'Scored'

export interface ApiMeta {
  requestId?: string | null
  cursor?: string | null
  hasMore?: boolean | null
}

export interface ApiEnvelope<T> {
  data: T
  meta?: ApiMeta | null
}

export interface ApiErrorDetail {
  code: string
  message: string
  details?: unknown[]
}

export interface ApiErrorBody {
  error: ApiErrorDetail
  meta?: ApiMeta
}

export interface QuizConfig {
  questionAdvanceMode: QuestionAdvanceMode
  answerRevealBehavior: AnswerRevealBehavior
  timeBonusEnabled: boolean
  timeBonusMaxPoints: number
  streakBonusEnabled: boolean
  streakBonusRules?: Record<string, unknown> | null
  questionOrderShuffle: boolean
  answerOptionShuffle: boolean
}

export interface Quiz {
  id: string
  title: string
  description?: string | null
  status: QuizStatus
  brandingMediaFileId?: string | null
  config?: QuizConfig | null
  createdAt: string
  updatedAt: string
}

export interface QuizCreateInput {
  title: string
  description?: string | null
  config?: Partial<QuizConfig> | null
}

export interface QuizUpdateInput {
  title?: string
  description?: string | null
  config?: Partial<QuizConfig> | null
}

export interface PaginatedQuizzes {
  items: Quiz[]
  total: number
  offset: number
  limit: number
}

export interface QuizDeleteResult {
  id: string
  deleted: boolean
  hard: boolean
  status?: QuizStatus | null
}

export interface Section {
  id: string
  quizId: string
  name: string
  sortOrder: number
  createdAt: string
  updatedAt: string
}

export interface SectionCreateInput {
  name: string
  sortOrder?: number | null
}

export interface SectionUpdateInput {
  name?: string
  sortOrder?: number | null
}

export interface SectionList {
  items: Section[]
  total: number
}

export interface Question {
  id: string
  sectionId: string
  questionType: QuestionType
  promptText?: string | null
  explanation?: string | null
  mediaFileId?: string | null
  basePoints: number
  timeLimitSeconds?: number | null
  allowMultipleCorrect: boolean
  sortOrder: number
  createdAt: string
  updatedAt: string
}

export interface QuestionCreateInput {
  questionType: QuestionType
  promptText: string
  explanation?: string | null
  basePoints?: number
  timeLimitSeconds?: number | null
  allowMultipleCorrect?: boolean
  sortOrder?: number | null
}

export interface QuestionUpdateInput {
  questionType?: QuestionType
  promptText?: string
  explanation?: string | null
  basePoints?: number
  timeLimitSeconds?: number | null
  allowMultipleCorrect?: boolean
  sortOrder?: number | null
  clearMedia?: boolean
}

export interface QuestionList {
  items: Question[]
  total: number
}

export interface AnswerOption {
  id: string
  questionId: string
  text: string
  isCorrect: boolean
  sortOrder: number
  createdAt: string
  updatedAt: string
}

export interface AnswerOptionCreateInput {
  text: string
  isCorrect?: boolean
  sortOrder?: number | null
}

export interface AnswerOptionUpdateInput {
  text?: string
  isCorrect?: boolean
  sortOrder?: number | null
}

export interface AnswerOptionList {
  items: AnswerOption[]
  total: number
}

export interface MediaFile {
  id: string
  category: MediaCategory
  mimeType: string
  fileSize: number
  originalFilename?: string | null
  quizId?: string | null
  url: string
  createdAt: string
  updatedAt: string
}

export interface MediaList {
  items: MediaFile[]
  total: number
}

export interface MediaApplyToAllResult {
  mediaId: string
  mediaFileId: string
  quizId: string
  updatedCount: number
  skippedCount: number
  questionIds: string[]
}

export interface MediaRemoveFromAllResult {
  mediaId: string
  quizId: string
  clearedCount: number
}

export interface RoomConfig {
  id: string
  questionAdvanceMode: QuestionAdvanceMode
  answerRevealBehavior: AnswerRevealBehavior
  timeBonusEnabled: boolean
  timeBonusMaxPoints: number
  streakBonusEnabled: boolean
  streakBonusRules?: Record<string, unknown> | null
  questionOrderShuffle: boolean
  answerOptionShuffle: boolean
}

export interface RoomConfigInput {
  questionAdvanceMode?: QuestionAdvanceMode | null
  answerRevealBehavior?: AnswerRevealBehavior | null
  timeBonusEnabled?: boolean | null
  timeBonusMaxPoints?: number | null
  streakBonusEnabled?: boolean | null
  streakBonusRules?: Record<string, unknown> | null
  questionOrderShuffle?: boolean | null
  answerOptionShuffle?: boolean | null
}

export interface LiveRoom {
  id: string
  quizId: string
  state: RoomState
  lobbySubState?: LobbySubState | null
  roomCode: string
  secretToken: string
  quizTitleSnapshot: string
  currentQuestionIndex?: number | null
  codesExpired: boolean
  awaitingHostAdvance?: boolean
  joinUrl: string
  displayUrl: string
  qrTarget: string
  config?: RoomConfig | null
  sectionCount: number
  questionCount: number
  startedAt?: string | null
  completedAt?: string | null
  closedAt?: string | null
  createdAt: string
  updatedAt: string
  /** Present on some WS room snapshots / resync payloads. */
  questionAdvanceMode?: QuestionAdvanceMode | null
}

export interface LiveRoomCreateInput {
  quizId: string
  config?: RoomConfigInput | null
}

export interface PaginatedLiveRooms {
  items: LiveRoom[]
  total: number
}

export interface LiveRoomDeleteResult {
  id: string
  deleted: boolean
}

export interface Admin {
  id: string
  username: string
  name?: string
  email?: string | null
  role: AdminRole
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  name: string
  email: string
  username: string
  password: string
  confirmPassword?: string
}

export interface LoginResponse {
  accessToken: string
  expiresAt: string
}

export interface LeaderboardEntry {
  rank: number
  participantId: string
  displayName: string
  score: number
  streak?: number
  timeBonus?: number
  lastTimeBonus?: number
  lastIsCorrect?: boolean | null
}

export interface PodiumEntry {
  rank: 1 | 2 | 3
  participantId: string
  displayName: string
  score: number
}

export interface Podium {
  entries: PodiumEntry[]
}

export interface LiveParticipant {
  id: string
  displayName: string
  email?: string | null
  state: ParticipantState
  score?: number
  connected?: boolean
}

export interface LiveQuestionSnapshot {
  id: string
  index: number
  promptText?: string | null
  questionType?: QuestionType
  state?: SessionQuestionState
  timeLimitSeconds?: number | null
  timerEndsAt?: string | null
  basePoints?: number
  options?: Array<{
    id: string
    text: string
    sortOrder: number
  }>
}

export interface WsMessage<T = Record<string, unknown>> {
  type: string
  payload: T
  timestamp: string
}

export interface ConnectionStatus {
  status: 'connecting' | 'connected' | 'disconnected' | 'error'
}

/** Participant join / session types */

export interface JoinRequest {
  roomCode: string
  displayName: string
  email: string
}

export interface ParticipantProfile {
  id: string
  liveRoomId: string
  displayName: string
  email: string
  state: ParticipantState
  connectionStatus: string
  totalScore: number
  streak: number
  rank?: number | null
  totalCorrect: number
  totalIncorrect: number
  unansweredCount: number
  joinedAt: string
  createdAt: string
  updatedAt: string
}

export interface JoinRoomMeta {
  id: string
  roomCode: string
  state: RoomState
  lobbySubState?: LobbySubState | null
  quizTitle: string
  codesExpired: boolean
}

export interface JoinResponse {
  sessionToken: string
  participant: ParticipantProfile
  room: JoinRoomMeta
  restored: boolean
}

export interface LeaveResponse {
  id: string
  left: boolean
  state: ParticipantState
}

export interface SubmissionStatus {
  hasSubmitted: boolean
  questionId?: string | null
  questionIndex?: number | null
  questionState?: SessionQuestionState | string | null
  selectedOptionIds?: string[] | null
  status?: string | null
  submittedAt?: string | null
}

export type AnswerSubmitState =
  | 'idle'
  | 'selecting'
  | 'submitting'
  | 'submitted'
  | 'rejected'
  | 'already_submitted'

export interface ParticipantLiveOption {
  id: string
  text: string
  sortOrder: number
  isCorrect?: boolean
}

export interface ParticipantLiveQuestion {
  id: string
  index: number
  promptText?: string | null
  explanation?: string | null
  questionType?: QuestionType
  state?: SessionQuestionState
  timeLimitSeconds?: number | null
  timerEndsAt?: string | null
  basePoints?: number
  allowMultipleCorrect?: boolean
  mediaFileId?: string | null
  /** WS path/URL for question media (no bytes). Prefer over reconstructing from mediaFileId. */
  imageUrl?: string | null
  sectionId?: string | null
  sectionName?: string | null
  totalQuestions?: number | null
  options: ParticipantLiveOption[]
  isAcceptingAnswers?: boolean
}

export interface PersonalScoreFeedback {
  questionId: string
  questionIndex: number
  isCorrect: boolean
  isUnanswered: boolean
  basePoints: number
  timeBonus: number
  streakBonus: number
  pointsEarned: number
  totalScore: number
  streak: number
}

export interface ParticipantSelfSnapshot {
  id: string
  displayName: string
  state?: ParticipantState
  connectionStatus?: string
  totalScore: number
  streak: number
  rank?: number | null
  totalCorrect?: number
  totalIncorrect?: number
  unansweredCount?: number
  email?: string
}

/** Admin dashboard */

export interface DashboardSummary {
  quizzesTotal: number
  quizzesDraft: number
  quizzesReady: number
  quizzesInUse: number
  quizzesArchived: number
  roomsActive: number
  roomsCompleted: number
  participantsToday: number
}

/** Admin room participants */

export interface AdminParticipant {
  id: string
  displayName: string
  email: string
  state: ParticipantState
  connectionStatus: string
  totalScore: number
  streak: number
  rank?: number | null
  totalCorrect: number
  totalIncorrect: number
  unansweredCount: number
  joinedAt: string
}

export interface AdminParticipantList {
  items: AdminParticipant[]
  total: number
}

/** Room results & analytics */

export interface ResultsRoom {
  id: string
  roomCode: string
  quizTitleSnapshot: string
  state: RoomState
  startedAt?: string | null
  completedAt?: string | null
}

export interface ResultsSummary {
  participantCount: number
  averageScore: number
  averageAccuracyPercent: number
  totalQuestions: number
  averageResponseTimeMs?: number | null
}

export interface ResultsLeaderboardEntry {
  rank: number
  participantId: string
  displayName: string
  score: number
  streak: number
  totalCorrect: number
  totalIncorrect: number
  unansweredCount: number
}

export interface ResultsPodium {
  entries: ResultsLeaderboardEntry[]
}

export interface OptionDistribution {
  optionId: string
  text: string
  selectedCount: number
  isCorrect: boolean
}

export interface QuestionAnalytics {
  questionId: string
  questionIndex: number
  promptText?: string | null
  sectionName: string
  submissionCount: number
  correctCount: number
  incorrectCount: number
  unansweredCount: number
  accuracyPercent: number
  averageResponseTimeMs?: number | null
  optionDistribution: OptionDistribution[]
}

export interface SectionAnalytics {
  sectionId: string
  name: string
  averageScore: number
  questionCount: number
}

export interface RoomResults {
  room: ResultsRoom
  summary: ResultsSummary
  leaderboard: ResultsLeaderboardEntry[]
  podium: ResultsPodium
  questionAnalytics: QuestionAnalytics[]
  sectionAnalytics: SectionAnalytics[]
}

/** Auth: change password */

export interface ChangePasswordRequest {
  currentPassword: string
  newPassword: string
}

export interface ChangePasswordResponse {
  message: string
}

export type AdminTheme = 'light' | 'dark'
