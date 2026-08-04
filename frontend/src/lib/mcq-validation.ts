/** Strict MCQ option rules shared by builder, review, and tests. */

export const MCQ_EXACTLY_FOUR = 'MCQ must contain exactly 4 options.'
export const MCQ_ALL_FILLED = 'All options must be filled.'
export const MCQ_DUPLICATES = 'Duplicate options are not allowed.'
export const MCQ_ONE_CORRECT = 'Only one option can be marked correct.'
export const MCQ_SELECT_CORRECT = 'Please select the correct answer.'

export interface McqOptionLike {
  text: string
  isCorrect: boolean
}

export function isTrueFalseOptions(options: McqOptionLike[]): boolean {
  if (options.length !== 2) return false
  const texts = new Set(options.map((o) => o.text.trim().toLowerCase()))
  return texts.has('true') && texts.has('false') && texts.size === 2
}

/** Returns all MCQ validation messages (empty when valid). */
export function collectMcqOptionErrors(options: McqOptionLike[]): string[] {
  if (isTrueFalseOptions(options)) {
    const correct = options.filter((o) => o.isCorrect)
    if (correct.length === 0) return [MCQ_SELECT_CORRECT]
    if (correct.length > 1) return [MCQ_ONE_CORRECT]
    return []
  }

  const errors: string[] = []
  if (options.length !== 4) {
    errors.push(MCQ_EXACTLY_FOUR)
  }

  const texts = options.map((o) => o.text.trim())
  if (texts.some((t) => !t)) {
    errors.push(MCQ_ALL_FILLED)
  }

  const lowered = texts.filter(Boolean).map((t) => t.toLowerCase())
  if (lowered.length !== new Set(lowered).size) {
    errors.push(MCQ_DUPLICATES)
  }

  const correct = options.filter((o) => o.isCorrect)
  const correctFilled = correct.filter((o) => o.text.trim())
  if (correct.length === 0 || correctFilled.length === 0) {
    errors.push(MCQ_SELECT_CORRECT)
  } else if (correct.length > 1) {
    errors.push(MCQ_ONE_CORRECT)
  }

  return errors
}

export function firstMcqOptionError(options: McqOptionLike[]): string | null {
  return collectMcqOptionErrors(options)[0] ?? null
}

export function isMcqOptionsValid(options: McqOptionLike[]): boolean {
  return collectMcqOptionErrors(options).length === 0
}
