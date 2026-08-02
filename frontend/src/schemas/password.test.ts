import { describe, expect, it } from 'vitest'

import {
  PASSWORD_MIN_LENGTH,
  PASSWORD_POLICY_HINT,
  strongPasswordSchema,
} from '@/schemas/password'

describe('strongPasswordSchema', () => {
  it('matches the documented policy hint', () => {
    expect(PASSWORD_MIN_LENGTH).toBe(8)
    expect(PASSWORD_POLICY_HINT).toBe(
      'At least 8 characters with uppercase, lowercase, number, and special character.',
    )
  })

  it('rejects passwords shorter than 8 characters', () => {
    const result = strongPasswordSchema.safeParse('Ab1!xyz')
    expect(result.success).toBe(false)
  })

  it('accepts an 8-character complex password', () => {
    expect(strongPasswordSchema.safeParse('Abcd1!xy').success).toBe(true)
  })

  it('requires upper, lower, digit, and special', () => {
    expect(strongPasswordSchema.safeParse('abcdefgh').success).toBe(false)
    expect(strongPasswordSchema.safeParse('ABCDEFG1').success).toBe(false)
    expect(strongPasswordSchema.safeParse('abcdefg1').success).toBe(false)
    expect(strongPasswordSchema.safeParse('Abcdefg!').success).toBe(false)
  })
})
