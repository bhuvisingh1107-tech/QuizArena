export const queryKeys = {
  auth: {
    me: ['auth', 'me'] as const,
  },
  quizzes: {
    all: ['quizzes'] as const,
    list: (params?: Record<string, unknown>) => ['quizzes', 'list', params] as const,
    detail: (id: string) => ['quizzes', 'detail', id] as const,
  },
  sections: {
    list: (quizId: string) => ['sections', quizId] as const,
  },
  questions: {
    list: (quizId: string, sectionId: string) => ['questions', quizId, sectionId] as const,
  },
  options: {
    list: (quizId: string, sectionId: string, questionId: string) =>
      ['options', quizId, sectionId, questionId] as const,
  },
  media: {
    detail: (id: string) => ['media', id] as const,
  },
  liveRooms: {
    all: ['live-rooms'] as const,
    list: (params?: Record<string, unknown>) => ['live-rooms', 'list', params] as const,
    detail: (id: string) => ['live-rooms', 'detail', id] as const,
  },
}
