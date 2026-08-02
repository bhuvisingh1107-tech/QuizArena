export interface ParticipantSession {
  sessionToken: string
  roomCode: string
  roomId: string
  displayName: string
  email: string
  quizTitle: string
  participantId: string
  roomState?: import('@/types/api').RoomState
}

const KEYS = {
  sessionToken: 'qa_participant_session_token',
  roomCode: 'qa_participant_room_code',
  roomId: 'qa_participant_room_id',
  displayName: 'qa_participant_display_name',
  email: 'qa_participant_email',
  quizTitle: 'qa_participant_quiz_title',
  participantId: 'qa_participant_id',
  roomState: 'qa_participant_room_state',
} as const

function read(key: string): string | null {
  try {
    return sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) {
      sessionStorage.removeItem(key)
    } else {
      sessionStorage.setItem(key, value)
    }
  } catch {
    // sessionStorage may be unavailable
  }
}

export function getSessionToken(): string | null {
  return read(KEYS.sessionToken)
}

export function setSessionToken(token: string): void {
  write(KEYS.sessionToken, token)
}

export function getRoomCode(): string | null {
  return read(KEYS.roomCode)
}

export function setRoomCode(roomCode: string): void {
  write(KEYS.roomCode, roomCode)
}

export function getRoomId(): string | null {
  return read(KEYS.roomId)
}

export function setRoomId(roomId: string): void {
  write(KEYS.roomId, roomId)
}

export function getDisplayName(): string | null {
  return read(KEYS.displayName)
}

export function setDisplayName(displayName: string): void {
  write(KEYS.displayName, displayName)
}

export function getEmail(): string | null {
  return read(KEYS.email)
}

export function setEmail(email: string): void {
  write(KEYS.email, email)
}

export function getQuizTitle(): string | null {
  return read(KEYS.quizTitle)
}

export function setQuizTitle(quizTitle: string): void {
  write(KEYS.quizTitle, quizTitle)
}

export function getParticipantId(): string | null {
  return read(KEYS.participantId)
}

export function setParticipantId(participantId: string): void {
  write(KEYS.participantId, participantId)
}

export function getRoomState(): import('@/types/api').RoomState | null {
  const value = read(KEYS.roomState)
  return (value as import('@/types/api').RoomState | null) ?? null
}

export function setRoomState(roomState: import('@/types/api').RoomState | null): void {
  write(KEYS.roomState, roomState)
}

export function getParticipantSession(): ParticipantSession | null {
  const sessionToken = getSessionToken()
  const roomCode = getRoomCode()
  const roomId = getRoomId()
  const displayName = getDisplayName()
  const email = getEmail()
  const quizTitle = getQuizTitle()
  const participantId = getParticipantId()
  const roomState = getRoomState() ?? undefined

  if (
    !sessionToken ||
    !roomCode ||
    !roomId ||
    !displayName ||
    !email ||
    !quizTitle ||
    !participantId
  ) {
    return null
  }

  return {
    sessionToken,
    roomCode,
    roomId,
    displayName,
    email,
    quizTitle,
    participantId,
    roomState,
  }
}

export function setParticipantSession(session: ParticipantSession): void {
  setSessionToken(session.sessionToken)
  setRoomCode(session.roomCode)
  setRoomId(session.roomId)
  setDisplayName(session.displayName)
  setEmail(session.email)
  setQuizTitle(session.quizTitle)
  setParticipantId(session.participantId)
  setRoomState(session.roomState ?? null)
}

export function clearParticipantSession(): void {
  write(KEYS.sessionToken, null)
  write(KEYS.roomCode, null)
  write(KEYS.roomId, null)
  write(KEYS.displayName, null)
  write(KEYS.email, null)
  write(KEYS.quizTitle, null)
  write(KEYS.participantId, null)
  write(KEYS.roomState, null)
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('qa:participant-session-cleared'))
  }
}
