import { useQuery } from '@tanstack/react-query'

import { apiClient, apiGet, ApiError, toApiError } from '@/lib/api-client'
import { queryKeys } from '@/hooks/queries/keys'
import type { RoomResults } from '@/types/api'

export function useRoomResults(roomId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.liveRooms.results(roomId ?? ''),
    queryFn: () => apiGet<RoomResults>(`/live-rooms/${roomId}/results`),
    enabled: Boolean(roomId) && enabled,
  })
}

export async function downloadRoomResultsCsv(roomId: string): Promise<void> {
  return downloadRoomResults(roomId, 'csv')
}

export async function downloadRoomResults(
  roomId: string,
  format: 'xlsx' | 'csv' = 'xlsx',
): Promise<void> {
  try {
    const response = await apiClient.get(`/live-rooms/${roomId}/results/export`, {
      responseType: 'blob',
      params: { format },
    })

    const blob = response.data instanceof Blob ? response.data : new Blob([response.data])
    if (blob.type && blob.type.includes('application/json')) {
      const text = await blob.text()
      let message = 'Export failed'
      try {
        const parsed = JSON.parse(text) as { error?: { message?: string } }
        message = parsed.error?.message ?? message
      } catch {
        // keep default
      }
      throw new ApiError(message, { status: response.status, code: 'EXPORT_FAILED' })
    }

    const disposition = response.headers['content-disposition'] as string | undefined
    const match = disposition?.match(/filename="?([^"]+)"?/i)
    const fallback = format === 'csv' ? `room-${roomId}-results.csv` : `room-${roomId}-results.xlsx`
    const filename = match?.[1] ?? fallback

    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  } catch (error) {
    if (error instanceof ApiError) throw error
    // Axios error with blob body
    const axiosError = error as {
      response?: { data?: Blob; status?: number }
      isAxiosError?: boolean
    }
    if (axiosError.response?.data instanceof Blob) {
      try {
        const text = await axiosError.response.data.text()
        const parsed = JSON.parse(text) as {
          error?: { code?: string; message?: string; details?: unknown[] }
        }
        throw new ApiError(parsed.error?.message ?? 'Export failed', {
          status: axiosError.response.status ?? 500,
          code: parsed.error?.code ?? 'EXPORT_FAILED',
          details: parsed.error?.details,
        })
      } catch (inner) {
        if (inner instanceof ApiError) throw inner
      }
    }
    throw toApiError(error as never)
  }
}
