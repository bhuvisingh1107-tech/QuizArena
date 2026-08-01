import { z } from 'zod'

export const questionSchema = z.object({
  questionType: z.enum(['Text', 'Image', 'Audio', 'Buzzer']),
  promptText: z
    .string()
    .min(1, 'Question text is required')
    .transform((v) => v.trim())
    .refine((v) => v.length > 0, 'Question text must not be blank'),
  explanation: z.string().max(10_000).nullable().optional(),
  basePoints: z.number().int().min(1).default(1),
  timeLimitSeconds: z.number().int().min(1).nullable().optional(),
  allowMultipleCorrect: z.boolean().default(false),
  sortOrder: z.number().int().min(0).nullable().optional(),
})

export type QuestionFormValues = z.infer<typeof questionSchema>
