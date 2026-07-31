import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuthContext } from '@/contexts/AuthContext'
import { queryKeys } from '@/hooks/queries/keys'
import type { LoginRequest } from '@/types/api'

/** Re-export auth context as a query-style hook for consistent imports. */
export function useAuth() {
  return useAuthContext()
}

export function useLoginMutation() {
  const { login } = useAuthContext()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (credentials: LoginRequest) => login(credentials),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.auth.me })
    },
  })
}

export function useLogoutMutation() {
  const { logout } = useAuthContext()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => logout(),
    onSuccess: () => {
      queryClient.clear()
    },
  })
}

export function useCurrentAdminQuery(enabled = true) {
  const { admin, isAuthenticated, refreshAdmin } = useAuthContext()

  return useQuery({
    queryKey: queryKeys.auth.me,
    queryFn: async () => {
      await refreshAdmin()
      return admin
    },
    enabled: enabled && isAuthenticated,
    initialData: admin,
  })
}
