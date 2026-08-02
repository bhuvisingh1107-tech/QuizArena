import { describe, expect, it } from 'vitest'

import { canRest, preferFreshestRoom, roomStateRank } from '@/lib/room-lifecycle'
import type { LiveRoom } from '@/types/api'

function room(partial: Partial<LiveRoom> & Pick<LiveRoom, 'state'>): LiveRoom {
  return {
    id: 'r1',
    quizId: 'q1',
    roomCode: 'ABC',
    secretToken: 'tok',
    quizTitleSnapshot: 'Quiz',
    currentQuestionIndex: null,
    codesExpired: false,
    joinUrl: '',
    displayUrl: '',
    qrTarget: '',
    lobbySubState: null,
    ...partial,
  } as LiveRoom
}

describe('preferFreshestRoom', () => {
  it('prefers Lobby REST over stale Setup WS', () => {
    const merged = preferFreshestRoom(room({ state: 'Setup' }), room({ state: 'Lobby' }))
    expect(merged?.state).toBe('Lobby')
  })

  it('prefers Completed WS over Active REST', () => {
    const merged = preferFreshestRoom(room({ state: 'Completed' }), room({ state: 'Active' }))
    expect(merged?.state).toBe('Completed')
  })

  it('keeps primary when ranks match', () => {
    const merged = preferFreshestRoom(
      room({ state: 'Lobby', lobbySubState: 'LobbyOpen' }),
      room({ state: 'Lobby', lobbySubState: 'LobbyClosed' }),
    )
    expect(merged?.state).toBe('Lobby')
    expect(merged?.lobbySubState).toBe('LobbyOpen')
  })
})

describe('canRest', () => {
  it('enables Start Quiz only in Lobby', () => {
    expect(canRest('Setup', 'start')).toBe(false)
    expect(canRest('Lobby', 'start')).toBe(true)
    expect(canRest('Active', 'start')).toBe(false)
  })

  it('disables End Quiz after Completed', () => {
    expect(canRest('Active', 'end')).toBe(true)
    expect(canRest('Completed', 'end')).toBe(false)
    expect(canRest('Closed', 'end')).toBe(false)
  })
})

describe('roomStateRank', () => {
  it('orders lifecycle stages', () => {
    expect(roomStateRank('Setup')).toBeLessThan(roomStateRank('Lobby'))
    expect(roomStateRank('Lobby')).toBeLessThan(roomStateRank('Active'))
    expect(roomStateRank('Active')).toBeLessThan(roomStateRank('Completed'))
  })
})
