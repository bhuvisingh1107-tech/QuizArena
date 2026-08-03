import axios, {
  type AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
} from 'axios'

import { ApiError, toApiError, unwrapData } from '@/lib/api-client'
import { getApiBaseUrl } from '@/lib/env'
import { clearParticipantSession, getSessionToken } from '@/lib/participant-session'
import type { ApiEnvelope, ApiErrorBody } from '@/types/api'

const baseURL = getApiBaseUrl()

export const participantApiClient: AxiosInstance = axios.create({
  baseURL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

function isParticipantPath(pathname: string): boolean {
  return (
    pathname === '/join' ||
    pathname.startsWith('/join/') ||
    pathname === '/lobby' ||
    pathname.startsWith('/lobby/') ||
    pathname === '/quiz' ||
    pathname.startsWith('/quiz/') ||
    pathname === '/results' ||
    pathname.startsWith('/results/')
  )
}

participantApiClient.interceptors.request.use((config) => {
  const token = getSessionToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

participantApiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    if (error.response?.status === 401) {
      clearParticipantSession()
      if (typeof window !== 'undefined' && isParticipantPath(window.location.pathname)) {
        window.location.assign('/join')
      }
    }
    throw toApiError(error)
  },
)

export async function participantGet<T>(
  url: string,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await participantApiClient.get<ApiEnvelope<T>>(url, config)
  return unwrapData(response)
}

export async function participantPost<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await participantApiClient.post<ApiEnvelope<T>>(url, data, config)
  return unwrapData(response)
}

export { ApiError }
export type { AxiosResponse }
