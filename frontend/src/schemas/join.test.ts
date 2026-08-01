import { describe, expect, it } from 'vitest'

import { joinFormSchema, joinRoomCodeSchema } from '@/schemas/join'

describe('join form validation', () => {
  it('rejects short or non-alphanumeric room codes', () => {
    expect(joinRoomCodeSchema.safeParse({ roomCode: 'AB12' }).success).toBe(false)
    expect(joinRoomCodeSchema.safeParse({ roomCode: 'ABC12!' }).success).toBe(false)
    expect(joinRoomCodeSchema.safeParse({ roomCode: 'abc123' }).success).toBe(true)
  })

  it('requires display name only (no email in form)', () => {
    const missingName = joinFormSchema.safeParse({
      roomCode: 'ABC123',
      displayName: '',
    })
    expect(missingName.success).toBe(false)

    const ok = joinFormSchema.safeParse({
      roomCode: 'xyz789',
      displayName: 'Alex',
    })
    expect(ok.success).toBe(true)
    if (ok.success) {
      expect(ok.data.roomCode).toBe('XYZ789')
    }
  })
})
