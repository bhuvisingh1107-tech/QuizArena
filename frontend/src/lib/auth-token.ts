const TOKEN_KEY = 'qa_admin_token'
const EXPIRES_KEY = 'qa_admin_expires_at'

let memoryToken: string | null = null
let memoryExpiresAt: string | null = null

function readSession(key: string): string | null {
  try {
    return sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function writeSession(key: string, value: string | null): void {
  try {
    if (value === null) {
      sessionStorage.removeItem(key)
    } else {
      sessionStorage.setItem(key, value)
    }
  } catch {
    // sessionStorage may be unavailable (private mode / SSR)
  }
}

export function getToken(): string | null {
  if (memoryToken) return memoryToken
  const stored = readSession(TOKEN_KEY)
  if (stored) {
    memoryToken = stored
  }
  return memoryToken
}

export function setToken(token: string): void {
  memoryToken = token
  writeSession(TOKEN_KEY, token)
}

export function clearToken(): void {
  memoryToken = null
  memoryExpiresAt = null
  writeSession(TOKEN_KEY, null)
  writeSession(EXPIRES_KEY, null)
}

export function getExpiresAt(): string | null {
  if (memoryExpiresAt) return memoryExpiresAt
  const stored = readSession(EXPIRES_KEY)
  if (stored) {
    memoryExpiresAt = stored
  }
  return memoryExpiresAt
}

export function setExpiresAt(expiresAt: string): void {
  memoryExpiresAt = expiresAt
  writeSession(EXPIRES_KEY, expiresAt)
}
