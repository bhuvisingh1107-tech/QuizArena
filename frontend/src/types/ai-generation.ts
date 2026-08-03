export type AiGenerationMode = 'document' | 'topic'
export type AiJobStatus =
  | 'queued'
  | 'uploading'
  | 'extracting'
  | 'analyzing'
  | 'generating'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type AiDifficulty = 'easy' | 'medium' | 'hard' | 'mixed'
export type AiQuestionKind = 'mcq' | 'multiple_correct' | 'true_false' | 'fill_blank'

export interface AiGenerateDocumentRequest {
  title?: string
  language?: string
  questionCount?: number
  difficulty?: AiDifficulty
  questionKinds?: AiQuestionKind[]
}

export interface AiGenerateTopicRequest {
  topic: string
  title?: string
  language?: string
  questionCount?: number
  difficulty?: AiDifficulty
  questionKinds?: AiQuestionKind[]
}

export interface AiOption {
  text: string
  isCorrect: boolean
}

export interface AiGeneratedQuestion {
  id: string
  kind: AiQuestionKind
  promptText: string
  explanation?: string | null
  difficulty: AiDifficulty
  topicLabel?: string | null
  estimatedTimeSeconds: number
  options: AiOption[]
  sourceLocator?: string | null
  sortOrder: number
}

export interface AiGeneratedSection {
  id: string
  name: string
  summary?: string | null
  sortOrder: number
  concepts: string[]
  questions: AiGeneratedQuestion[]
}

export interface AiSourceFile {
  id: string
  originalFilename: string
  mimeType: string
  fileSize: number
  extractor?: string | null
}

export interface AiSourceReference {
  id: string
  kind: string
  title: string
  locator: string
  publisher?: string | null
}

export interface AiJob {
  id: string
  mode: AiGenerationMode
  status: AiJobStatus
  progressPercent: number
  progressMessage?: string | null
  errorCode?: string | null
  errorMessage?: string | null
  topic?: string | null
  title?: string | null
  language: string
  questionCount: number
  difficulty: AiDifficulty
  questionKinds: string[]
  resultQuizId?: string | null
  sourceFiles: AiSourceFile[]
  sources: AiSourceReference[]
  sections: AiGeneratedSection[]
  createdAt: string
  updatedAt: string
  startedAt?: string | null
  completedAt?: string | null
}

export interface AiQuestionPatch {
  promptText?: string
  explanation?: string | null
  difficulty?: AiDifficulty
  kind?: AiQuestionKind
  topicLabel?: string | null
  estimatedTimeSeconds?: number
  options?: AiOption[]
}

export interface AiSaveResult {
  quizId: string
  jobId: string
}
