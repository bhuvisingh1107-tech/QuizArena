import { apiDelete, apiGet, apiPatch, apiPost } from '@/lib/api-client'
import type {
  AiGenerateDocumentRequest,
  AiGenerateTopicRequest,
  AiGeneratedQuestion,
  AiGeneratedSection,
  AiJob,
  AiQuestionPatch,
  AiSaveResult,
} from '@/types/ai-generation'

export function createDocumentJob(body: AiGenerateDocumentRequest) {
  return apiPost<AiJob>('/ai/generate/document', body)
}

export function createTopicJob(body: AiGenerateTopicRequest) {
  return apiPost<AiJob>('/ai/generate/topic', body)
}

export async function uploadAiSource(jobId: string, file: File) {
  const form = new FormData()
  form.append('jobId', jobId)
  form.append('file', file)
  return apiPost<AiJob>('/ai/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getAiJob(jobId: string) {
  return apiGet<AiJob>(`/ai/jobs/${jobId}`)
}

export function listAiJobs() {
  return apiGet<{ items: AiJob[] }>('/ai/jobs')
}

export function cancelAiJob(jobId: string) {
  return apiPost<AiJob>(`/ai/jobs/${jobId}/cancel`, {})
}

export function patchAiQuestion(questionId: string, body: AiQuestionPatch) {
  return apiPatch<AiGeneratedQuestion>(`/ai/question/${questionId}`, body)
}

export function deleteAiQuestion(questionId: string) {
  return apiDelete(`/ai/question/${questionId}`)
}

export function regenerateAiQuestion(questionId: string) {
  return apiPost<AiGeneratedQuestion>(`/ai/regenerate/question/${questionId}`, {})
}

export function regenerateAiSection(sectionId: string) {
  return apiPost<AiGeneratedSection>(`/ai/regenerate/section/${sectionId}`, {})
}

export function regenerateAiQuiz(jobId: string) {
  return apiPost<AiJob>(`/ai/regenerate/quiz/${jobId}`, {})
}

export function saveAiJob(jobId: string) {
  return apiPost<AiSaveResult>('/ai/save', { jobId })
}
