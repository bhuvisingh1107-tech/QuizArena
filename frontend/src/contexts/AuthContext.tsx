import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { apiGet, apiPost } from '@/lib/api-client'
import {
  clearToken,
  getExpiresAt,
  getToken,
  setExpiresAt,
  setToken,
} from '@/lib/auth-token'
import type { Admin, LoginRequest, LoginResponse, RegisterRequest } from '@/types/api'

interface AuthContextValue {
  admin: Admin | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (credentials: LoginRequest) => Promise<void>
  register: (payload: RegisterRequest) => Promise<void>
  logout: () => Promise<void>
  refreshAdmin: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

async function persistSession(result: LoginResponse, setAdmin: (admin: Admin) => void) {
  setToken(result.accessToken)
  setExpiresAt(result.expiresAt)
  const me = await apiGet<Admin>('/admin/me')
  setAdmin(me)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<Admin | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshAdmin = useCallback(async () => {
    const token = getToken()
    if (!token) {
      setAdmin(null)
      return
    }
    const me = await apiGet<Admin>('/admin/me')
    setAdmin(me)
  }, [])

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      const token = getToken()
      if (!token) {
        if (!cancelled) {
          setAdmin(null)
          setIsLoading(false)
        }
        return
      }

      const expiresAt = getExpiresAt()
      if (expiresAt && new Date(expiresAt).getTime() <= Date.now()) {
        clearToken()
        if (!cancelled) {
          setAdmin(null)
          setIsLoading(false)
        }
        return
      }

      try {
        const me = await apiGet<Admin>('/admin/me')
        if (!cancelled) setAdmin(me)
      } catch {
        clearToken()
        if (!cancelled) setAdmin(null)
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  // Mid-session JWT expiry: clear auth so REST and WS stop acting as logged-in.
  useEffect(() => {
    if (!admin) return
    const expiresAt = getExpiresAt()
    if (!expiresAt) return
    const ms = new Date(expiresAt).getTime() - Date.now()
    if (ms <= 0) {
      clearToken()
      setAdmin(null)
      return
    }
    const id = window.setTimeout(() => {
      clearToken()
      setAdmin(null)
    }, ms)
    return () => window.clearTimeout(id)
  }, [admin])

  const login = useCallback(async (credentials: LoginRequest) => {
    const result = await apiPost<LoginResponse>('/admin/login', credentials)
    await persistSession(result, setAdmin)
  }, [])

  const register = useCallback(async (payload: RegisterRequest) => {
    const result = await apiPost<LoginResponse>('/admin/register', payload)
    await persistSession(result, setAdmin)
  }, [])

  const logout = useCallback(async () => {
    try {
      if (getToken()) {
        await apiPost<{ message: string }>('/admin/logout')
      }
    } catch {
      // Always clear local session even if logout request fails
    } finally {
      clearToken()
      setAdmin(null)
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      admin,
      isAuthenticated: Boolean(admin),
      isLoading,
      login,
      register,
      logout,
      refreshAdmin,
    }),
    [admin, isLoading, login, register, logout, refreshAdmin],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuthContext must be used within AuthProvider')
  }
  return ctx
}
