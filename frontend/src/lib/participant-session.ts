export interface ParticipantSession {
  sessionToken: string
  roomCode: string
  roomId: string
  displayName: string
  email: string
  quizTitle: string
  participantId: string
}

const KEYS = {
  sessionToken: 'qa_participant_session_token',
  roomCode: 'qa_participant_room_code',
  roomId: 'qa_participant_room_id',
  displayName: 'qa_participant_display_name',
  email: 'qa_participant_email',
  quizTitle: 'qa_participant_quiz_title',
  participantId: 'qa_participant_id',
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

export function getParticipantSession(): ParticipantSession | null {
  const sessionToken = getSessionToken()
  const roomCode = getRoomCode()
  const roomId = getRoomId()
  const displayName = getDisplayName()
  const email = getEmail()
  const quizTitle = getQuizTitle()
  const participantId = getParticipantId()

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
}

export function clearParticipantSession(): void {
  write(KEYS.sessionToken, null)
  write(KEYS.roomCode, null)
  write(KEYS.roomId, null)
  write(KEYS.displayName, null)
  write(KEYS.email, null)
  write(KEYS.quizTitle, null)
  write(KEYS.participantId, null)
}
