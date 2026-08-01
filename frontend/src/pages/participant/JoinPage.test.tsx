import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { ParticipantSessionProvider } from '@/contexts/ParticipantSessionContext'
import { JoinPage } from '@/pages/participant/JoinPage'

function renderJoinPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ParticipantSessionProvider>
          <JoinPage />
        </ParticipantSessionProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('JoinPage validation', () => {
  it('shows name and room code validation errors', async () => {
    const user = userEvent.setup()

    renderJoinPage()

    await user.click(screen.getByRole('button', { name: /join room/i }))

    expect(await screen.findByText(/display name is required/i)).toBeInTheDocument()

    await user.type(screen.getByLabelText(/room code/i), 'ab')
    await user.click(screen.getByRole('button', { name: /join room/i }))

    expect(await screen.findByText(/room code must be 6/i)).toBeInTheDocument()
  })

  it('does not show an email field', () => {
    renderJoinPage()

    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
  })
})
