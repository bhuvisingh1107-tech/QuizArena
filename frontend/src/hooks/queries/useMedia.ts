import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient, apiDelete, apiGet, apiPost, unwrapData } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type { ApiEnvelope, MediaCategory, MediaFile } from '@/types/api'

export function useMedia(mediaId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.media.detail(mediaId ?? ''),
    queryFn: () => apiGet<MediaFile>(`/media/${mediaId}`),
    enabled: Boolean(mediaId) && enabled,
  })
}

export function useMediaMutations() {
  const queryClient = useQueryClient()

  const uploadMedia = useMutation({
    mutationFn: async (input: {
      file: File
      category: MediaCategory
      quizId?: string | null
    }) => {
      const form = new FormData()
      form.append('file', input.file)
      form.append('category', input.category)
      if (input.quizId) {
        form.append('quizId', input.quizId)
      }
      const response = await apiClient.post<ApiEnvelope<MediaFile>>('/media', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return unwrapData(response)
    },
    onSuccess: async (media) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.media.detail(media.id) })
    },
  })

  const deleteMedia = useMutation({
    mutationFn: (mediaId: string) =>
      apiDelete<{ id: string; deleted: boolean }>(`/media/${mediaId}`),
    onSuccess: async (_result, mediaId) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.media.detail(mediaId) })
    },
  })

  const attachMedia = useMutation({
    mutationFn: ({
      mediaId,
      quizId,
      sectionId,
      questionId,
    }: {
      mediaId: string
      quizId: string
      sectionId: string
      questionId: string
    }) =>
      apiPost<{ mediaId: string; questionId: string; mediaFileId: string }>(
        `/media/${mediaId}/attach`,
        { quizId, sectionId, questionId },
      ),
  })

  return { uploadMedia, deleteMedia, attachMedia }
}
