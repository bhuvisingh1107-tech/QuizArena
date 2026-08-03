import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

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

export function useAiJobsQuery() {
  return useQuery({
    queryKey: aiQueryKeys.jobs,
    queryFn: listAiJobs,
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

  const invalidate = (jobId?: string) => {
    void queryClient.invalidateQueries({ queryKey: ['ai'] })
    if (jobId) void queryClient.invalidateQueries({ queryKey: aiQueryKeys.job(jobId) })
  }

  return {
    createDocument: useMutation({
      mutationFn: (body: AiGenerateDocumentRequest) => createDocumentJob(body),
      onSuccess: (job) => invalidate(job.id),
    }),
    createTopic: useMutation({
      mutationFn: (body: AiGenerateTopicRequest) => createTopicJob(body),
      onSuccess: (job) => invalidate(job.id),
    }),
    upload: useMutation({
      mutationFn: ({ jobId, file }: { jobId: string; file: File }) => uploadAiSource(jobId, file),
      onSuccess: (job) => invalidate(job.id),
    }),
    cancel: useMutation({
      mutationFn: (jobId: string) => cancelAiJob(jobId),
      onSuccess: (job) => invalidate(job.id),
    }),
    patchQuestion: useMutation({
      mutationFn: ({ questionId, body }: { questionId: string; body: AiQuestionPatch }) =>
        patchAiQuestion(questionId, body),
      onSuccess: () => invalidate(),
    }),
    deleteQuestion: useMutation({
      mutationFn: (questionId: string) => deleteAiQuestion(questionId),
      onSuccess: () => invalidate(),
    }),
    regenerateQuestion: useMutation({
      mutationFn: (questionId: string) => regenerateAiQuestion(questionId),
      onSuccess: () => invalidate(),
    }),
    regenerateSection: useMutation({
      mutationFn: (sectionId: string) => regenerateAiSection(sectionId),
      onSuccess: () => invalidate(),
    }),
    regenerateQuiz: useMutation({
      mutationFn: (jobId: string) => regenerateAiQuiz(jobId),
      onSuccess: (job) => invalidate(job.id),
    }),
    save: useMutation({
      mutationFn: (jobId: string) => saveAiJob(jobId),
      onSuccess: () => invalidate(),
    }),
  }
}
