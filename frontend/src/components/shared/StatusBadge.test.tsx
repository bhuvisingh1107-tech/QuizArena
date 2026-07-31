import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatusBadge } from '@/components/shared/StatusBadge'

describe('StatusBadge', () => {
  it('renders quiz status labels', () => {
    render(<StatusBadge status="Ready" />)
    expect(screen.getByText('Ready')).toBeInTheDocument()
  })

  it('renders room state labels', () => {
    render(<StatusBadge state="Active" />)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })
})
