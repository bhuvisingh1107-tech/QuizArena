import { z } from 'zod'

const strongPassword = z
  .string()
  .min(12, 'Password must be at least 12 characters')
  .max(128)
  .regex(/[A-Z]/, 'Password must include an uppercase letter')
  .regex(/[a-z]/, 'Password must include a lowercase letter')
  .regex(/[0-9]/, 'Password must include a digit')
  .regex(/[^A-Za-z0-9]/, 'Password must include a special character')

export const registerSchema = z
  .object({
    name: z.string().trim().min(1, 'Full name is required').max(120),
    email: z.string().trim().email('Enter a valid email').max(255),
    username: z
      .string()
      .trim()
      .min(3, 'Username must be at least 3 characters')
      .max(64)
      .regex(
        /^[A-Za-z0-9_-]+$/,
        'Username may only contain letters, numbers, hyphens, and underscores',
      ),
    password: strongPassword,
    confirmPassword: z.string().min(1, 'Confirm your password'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })

export type RegisterFormValues = z.infer<typeof registerSchema>
