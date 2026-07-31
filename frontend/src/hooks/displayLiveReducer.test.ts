import { describe, expect, it } from 'vitest'

import {
  computeReconnectDelay,
  deriveViewMode,
  displayLiveReducer,
  initialDisplayLiveState,
} from '@/hooks/displayLiveReducer'

function event(type: string, payload: Record<string, unknown> = {}) {
  return {
    type: 'EVENT' as const,
    message: {
      type,
      payload,
      timestamp: new Date().toISOString(),
    },
  }
}

describe('displayLiveReducer', () => {
  it('starts in waiting mode for lobby/setup', () => {
    const lobby = displayLiveReducer(
      initialDisplayLiveState,
      event('resync', {
        room: {
          id: 'r1',
          roomCode: 'ABC123',
          state: 'Lobby',
          quizTitle: 'Trivia Night',
        },
      }),
    )

    expect(lobby.room?.roomCode).toBe('ABC123')
    expect(lobby.room?.quizTitle).toBe('Trivia Night')
    expect(lobby.viewMode).toBe('waiting')
    expect(lobby.connectionStatus).toBe('connected')
  })

  it('handles question:started without exposing isCorrect while open', () => {
    const started = displayLiveReducer(
      {
        ...initialDisplayLiveState,
        room: {
          id: 'r1',
          roomCode: 'ABC123',
          state: 'Active',
          quizTitle: 'Trivia Night',
        },
      },
      event('question:started', {
        questionIndex: 0,
        totalQuestions: 5,
        section: { id: 's1', name: 'Warmup' },
        question: {
          id: 'q1',
          promptText: 'Capital of France?',
          state: 'Open',
          options: [
            { id: 'a', text: 'Paris', sortOrder: 0, isCorrect: true },
            { id: 'b', text: 'Lyon', sortOrder: 1, isCorrect: false },
          ],
        },
      }),
    )

    expect(started.viewMode).toBe('question')
    expect(started.question?.promptText).toBe('Capital of France?')
    expect(started.question?.options).toHaveLength(2)
    expect(started.question?.options[0]).not.toHaveProperty('isCorrect')
    expect(started.question?.options[1]).not.toHaveProperty('isCorrect')
    expect(started.section?.name).toBe('Warmup')
  })

  it('keeps isCorrect hidden after question:closed until reveal', () => {
    const open = displayLiveReducer(
      {
        ...initialDisplayLiveState,
        room: {
          id: 'r1',
          roomCode: 'ABC123',
          state: 'Active',
          quizTitle: 'Trivia',
        },
      },
      event('question:started', {
        question: {
          id: 'q1',
          promptText: 'Q?',
          state: 'Open',
          options: [
            { id: 'a', text: 'A', sortOrder: 0, isCorrect: true },
            { id: 'b', text: 'B', sortOrder: 1, isCorrect: false },
          ],
        },
      }),
    )

    const closed = displayLiveReducer(
      open,
      event('question:closed', {
        question: {
          id: 'q1',
          state: 'Closed',
          options: [
            { id: 'a', text: 'A', sortOrder: 0, isCorrect: true },
            { id: 'b', text: 'B', sortOrder: 1, isCorrect: false },
          ],
        },
      }),
    )

    expect(closed.viewMode).toBe('question')
    expect(closed.question?.state).toBe('Closed')
    expect(closed.question?.options.every((o) => !('isCorrect' in o))).toBe(true)
  })

  it('highlights correct options on reveal', () => {
    const base = {
      ...initialDisplayLiveState,
      room: {
        id: 'r1',
        roomCode: 'ABC123',
        state: 'Active' as const,
        quizTitle: 'Trivia',
      },
      question: {
        id: 'q1',
        index: 0,
        promptText: 'Capital?',
        state: 'Closed' as const,
        options: [
          { id: 'a', text: 'Paris', sortOrder: 0 },
          { id: 'b', text: 'Lyon', sortOrder: 1 },
        ],
      },
      viewMode: 'question' as const,
    }

    const revealed = displayLiveReducer(
      base,
      event('question:reveal', {
        question: {
          id: 'q1',
          options: [
            { id: 'a', text: 'Paris', sortOrder: 0, isCorrect: true },
            { id: 'b', text: 'Lyon', sortOrder: 1, isCorrect: false },
          ],
        },
      }),
    )

    expect(revealed.viewMode).toBe('reveal')
    expect(revealed.question?.state).toBe('Revealed')
    expect(revealed.question?.options.find((o) => o.id === 'a')?.isCorrect).toBe(true)
    expect(revealed.question?.options.find((o) => o.id === 'b')?.isCorrect).toBe(false)
  })

  it('updates leaderboard and stores previousRanks', () => {
    const withBoard = {
      ...initialDisplayLiveState,
      room: {
        id: 'r1',
        roomCode: 'ABC123',
        state: 'Active' as const,
        quizTitle: 'Trivia',
      },
      question: {
        id: 'q1',
        index: 0,
        promptText: 'Q',
        state: 'Scored' as const,
        options: [{ id: 'a', text: 'A', sortOrder: 0, isCorrect: true }],
      },
      viewMode: 'reveal' as const,
      leaderboard: [
        { rank: 1, participantId: 'p1', displayName: 'Alex', score: 40 },
        { rank: 2, participantId: 'p2', displayName: 'Sam', score: 20 },
      ],
    }

    const next = displayLiveReducer(
      withBoard,
      event('leaderboard:updated', {
        entries: [
          {
            rank: 1,
            participantId: 'p2',
            displayName: 'Sam',
            score: 50,
            email: 'secret@example.com',
          },
          {
            rank: 2,
            participantId: 'p1',
            displayName: 'Alex',
            score: 40,
            email: 'a@example.com',
          },
        ],
      }),
    )

    expect(next.previousRanks).toEqual({ p1: 1, p2: 2 })
    expect(next.leaderboard[0]).toMatchObject({
      rank: 1,
      participantId: 'p2',
      displayName: 'Sam',
      score: 50,
    })
    expect(next.leaderboard[0]).not.toHaveProperty('email')
    // Prefer staying on reveal while Active with scored question
    expect(next.viewMode).toBe('reveal')
  })

  it('enters section_break on section:break', () => {
    const next = displayLiveReducer(
      {
        ...initialDisplayLiveState,
        room: {
          id: 'r1',
          roomCode: 'ABC123',
          state: 'Active',
          quizTitle: 'Trivia',
        },
      },
      event('section:break', {
        section: { id: 's1', name: 'Round 1', sortOrder: 0 },
        entries: [
          { rank: 1, participantId: 'p1', displayName: 'Alex', score: 30 },
        ],
      }),
    )

    expect(next.viewMode).toBe('section_break')
    expect(next.room?.state).toBe('SectionBreak')
    expect(next.section?.name).toBe('Round 1')
    expect(next.leaderboard).toHaveLength(1)
  })

  it('moves to podium then completed on quiz:completed', () => {
    const podium = displayLiveReducer(
      {
        ...initialDisplayLiveState,
        room: {
          id: 'r1',
          roomCode: 'ABC123',
          state: 'Active',
          quizTitle: 'Trivia Night',
        },
      },
      event('quiz:completed', {
        podium: {
          entries: [
            { rank: 1, participantId: 'p1', displayName: 'Alex', score: 100 },
            { rank: 2, participantId: 'p2', displayName: 'Sam', score: 80 },
            { rank: 3, participantId: 'p3', displayName: 'Jo', score: 60 },
          ],
        },
      }),
    )

    expect(podium.resultsReady).toBe(true)
    expect(podium.room?.state).toBe('Completed')
    expect(podium.viewMode).toBe('podium')
    expect(podium.podium?.entries).toHaveLength(3)

    const completedOnly = displayLiveReducer(
      {
        ...initialDisplayLiveState,
        room: {
          id: 'r1',
          roomCode: 'ABC123',
          state: 'Active',
          quizTitle: 'Trivia',
        },
      },
      event('results:ready', {}),
    )
    expect(completedOnly.viewMode).toBe('completed')
  })

  it('sets authFailed on AUTH_ERROR / ROOM_CLOSED', () => {
    const auth = displayLiveReducer(
      initialDisplayLiveState,
      event('error', { code: 'AUTH_ERROR', message: 'Invalid token' }),
    )
    expect(auth.authFailed).toBe(true)
    expect(auth.lastError).toBe('Invalid token')

    const closed = displayLiveReducer(
      initialDisplayLiveState,
      event('error', { code: 'ROOM_CLOSED', message: 'Room is closed' }),
    )
    expect(closed.authFailed).toBe(true)
  })

  it('handles minimal resync question snapshots gracefully', () => {
    const next = displayLiveReducer(
      {
        ...initialDisplayLiveState,
        question: {
          id: 'q1',
          index: 0,
          promptText: 'Kept',
          state: 'Open',
          options: [{ id: 'a', text: 'A', sortOrder: 0 }],
        },
      },
      event('resync', {
        room: {
          id: 'r1',
          roomCode: 'ZZZ999',
          state: 'Active',
          quizTitle: 'Live',
        },
        question: { id: 'q1', state: 'Open' },
      }),
    )

    expect(next.room?.roomCode).toBe('ZZZ999')
    expect(next.question?.promptText).toBe('Kept')
    expect(next.viewMode).toBe('question')
  })
})

describe('deriveViewMode', () => {
  it('maps room and question states to display modes', () => {
    expect(
      deriveViewMode({
        room: {
          id: 'r',
          roomCode: 'A',
          state: 'Lobby',
          quizTitle: 'T',
        },
        question: null,
        podium: null,
        resultsReady: false,
      }),
    ).toBe('waiting')

    expect(
      deriveViewMode({
        room: {
          id: 'r',
          roomCode: 'A',
          state: 'SectionBreak',
          quizTitle: 'T',
        },
        question: null,
        podium: null,
        resultsReady: false,
      }),
    ).toBe('section_break')
  })
})

describe('display reconnect backoff', () => {
  it('uses exponential backoff capped at 10s', () => {
    expect(computeReconnectDelay(0)).toBe(1000)
    expect(computeReconnectDelay(1)).toBe(2000)
    expect(computeReconnectDelay(2)).toBe(4000)
    expect(computeReconnectDelay(3)).toBe(8000)
    expect(computeReconnectDelay(4)).toBe(10_000)
    expect(computeReconnectDelay(8)).toBe(10_000)
  })
})
