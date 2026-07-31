import { z } from 'zod'

export const sectionSchema = z.object({
  name: z
    .string()
    .min(1, 'Section name is required')
    .max(255)
    .transform((v) => v.trim())
    .refine((v) => v.length > 0, 'Section name must not be blank'),
  sortOrder: z.number().int().min(0).nullable().optional(),
})

export type SectionFormValues = z.infer<typeof sectionSchema>
