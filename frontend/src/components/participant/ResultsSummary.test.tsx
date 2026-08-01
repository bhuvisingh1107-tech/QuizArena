import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ResultsSummary } from '@/components/participant/ResultsSummary'

describe('ResultsSummary accuracy', () => {
  it('renders computed accuracy and bonus stats', () => {
    render(
      <ResultsSummary
        displayName="Alex"
        rank={2}
        score={80}
        correct={3}
        incorrect={1}
        unanswered={0}
        timeBonus={12}
        streakBonus={8}
      />,
    )

    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
    expect(screen.getByText('80')).toBeInTheDocument()
    expect(screen.getByText('+12')).toBeInTheDocument()
    expect(screen.getByText('+8')).toBeInTheDocument()
  })
})
