import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

import { QuestionCard } from '@/components/participant/QuestionCard'
import type { ParticipantLiveQuestion } from '@/types/api'

vi.mock('@/lib/media-url', () => ({
  resolveLiveMediaUrl: ({
    mediaFileId,
    token,
  }: {
    mediaFileId?: string | null
    token: string
  }) =>
    mediaFileId
      ? `https://api.example.com/api/v1/media/${mediaFileId}/content?token=${token}`
      : null,
  preloadLiveMedia: () => {},
}))

function question(
  overrides: Partial<ParticipantLiveQuestion> & Pick<ParticipantLiveQuestion, 'id' | 'index'>,
): ParticipantLiveQuestion {
  return {
    promptText: `Prompt ${overrides.index}`,
    questionType: 'Image',
    state: 'Open',
    mediaFileId: 'shared-media',
    imageUrl: '/api/v1/media/shared-media/content',
    options: [],
    totalQuestions: 3,
    ...overrides,
  }
}

describe('QuestionCard shared media across questions', () => {
  beforeEach(() => {
    // Simulate a browser HTTP cache hit: decode is done before onLoad can attach.
    Object.defineProperty(HTMLImageElement.prototype, 'complete', {
      configurable: true,
      get: () => true,
    })
    Object.defineProperty(HTMLImageElement.prototype, 'naturalWidth', {
      configurable: true,
      get: () => 640,
    })
    Object.defineProperty(HTMLImageElement.prototype, 'naturalHeight', {
      configurable: true,
      get: () => 480,
    })
  })

  afterEach(() => {
    for (const key of ['complete', 'naturalWidth', 'naturalHeight'] as const) {
      // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
      delete (HTMLImageElement.prototype as unknown as Record<string, unknown>)[key]
    }
  })

  it('shows the image on a later question when the browser served it from cache', async () => {
    const first = question({ id: 'q1', index: 0, promptText: 'Q1' })
    const { rerender } = render(
      <QuestionCard question={first} sessionToken="tok" />,
    )

    await waitFor(() => {
      expect(screen.queryByTestId('participant-media-skeleton')).toBeNull()
    })
    expect(screen.getByTestId('participant-media-img')).toBeTruthy()

    // Q2 shares the same mediaFileId / imageUrl (apply-to-all). No load event —
    // only img.complete from cache must clear the skeleton.
    const second = question({ id: 'q2', index: 1, promptText: 'Q2' })
    rerender(<QuestionCard question={second} sessionToken="tok" />)

    await waitFor(() => {
      expect(screen.queryByTestId('participant-media-skeleton')).toBeNull()
    })
    expect(screen.getByText('Q2')).toBeTruthy()
    expect(screen.getByTestId('participant-media-img').getAttribute('src')).toContain(
      'shared-media',
    )
  })
})
