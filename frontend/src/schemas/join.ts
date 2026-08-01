import { z } from 'zod'

export const roomCodeSchema = z
  .string()
  .trim()
  .toUpperCase()
  .length(6, 'Room code must be 6 characters')
  .regex(/^[A-Z0-9]{6}$/, 'Room code must be 6 alphanumeric characters')

export const joinRoomCodeSchema = z.object({
  roomCode: roomCodeSchema,
})

export const joinFormSchema = z.object({
  roomCode: roomCodeSchema,
  displayName: z
    .string()
    .trim()
    .min(1, 'Display name is required')
    .max(64, 'Display name must be at most 64 characters'),
})

export type JoinRoomCodeFormValues = z.infer<typeof joinRoomCodeSchema>
export type JoinFormValues = z.infer<typeof joinFormSchema>
