import { describe, expect, it } from 'vitest'

import {
  MCQ_ALL_FILLED,
  MCQ_DUPLICATES,
  MCQ_EXACTLY_FOUR,
  MCQ_ONE_CORRECT,
  MCQ_SELECT_CORRECT,
  collectMcqOptionErrors,
  firstMcqOptionError,
  isMcqOptionsValid,
} from '@/lib/mcq-validation'

describe('MCQ validation', () => {
  it('accepts a valid 4-option MCQ', () => {
    const options = [
      { text: 'Paris', isCorrect: true },
      { text: 'London', isCorrect: false },
      { text: 'Berlin', isCorrect: false },
      { text: 'Madrid', isCorrect: false },
    ]
    expect(isMcqOptionsValid(options)).toBe(true)
    expect(firstMcqOptionError(options)).toBeNull()
  })

  it('rejects 3 options', () => {
    expect(
      collectMcqOptionErrors([
        { text: 'A', isCorrect: true },
        { text: 'B', isCorrect: false },
        { text: 'C', isCorrect: false },
      ]),
    ).toContain(MCQ_EXACTLY_FOUR)
  })

  it('rejects 5 options', () => {
    expect(
      collectMcqOptionErrors([
        { text: 'A', isCorrect: true },
        { text: 'B', isCorrect: false },
        { text: 'C', isCorrect: false },
        { text: 'D', isCorrect: false },
        { text: 'E', isCorrect: false },
      ]),
    ).toContain(MCQ_EXACTLY_FOUR)
  })

  it('rejects blank options', () => {
    expect(
      collectMcqOptionErrors([
        { text: 'A', isCorrect: true },
        { text: '  ', isCorrect: false },
        { text: 'C', isCorrect: false },
        { text: 'D', isCorrect: false },
      ]),
    ).toContain(MCQ_ALL_FILLED)
  })

  it('rejects duplicate options', () => {
    expect(
      collectMcqOptionErrors([
        { text: 'Paris', isCorrect: true },
        { text: 'paris', isCorrect: false },
        { text: 'Berlin', isCorrect: false },
        { text: 'Madrid', isCorrect: false },
      ]),
    ).toContain(MCQ_DUPLICATES)
  })

  it('rejects no correct answer', () => {
    expect(
      collectMcqOptionErrors([
        { text: 'A', isCorrect: false },
        { text: 'B', isCorrect: false },
        { text: 'C', isCorrect: false },
        { text: 'D', isCorrect: false },
      ]),
    ).toContain(MCQ_SELECT_CORRECT)
  })

  it('rejects multiple correct answers', () => {
    expect(
      collectMcqOptionErrors([
        { text: 'A', isCorrect: true },
        { text: 'B', isCorrect: true },
        { text: 'C', isCorrect: false },
        { text: 'D', isCorrect: false },
      ]),
    ).toContain(MCQ_ONE_CORRECT)
  })

  it('accepts true/false', () => {
    expect(
      isMcqOptionsValid([
        { text: 'True', isCorrect: true },
        { text: 'False', isCorrect: false },
      ]),
    ).toBe(true)
  })
})
