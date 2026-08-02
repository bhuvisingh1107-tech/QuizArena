import { z } from 'zod'

/** Keep in sync with backend `app.core.password_policy` (FR-005). */
export const PASSWORD_MIN_LENGTH = 8

export const PASSWORD_POLICY_HINT =
  'At least 8 characters with uppercase, lowercase, number, and special character.'

export const strongPasswordSchema = z
  .string()
  .min(PASSWORD_MIN_LENGTH, `Password must be at least ${PASSWORD_MIN_LENGTH} characters`)
  .max(128)
  .regex(/[A-Z]/, 'Password must include an uppercase letter')
  .regex(/[a-z]/, 'Password must include a lowercase letter')
  .regex(/[0-9]/, 'Password must include a digit')
  .regex(/[^A-Za-z0-9]/, 'Password must include a special character')
