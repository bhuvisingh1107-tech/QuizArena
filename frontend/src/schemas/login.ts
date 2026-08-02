import { z } from 'zod'

export const loginSchema = z.object({
  username: z.string().min(1, 'Username or email is required').max(255),
  password: z.string().min(1, 'Password is required').max(128),
})

export type LoginFormValues = z.infer<typeof loginSchema>
