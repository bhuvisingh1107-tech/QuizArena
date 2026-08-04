import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { QuestionsStep } from '@/components/quiz-builder/QuestionsStep'
import type { Section } from '@/types/api'

vi.mock('@/lib/toast-helpers', () => ({
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}))

vi.mock('@/hooks/queries/useQuestions', () => ({
  useQuestions: () => ({
    data: { items: [], total: 0 },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useQuestionMutations: () => ({
    deleteQuestion: { mutateAsync: vi.fn() },
  }),
}))

vi.mock('@/hooks/queries/useOptions', () => ({
  useOptions: () => ({
    data: { items: [], total: 0 },
    isLoading: false,
  }),
}))

function renderStep(props: Partial<ComponentProps<typeof QuestionsStep>> = {}) {
  const sections: Section[] = [
    {
      id: 's1',
      quizId: 'q1',
      name: 'Section 1',
      sortOrder: 0,
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    },
    {
      id: 's2',
      quizId: 'q1',
      name: 'Section 2',
      sortOrder: 1,
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    },
  ]
  const onDeleteSection = vi.fn(async () => undefined)
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <QuestionsStep
        quizId="q1"
        sections={sections}
        section={sections[0]}
        selectedSectionId="s1"
        onSelectSection={vi.fn()}
        onAddSection={vi.fn()}
        onRenameSection={vi.fn()}
        onDeleteSection={onDeleteSection}
        sectionsLoading={false}
        sectionsError={false}
        onRetrySections={vi.fn()}
        onContinue={vi.fn()}
        {...props}
      />
    </QueryClientProvider>,
  )
  return { onDeleteSection, sections }
}

describe('QuestionsStep delete section', () => {
  it('asks for confirmation before deleting a section', async () => {
    const user = userEvent.setup()
    const { onDeleteSection } = renderStep()

    await user.click(screen.getByRole('button', { name: 'Delete Section' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Delete section?')).toBeInTheDocument()
    expect(onDeleteSection).not.toHaveBeenCalled()

    await user.click(within(dialog).getByRole('button', { name: 'Delete Section' }))
    expect(onDeleteSection).toHaveBeenCalled()
  })

  it('cancels delete confirmation without calling the API', async () => {
    const user = userEvent.setup()
    const { onDeleteSection } = renderStep()

    await user.click(screen.getByRole('button', { name: 'Delete Section' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(onDeleteSection).not.toHaveBeenCalled()
  })

  it('prevents deleting the last remaining section', async () => {
    const user = userEvent.setup()
    const only: Section = {
      id: 's1',
      quizId: 'q1',
      name: 'Only section',
      sortOrder: 0,
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    }
    const onDeleteSection = vi.fn(async () => undefined)
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    render(
      <QueryClientProvider client={client}>
        <QuestionsStep
          quizId="q1"
          sections={[only]}
          section={only}
          selectedSectionId="s1"
          onSelectSection={vi.fn()}
          onAddSection={vi.fn()}
          onRenameSection={vi.fn()}
          onDeleteSection={onDeleteSection}
          sectionsLoading={false}
          sectionsError={false}
          onRetrySections={vi.fn()}
          onContinue={vi.fn()}
        />
      </QueryClientProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Delete Section' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(onDeleteSection).not.toHaveBeenCalled()
  })
})
