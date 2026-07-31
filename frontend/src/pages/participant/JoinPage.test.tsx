import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { JoinPage } from '@/pages/participant/JoinPage'

describe('JoinPage validation', () => {
  it('shows room code validation errors', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <JoinPage />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText(/room code/i), 'ab')
    await user.click(screen.getByRole('button', { name: /continue/i }))

    expect(await screen.findByText(/room code must be 6/i)).toBeInTheDocument()
  })
})
