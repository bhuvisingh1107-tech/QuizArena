import { useQueries } from '@tanstack/react-query'

import { queryKeys } from '@/hooks/queries/keys'
import { apiGet } from '@/lib/api-client'
import { firstMcqOptionError } from '@/lib/mcq-validation'
import type { AnswerOptionList, QuestionList, Section } from '@/types/api'

export interface QuizMcqIssue {
  questionId: string
  sectionId: string
  promptText: string
  message: string
}

/** Aggregate MCQ validation across every question in the quiz (for Publish / Start gates). */
export function useQuizMcqIssues(quizId: string, sections: Section[]) {
  const questionQueries = useQueries({
    queries: sections.map((section) => ({
      queryKey: queryKeys.questions.list(quizId, section.id),
      queryFn: () =>
        apiGet<QuestionList>(`/quizzes/${quizId}/sections/${section.id}/questions`),
    })),
  })

  const questionRefs = sections.flatMap((section, sectionIndex) => {
    const items = questionQueries[sectionIndex]?.data?.items ?? []
    return items.map((question) => ({
      sectionId: section.id,
      questionId: question.id,
      promptText: question.promptText ?? '',
    }))
  })

  const optionQueries = useQueries({
    queries: questionRefs.map((ref) => ({
      queryKey: queryKeys.options.list(quizId, ref.sectionId, ref.questionId),
      queryFn: () =>
        apiGet<AnswerOptionList>(
          `/quizzes/${quizId}/sections/${ref.sectionId}/questions/${ref.questionId}/options`,
        ),
      enabled: Boolean(ref.questionId),
    })),
  })

  const loading =
    questionQueries.some((q) => q.isLoading) || optionQueries.some((q) => q.isLoading)

  const issues: QuizMcqIssue[] = []
  questionRefs.forEach((ref, index) => {
    const items = optionQueries[index]?.data?.items
    if (!items) return
    const message = firstMcqOptionError(
      [...items]
        .sort((a, b) => a.sortOrder - b.sortOrder)
        .map((o) => ({ text: o.text, isCorrect: o.isCorrect })),
    )
    if (message) {
      issues.push({
        questionId: ref.questionId,
        sectionId: ref.sectionId,
        promptText: ref.promptText,
        message,
      })
    }
  })

  return {
    loading,
    issues,
    hasInvalidMcq: issues.length > 0,
  }
}
