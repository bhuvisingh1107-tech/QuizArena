import axios, {
  type AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
} from 'axios'

import { clearToken, getToken } from '@/lib/auth-token'
import { getApiBaseUrl } from '@/lib/env'
import type { ApiEnvelope, ApiErrorBody, ApiMeta } from '@/types/api'

export class ApiError extends Error {
  readonly code: string
  readonly details: unknown[]
  readonly status: number
  readonly meta?: ApiMeta

  constructor(
    message: string,
    options: {
      code: string
      details?: unknown[]
      status?: number
      meta?: ApiMeta
    },
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = options.code
    this.details = options.details ?? []
    this.status = options.status ?? 0
    this.meta = options.meta
  }
}

const baseURL = getApiBaseUrl()

export const apiClient: AxiosInstance = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    if (error.response?.status === 401) {
      clearToken()
      if (typeof window !== 'undefined' && !window.location.pathname.includes('/admin/login')) {
        window.location.assign('/admin/login')
      }
    }
    throw toApiError(error)
  },
)

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorBody>
    const body = axiosError.response?.data
    if (body?.error) {
      return new ApiError(body.error.message, {
        code: body.error.code,
        details: body.error.details ?? [],
        status: axiosError.response?.status ?? 0,
        meta: body.meta,
      })
    }
    return new ApiError(axiosError.message || 'Network request failed', {
      code: 'NETWORK_ERROR',
      status: axiosError.response?.status ?? 0,
    })
  }

  if (error instanceof Error) {
    return new ApiError(error.message, { code: 'UNKNOWN_ERROR' })
  }

  return new ApiError('An unexpected error occurred', { code: 'UNKNOWN_ERROR' })
}

export function unwrapData<T>(response: AxiosResponse<ApiEnvelope<T>>): T {
  return response.data.data
}

export async function apiGet<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await apiClient.get<ApiEnvelope<T>>(url, config)
  return unwrapData(response)
}

export async function apiPost<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await apiClient.post<ApiEnvelope<T>>(url, data, config)
  return unwrapData(response)
}

export async function apiPatch<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await apiClient.patch<ApiEnvelope<T>>(url, data, config)
  return unwrapData(response)
}

export async function apiPut<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await apiClient.put<ApiEnvelope<T>>(url, data, config)
  return unwrapData(response)
}

export async function apiDelete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await apiClient.delete<ApiEnvelope<T>>(url, config)
  return unwrapData(response)
}
