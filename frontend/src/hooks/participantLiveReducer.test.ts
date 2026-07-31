import { describe, expect, it } from 'vitest'

import {
  computeAccuracyPercent,
  computeReconnectDelay,
  getParticipantRouteForRoomState,
  initialParticipantLiveState,
  participantLiveReducer,
} from '@/hooks/participantLiveReducer'

describe('participantLiveReducer', () => {
  it('handles question:started and resets submission', () => {
    const started = participantLiveReducer(initialParticipantLiveState, {
      type: 'EVENT',
      message: {
        type: 'question:started',
        timestamp: new Date().toISOString(),
        payload: {
          questionIndex: 0,
          totalQuestions: 5,
          section: { id: 's1', name: 'Warmup' },
          question: {
            id: 'q1',
            promptText: 'Capital of France?',
            state: 'Open',
            allowMultipleCorrect: false,
            options: [
              { id: 'a', text: 'Paris', sortOrder: 0 },
              { id: 'b', text: 'Lyon', sortOrder: 1 },
            ],
          },
        },
      },
    })

    expect(started.question?.id).toBe('q1')
    expect(started.question?.promptText).toBe('Capital of France?')
    expect(started.options).toHaveLength(2)
    expect(started.submissionStatus).toBe('idle')
    expect(started.selectedOptionIds).toEqual([])
  })

  it('handles leaderboard:updated without emails', () => {
    const withSelf = {
      ...initialParticipantLiveState,
      self: {
        id: 'p1',
        displayName: 'Alex',
        totalScore: 0,
        streak: 0,
      },
    }

    const next = participantLiveReducer(withSelf, {
      type: 'EVENT',
      message: {
        type: 'leaderboard:updated',
        timestamp: new Date().toISOString(),
        payload: {
          entries: [
            {
              rank: 1,
              participantId: 'p1',
              displayName: 'Alex',
              score: 40,
              streak: 2,
              email: 'secret@example.com',
            },
          ],
        },
      },
    })

    expect(next.leaderboard[0]).toMatchObject({
      rank: 1,
      participantId: 'p1',
      displayName: 'Alex',
      score: 40,
    })
    expect(next.leaderboard[0]).not.toHaveProperty('email')
    expect(next.yourRank).toBe(1)
    expect(next.yourScore).toBe(40)
  })

  it('marks answer accepted and ALREADY_SUBMITTED rejected', () => {
    const accepted = participantLiveReducer(
      { ...initialParticipantLiveState, submissionStatus: 'submitting' },
      {
        type: 'EVENT',
        message: {
          type: 'answer:accepted',
          timestamp: new Date().toISOString(),
          payload: { selectedOptionIds: ['a'] },
        },
      },
    )
    expect(accepted.submissionStatus).toBe('submitted')
    expect(accepted.selectedOptionIds).toEqual(['a'])

    const rejected = participantLiveReducer(
      { ...initialParticipantLiveState, submissionStatus: 'submitting' },
      {
        type: 'EVENT',
        message: {
          type: 'answer:rejected',
          timestamp: new Date().toISOString(),
          payload: { code: 'ALREADY_SUBMITTED', message: 'Already in' },
        },
      },
    )
    expect(rejected.submissionStatus).toBe('already_submitted')
  })

  it('blocks duplicate SUBMIT_START while submitted', () => {
    const state = {
      ...initialParticipantLiveState,
      submissionStatus: 'submitted' as const,
      selectedOptionIds: ['a'],
    }
    const next = participantLiveReducer(state, {
      type: 'SUBMIT_START',
      optionIds: ['b'],
    })
    expect(next).toBe(state)
  })
})

describe('reconnect backoff helpers', () => {
  it('uses exponential backoff capped at 10s', () => {
    expect(computeReconnectDelay(0)).toBe(1000)
    expect(computeReconnectDelay(1)).toBe(2000)
    expect(computeReconnectDelay(2)).toBe(4000)
    expect(computeReconnectDelay(3)).toBe(8000)
    expect(computeReconnectDelay(4)).toBe(10_000)
    expect(computeReconnectDelay(8)).toBe(10_000)
  })
})

describe('route hints', () => {
  it('maps room states to participant routes', () => {
    expect(getParticipantRouteForRoomState('Lobby')).toBe('/lobby')
    expect(getParticipantRouteForRoomState('Active')).toBe('/quiz')
    expect(getParticipantRouteForRoomState('Paused')).toBe('/quiz')
    expect(getParticipantRouteForRoomState('SectionBreak')).toBe('/quiz')
    expect(getParticipantRouteForRoomState('Completed')).toBe('/results')
  })
})

describe('accuracy helper', () => {
  it('computes rounded accuracy percent', () => {
    expect(computeAccuracyPercent(0, 0)).toBe(0)
    expect(computeAccuracyPercent(3, 1)).toBe(75)
    expect(computeAccuracyPercent(1, 2)).toBe(33)
  })
})
