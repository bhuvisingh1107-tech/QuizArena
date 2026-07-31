import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ResultsSummary } from '@/components/participant/ResultsSummary'

describe('ResultsSummary accuracy', () => {
  it('renders computed accuracy from correct/incorrect counts', () => {
    render(
      <ResultsSummary
        displayName="Alex"
        rank={2}
        score={80}
        correct={3}
        incorrect={1}
        unanswered={0}
      />,
    )

    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
    expect(screen.getByText('80')).toBeInTheDocument()
  })
})
