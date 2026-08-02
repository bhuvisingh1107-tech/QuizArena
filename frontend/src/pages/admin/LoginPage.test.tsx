import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { LoginPage } from '@/pages/admin/LoginPage'

vi.mock('@/hooks/queries/useAuth', () => ({
  useAuth: () => ({
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    admin: null,
    isAuthenticated: false,
    isLoading: false,
    refreshAdmin: vi.fn(),
  }),
}))

describe('LoginPage validation', () => {
  it('shows validation errors when fields are empty', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: /login/i }))

    expect(await screen.findByText(/username or email is required/i)).toBeInTheDocument()
    expect(await screen.findByText(/password is required/i)).toBeInTheDocument()
  })
})
