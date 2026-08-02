/** Canonical host auth / entry paths. Console remains under `/admin/*`. */

export const HOST_LOGIN_PATH = '/host/login'
export const HOST_SIGNUP_PATH = '/host/signup'
export const HOST_DASHBOARD_PATH = '/dashboard'

export function hostDestinationFrom(from: string | null | undefined): string {
  if (!from) return HOST_DASHBOARD_PATH
  if (from === '/host/login' || from === '/host/signup' || from === '/admin/login') {
    return HOST_DASHBOARD_PATH
  }
  if (from.startsWith('/admin') || from === '/dashboard') {
    return from === '/admin' || from === '/admin/' ? HOST_DASHBOARD_PATH : from
  }
  return HOST_DASHBOARD_PATH
}

export function isHostAuthPath(pathname: string): boolean {
  return (
    pathname === HOST_LOGIN_PATH ||
    pathname === HOST_SIGNUP_PATH ||
    pathname === '/admin/login'
  )
}
