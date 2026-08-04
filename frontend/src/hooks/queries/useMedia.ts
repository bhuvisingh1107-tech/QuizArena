import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient, apiDelete, apiGet, apiPost, unwrapData } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type {
  ApiEnvelope,
  MediaApplyToAllResult,
  MediaCategory,
  MediaFile,
  MediaList,
  MediaRemoveFromAllResult,
} from '@/types/api'

export function useMedia(mediaId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.media.detail(mediaId ?? ''),
    queryFn: () => apiGet<MediaFile>(`/media/${mediaId}`),
    enabled: Boolean(mediaId) && enabled,
  })
}

export function useQuizMedia(
  quizId: string | undefined,
  params: { category?: MediaCategory } = {},
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.media.list(quizId ?? '', params),
    queryFn: () =>
      apiGet<MediaList>('/media', {
        params: {
          quizId,
          ...(params.category ? { category: params.category } : {}),
        },
      }),
    enabled: Boolean(quizId) && enabled,
  })
}

export function useMediaMutations() {
  const queryClient = useQueryClient()

  const invalidateMedia = async (quizId?: string | null, mediaId?: string) => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.media.all })
    if (quizId) {
      await queryClient.invalidateQueries({ queryKey: queryKeys.media.list(quizId) })
    }
    if (mediaId) {
      await queryClient.invalidateQueries({ queryKey: queryKeys.media.detail(mediaId) })
    }
  }

  const invalidateQuizQuestions = async (quizId: string) => {
    await queryClient.invalidateQueries({
      queryKey: ['questions', quizId],
    })
  }

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
      await invalidateMedia(media.quizId, media.id)
    },
  })

  const deleteMedia = useMutation({
    mutationFn: (mediaId: string) =>
      apiDelete<{ id: string; deleted: boolean }>(`/media/${mediaId}`),
    onSuccess: async (_result, mediaId) => {
      await invalidateMedia(undefined, mediaId)
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
    onSuccess: async (_result, variables) => {
      await invalidateMedia(variables.quizId, variables.mediaId)
      await queryClient.invalidateQueries({
        queryKey: queryKeys.questions.list(variables.quizId, variables.sectionId),
      })
    },
  })

  const applyMediaToAll = useMutation({
    mutationFn: ({ mediaId, quizId }: { mediaId: string; quizId: string }) =>
      apiPost<MediaApplyToAllResult>(`/media/${mediaId}/apply-to-all`, { quizId }),
    onSuccess: async (result) => {
      await invalidateMedia(result.quizId, result.mediaId)
      await invalidateQuizQuestions(result.quizId)
    },
  })

  const removeMediaFromAll = useMutation({
    mutationFn: ({ mediaId, quizId }: { mediaId: string; quizId: string }) =>
      apiPost<MediaRemoveFromAllResult>(`/media/${mediaId}/remove-from-all`, { quizId }),
    onSuccess: async (result) => {
      await invalidateMedia(result.quizId, result.mediaId)
      await invalidateQuizQuestions(result.quizId)
    },
  })

  return {
    uploadMedia,
    deleteMedia,
    attachMedia,
    applyMediaToAll,
    removeMediaFromAll,
  }
}
