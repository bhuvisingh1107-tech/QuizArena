import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { Button } from '@/components/ui/button'

describe('Button', () => {
  it('renders and handles clicks', async () => {
    const user = userEvent.setup()
    let clicked = false

    render(
      <Button
        onClick={() => {
          clicked = true
        }}
      >
        Save quiz
      </Button>,
    )

    const button = screen.getByRole('button', { name: /save quiz/i })
    expect(button).toBeInTheDocument()
    await user.click(button)
    expect(clicked).toBe(true)
  })
})
