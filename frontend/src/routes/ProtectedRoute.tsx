import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { LoadingState } from '@/components/shared/LoadingState'
import { useAuth } from '@/hooks/queries/useAuth'
import { HOST_LOGIN_PATH } from '@/lib/host-routes'

export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <LoadingState label="Checking session…" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to={HOST_LOGIN_PATH} replace state={{ from: location.pathname }} />
  }

  return <Outlet />
}
