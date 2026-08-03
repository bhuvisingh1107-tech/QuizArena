import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LiveLeaderboardPanel } from '@/components/display/LiveLeaderboardPanel'

describe('LiveLeaderboardPanel', () => {
  it('renders rank name score time bonus streak', () => {
    render(
      <LiveLeaderboardPanel
        leaderboard={[
          {
            rank: 1,
            participantId: 'p1',
            displayName: 'Alex',
            score: 42,
            streak: 3,
            timeBonus: 8,
          },
          {
            rank: 2,
            participantId: 'p2',
            displayName: 'Sam',
            score: 30,
            streak: 1,
            lastTimeBonus: 2,
          },
        ]}
        previousRanks={{ p1: 2, p2: 1 }}
      />,
    )

    expect(screen.getByTestId('live-leaderboard-panel')).toBeInTheDocument()
    expect(screen.getByText('Alex')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('+8')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('↑1')).toBeInTheDocument()
  })
})
