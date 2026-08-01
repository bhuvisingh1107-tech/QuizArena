import { useMutation } from '@tanstack/react-query'

import { apiPost } from '@/lib/api-client'
import type { ChangePasswordRequest, ChangePasswordResponse } from '@/types/api'

export function useChangePassword() {
  return useMutation({
    mutationFn: (input: ChangePasswordRequest) =>
      apiPost<ChangePasswordResponse>('/admin/change-password', input),
  })
}
