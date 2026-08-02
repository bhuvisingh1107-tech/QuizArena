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

  it('handles score:personal and participant:count', () => {
    const withSelf = {
      ...initialParticipantLiveState,
      self: {
        id: 'p1',
        displayName: 'Alex',
        totalScore: 10,
        streak: 1,
      },
      cumulativeTimeBonus: 5,
      cumulativeStreakBonus: 2,
    }

    const scored = participantLiveReducer(withSelf, {
      type: 'EVENT',
      message: {
        type: 'score:personal',
        timestamp: new Date().toISOString(),
        payload: {
          questionId: 'q1',
          questionIndex: 0,
          isCorrect: true,
          isUnanswered: false,
          basePoints: 10,
          timeBonus: 3,
          streakBonus: 2,
          pointsEarned: 15,
          totalScore: 25,
          streak: 2,
        },
      },
    })

    expect(scored.lastFeedback?.pointsEarned).toBe(15)
    expect(scored.yourScore).toBe(25)
    expect(scored.cumulativeTimeBonus).toBe(8)
    expect(scored.cumulativeStreakBonus).toBe(4)

    const counted = participantLiveReducer(initialParticipantLiveState, {
      type: 'EVENT',
      message: {
        type: 'participant:count',
        timestamp: new Date().toISOString(),
        payload: { participantCount: 12 },
      },
    })
    expect(counted.participantCount).toBe(12)
  })

  it('tracks previous ranks on leaderboard:updated', () => {
    const prior = {
      ...initialParticipantLiveState,
      self: {
        id: 'p1',
        displayName: 'Alex',
        totalScore: 20,
        streak: 1,
      },
      leaderboard: [
        {
          rank: 2,
          participantId: 'p1',
          displayName: 'Alex',
          score: 20,
          streak: 1,
        },
      ],
      question: {
        id: 'q1',
        index: 0,
        state: 'Scored' as const,
        options: [],
      },
      lastFeedback: {
        questionId: 'q1',
        questionIndex: 0,
        isCorrect: true,
        isUnanswered: false,
        basePoints: 10,
        timeBonus: 0,
        streakBonus: 0,
        pointsEarned: 10,
        totalScore: 20,
        streak: 1,
      },
    }

    const next = participantLiveReducer(prior, {
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
              score: 30,
              streak: 2,
            },
          ],
        },
      },
    })

    expect(next.previousLeaderboardRanks.p1).toBe(2)
    expect(next.yourRank).toBe(1)
    expect(next.showLeaderboardInterstitial).toBe(true)
  })

  it('resync mid-reveal reads nested question.state for correctness', () => {
    const next = participantLiveReducer(initialParticipantLiveState, {
      type: 'EVENT',
      message: {
        type: 'resync',
        timestamp: new Date().toISOString(),
        payload: {
          room: { id: 'r1', roomCode: 'ABC123', state: 'Active', quizTitle: 'Quiz' },
          question: {
            questionIndex: 0,
            question: {
              id: 'q1',
              state: 'Revealed',
              promptText: 'Capital?',
              explanation: 'Paris is the capital',
              options: [
                { id: 'a', text: 'Paris', sortOrder: 0, isCorrect: true },
                { id: 'b', text: 'Lyon', sortOrder: 1, isCorrect: false },
              ],
            },
          },
        },
      },
    })

    expect(next.question?.state).toBe('Revealed')
    expect(next.question?.explanation).toBe('Paris is the capital')
    expect(next.options.find((o) => o.id === 'a')?.isCorrect).toBe(true)
  })

  it('forces Completed and clears waiting UI on quiz:completed', () => {
    const midQuiz = participantLiveReducer(initialParticipantLiveState, {
      type: 'EVENT',
      message: {
        type: 'question:started',
        timestamp: new Date().toISOString(),
        payload: {
          questionIndex: 0,
          question: {
            id: 'q1',
            promptText: 'Q?',
            state: 'Scored',
            options: [{ id: 'a', text: 'A', sortOrder: 0 }],
          },
        },
      },
    })
    const withSelf = {
      ...midQuiz,
      self: { id: 'p1', displayName: 'Alex', totalScore: 10, streak: 1 },
      showLeaderboardInterstitial: true,
    }

    const completed = participantLiveReducer(withSelf, {
      type: 'EVENT',
      message: {
        type: 'quiz:completed',
        timestamp: new Date().toISOString(),
        payload: {
          state: 'Completed',
          podium: {
            entries: [
              { rank: 1, participantId: 'p1', displayName: 'Alex', score: 40 },
            ],
          },
          leaderboard: [
            { rank: 1, participantId: 'p1', displayName: 'Alex', score: 40, streak: 2 },
          ],
        },
      },
    })

    expect(completed.room?.state).toBe('Completed')
    expect(completed.resultsReady).toBe(true)
    expect(completed.showLeaderboardInterstitial).toBe(false)
    expect(completed.question).toBeNull()
    expect(completed.podium?.entries).toHaveLength(1)
    expect(completed.leaderboard[0]?.score).toBe(40)
    expect(completed.yourRank).toBe(1)
  })

  it('does not reopen interstitial after Completed on leaderboard:updated', () => {
    const completed = {
      ...initialParticipantLiveState,
      resultsReady: true,
      room: {
        id: 'r1',
        roomCode: 'ABC',
        state: 'Completed' as const,
        quizTitle: 'Quiz',
      },
      question: {
        id: 'q1',
        index: 0,
        promptText: 'Q?',
        state: 'Scored' as const,
        options: [],
        timeLimitSeconds: null,
        timerEndsAt: null,
        sectionId: null,
        sectionName: null,
        totalQuestions: 1,
      },
      self: { id: 'p1', displayName: 'Alex', totalScore: 10, streak: 1 },
    }

    const next = participantLiveReducer(completed, {
      type: 'EVENT',
      message: {
        type: 'leaderboard:updated',
        timestamp: new Date().toISOString(),
        payload: {
          entries: [
            { rank: 1, participantId: 'p1', displayName: 'Alex', score: 40, streak: 2 },
          ],
        },
      },
    })

    expect(next.showLeaderboardInterstitial).toBe(false)
    expect(next.leaderboard).toHaveLength(1)
  })

  it('reads timer.endsAt from resync', () => {
    const endsAt = new Date(Date.now() + 20_000).toISOString()
    const next = participantLiveReducer(initialParticipantLiveState, {
      type: 'EVENT',
      message: {
        type: 'resync',
        timestamp: new Date().toISOString(),
        payload: {
          room: { id: 'r1', roomCode: 'ABC', state: 'Active', quizTitle: 'Quiz' },
          participant: { id: 'p1', displayName: 'Alex', totalScore: 0, streak: 0 },
          question: {
            questionIndex: 0,
            question: {
              id: 'q1',
              promptText: 'Q?',
              state: 'Open',
              timeLimitSeconds: 30,
              options: [{ id: 'a', text: 'A', sortOrder: 0 }],
            },
          },
          timer: { endsAt },
        },
      },
    })

    expect(next.question?.timerEndsAt).toBe(endsAt)
    expect(next.self?.id).toBe('p1')
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
