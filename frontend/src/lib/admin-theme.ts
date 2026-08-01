import type { AdminTheme } from '@/types/api'

export const ADMIN_THEME_KEY = 'qa_admin_theme'

export function getStoredAdminTheme(): AdminTheme {
  try {
    const stored = localStorage.getItem(ADMIN_THEME_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // ignore
  }
  return 'dark'
}

export function applyAdminTheme(theme: AdminTheme): void {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', theme)
  document.documentElement.style.colorScheme = theme
}

export function setAdminTheme(theme: AdminTheme): void {
  try {
    localStorage.setItem(ADMIN_THEME_KEY, theme)
  } catch {
    // ignore
  }
  applyAdminTheme(theme)
}

export function initAdminTheme(): AdminTheme {
  const theme = getStoredAdminTheme()
  applyAdminTheme(theme)
  return theme
}
