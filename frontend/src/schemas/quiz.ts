import { z } from 'zod'

export const quizConfigSchema = z.object({
  questionAdvanceMode: z.enum(['manual', 'automatic']).optional(),
  answerRevealBehavior: z.enum(['after_each', 'session_end']).optional(),
  timeBonusEnabled: z.boolean().optional(),
  timeBonusMaxPoints: z.number().int().min(0).optional(),
  streakBonusEnabled: z.boolean().optional(),
  streakBonusRules: z.record(z.unknown()).nullable().optional(),
  questionOrderShuffle: z.boolean().optional(),
  answerOptionShuffle: z.boolean().optional(),
})

export const quizCreateSchema = z.object({
  title: z
    .string()
    .min(1, 'Title is required')
    .max(255)
    .transform((v) => v.trim())
    .refine((v) => v.length > 0, 'Title must not be blank'),
  description: z.string().max(10_000).nullable().optional(),
  config: quizConfigSchema.nullable().optional(),
})

export const quizUpdateSchema = z.object({
  title: z
    .string()
    .min(1)
    .max(255)
    .transform((v) => v.trim())
    .refine((v) => v.length > 0, 'Title must not be blank')
    .optional(),
  description: z.string().max(10_000).nullable().optional(),
  config: quizConfigSchema.nullable().optional(),
})

export type QuizCreateFormValues = z.infer<typeof quizCreateSchema>
export type QuizUpdateFormValues = z.infer<typeof quizUpdateSchema>
