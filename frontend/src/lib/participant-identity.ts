const IDENTITY_EMAIL_KEY = 'qa_participant_identity_email'
const REMEMBERED_NAME_KEY = 'qa_remembered_display_name'

function readLocal(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeLocal(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // localStorage may be unavailable
  }
}

export function getOrCreateAnonymousEmail(): string {
  const existing = readLocal(IDENTITY_EMAIL_KEY)
  if (existing) return existing

  const uuid =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`
  const email = `player-${uuid}@participants.local`
  writeLocal(IDENTITY_EMAIL_KEY, email)
  return email
}

export function getRememberedDisplayName(): string {
  return readLocal(REMEMBERED_NAME_KEY) ?? ''
}

export function setRememberedDisplayName(displayName: string): void {
  const trimmed = displayName.trim()
  if (!trimmed) return
  writeLocal(REMEMBERED_NAME_KEY, trimmed)
}
