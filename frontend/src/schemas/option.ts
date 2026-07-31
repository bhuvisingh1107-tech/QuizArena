import { z } from 'zod'

export const optionSchema = z.object({
  text: z
    .string()
    .min(1, 'Option text is required')
    .max(500)
    .transform((v) => v.trim())
    .refine((v) => v.length > 0, 'Option text must not be blank'),
  isCorrect: z.boolean().default(false),
  sortOrder: z.number().int().min(0).nullable().optional(),
})

export type OptionFormValues = z.infer<typeof optionSchema>
