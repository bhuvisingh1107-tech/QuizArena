import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/hooks/queries/keys'
import {
  cancelAiJob,
  createDocumentJob,
  createTopicJob,
  deleteAiQuestion,
  getAiJob,
  listAiJobs,
  patchAiQuestion,
  regenerateAiQuestion,
  regenerateAiQuiz,
  regenerateAiSection,
  saveAiJob,
  uploadAiSource,
} from '@/lib/ai-api'
import type { AiGenerateDocumentRequest, AiGenerateTopicRequest, AiQuestionPatch } from '@/types/ai-generation'

export const aiQueryKeys = {
  jobs: ['ai', 'jobs'] as const,
  job: (id: string) => ['ai', 'jobs', id] as const,
}

const ACTIVE_STATUSES = new Set([
  'queued',
  'uploading',
  'extracting',
  'analyzing',
  'generating',
])

export function useAiJobsQuery(opts?: { pollActive?: boolean }) {
  return useQuery({
    queryKey: aiQueryKeys.jobs,
    queryFn: listAiJobs,
    refetchInterval: (query) => {
      if (!opts?.pollActive) return false
      const items = query.state.data?.items ?? []
      return items.some((j) => ACTIVE_STATUSES.has(j.status)) ? 2000 : false
    },
  })
}

export function useAiJobQuery(jobId: string | undefined, opts?: { poll?: boolean }) {
  return useQuery({
    queryKey: aiQueryKeys.job(jobId || ''),
    queryFn: () => getAiJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      if (!opts?.poll) return false
      const status = query.state.data?.status
      if (!status) return 1500
      if (['completed', 'failed', 'cancelled'].includes(status)) return false
      return 1500
    },
  })
}

export function useAiGenerationMutations() {
  const queryClient = useQueryClient()

  const invalidateAi = (jobId?: string) => {
    void queryClient.invalidateQueries({ queryKey: ['ai'] })
    if (jobId) void queryClient.invalidateQueries({ queryKey: aiQueryKeys.job(jobId) })
  }

  const invalidateQuizzes = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.quizzes.all })
    void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary })
  }

  return {
    createDocument: useMutation({
      mutationFn: (body: AiGenerateDocumentRequest) => createDocumentJob(body),
      onSuccess: (job) => invalidateAi(job.id),
    }),
    createTopic: useMutation({
      mutationFn: (body: AiGenerateTopicRequest) => createTopicJob(body),
      onSuccess: (job) => invalidateAi(job.id),
    }),
    upload: useMutation({
      mutationFn: ({ jobId, file }: { jobId: string; file: File }) => uploadAiSource(jobId, file),
      onSuccess: (job) => invalidateAi(job.id),
    }),
    cancel: useMutation({
      mutationFn: (jobId: string) => cancelAiJob(jobId),
      onSuccess: (job) => invalidateAi(job.id),
    }),
    patchQuestion: useMutation({
      mutationFn: ({ questionId, body }: { questionId: string; body: AiQuestionPatch }) =>
        patchAiQuestion(questionId, body),
      onSuccess: () => invalidateAi(),
    }),
    deleteQuestion: useMutation({
      mutationFn: (questionId: string) => deleteAiQuestion(questionId),
      onSuccess: () => invalidateAi(),
    }),
    regenerateQuestion: useMutation({
      mutationFn: (questionId: string) => regenerateAiQuestion(questionId),
      onSuccess: () => invalidateAi(),
    }),
    regenerateSection: useMutation({
      mutationFn: (sectionId: string) => regenerateAiSection(sectionId),
      onSuccess: () => invalidateAi(),
    }),
    regenerateQuiz: useMutation({
      mutationFn: (jobId: string) => regenerateAiQuiz(jobId),
      onSuccess: (job) => invalidateAi(job.id),
    }),
    save: useMutation({
      mutationFn: (jobId: string) => saveAiJob(jobId),
      onSuccess: () => {
        invalidateAi()
        invalidateQuizzes()
      },
    }),
    invalidateQuizzes,
  }
}
