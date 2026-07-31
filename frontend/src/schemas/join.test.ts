import { describe, expect, it } from 'vitest'

import {
  joinIdentitySchema,
  joinRoomCodeSchema,
} from '@/schemas/join'

describe('join form validation', () => {
  it('rejects short or non-alphanumeric room codes', () => {
    expect(joinRoomCodeSchema.safeParse({ roomCode: 'AB12' }).success).toBe(false)
    expect(joinRoomCodeSchema.safeParse({ roomCode: 'ABC12!' }).success).toBe(false)
    expect(joinRoomCodeSchema.safeParse({ roomCode: 'abc123' }).success).toBe(true)
  })

  it('requires display name and valid email', () => {
    const missingName = joinIdentitySchema.safeParse({
      roomCode: 'ABC123',
      displayName: '',
      email: 'a@b.com',
    })
    expect(missingName.success).toBe(false)

    const badEmail = joinIdentitySchema.safeParse({
      roomCode: 'ABC123',
      displayName: 'Alex',
      email: 'not-an-email',
    })
    expect(badEmail.success).toBe(false)

    const ok = joinIdentitySchema.safeParse({
      roomCode: 'xyz789',
      displayName: 'Alex',
      email: 'alex@example.com',
    })
    expect(ok.success).toBe(true)
    if (ok.success) {
      expect(ok.data.roomCode).toBe('XYZ789')
    }
  })
})
