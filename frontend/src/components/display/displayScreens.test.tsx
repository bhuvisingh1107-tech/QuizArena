import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LeaderboardScreen } from '@/components/display/LeaderboardScreen'
import { PodiumScreen } from '@/components/display/PodiumScreen'
import { QuestionScreen } from '@/components/display/QuestionScreen'
import { RevealScreen } from '@/components/display/RevealScreen'
import { WaitingScreen } from '@/components/display/WaitingScreen'

describe('WaitingScreen', () => {
  it('shows quiz title and room code', () => {
    render(
      <WaitingScreen
        quizTitle="Trivia Night"
        roomCode="ABC123"
        connectionStatus="connected"
      />,
    )

    expect(screen.getByText('Trivia Night')).toBeInTheDocument()
    expect(screen.getByTestId('display-room-code')).toHaveTextContent('ABC123')
    expect(screen.getByText('Waiting for host')).toBeInTheDocument()
  })
})

describe('QuestionScreen', () => {
  it('does not show correct markers when question is open', () => {
    render(
      <QuestionScreen
        question={{
          id: 'q1',
          index: 0,
          totalQuestions: 5,
          promptText: 'Capital of France?',
          sectionName: 'Warmup',
          state: 'Open',
          options: [
            { id: 'a', text: 'Paris', sortOrder: 0, isCorrect: true },
            { id: 'b', text: 'Lyon', sortOrder: 1, isCorrect: false },
          ],
        }}
      />,
    )

    expect(screen.getByText('Capital of France?')).toBeInTheDocument()
    expect(screen.getByText('Paris')).toBeInTheDocument()
    expect(screen.queryByText(/correct/i)).not.toBeInTheDocument()
    expect(screen.queryByTestId('correct-marker')).not.toBeInTheDocument()
  })

  it('shows media placeholder when mediaFileId is present', () => {
    render(
      <QuestionScreen
        question={{
          id: 'q1',
          index: 0,
          promptText: 'Look at the image',
          mediaFileId: 'media-1',
          state: 'Open',
          options: [{ id: 'a', text: 'Yes', sortOrder: 0 }],
        }}
      />,
    )

    expect(screen.getByTestId('media-placeholder')).toBeInTheDocument()
  })
})

describe('RevealScreen', () => {
  it('marks correct options', () => {
    render(
      <RevealScreen
        question={{
          id: 'q1',
          index: 0,
          promptText: 'Capital of France?',
          state: 'Revealed',
          options: [
            { id: 'a', text: 'Paris', sortOrder: 0, isCorrect: true },
            { id: 'b', text: 'Lyon', sortOrder: 1, isCorrect: false },
          ],
        }}
      />,
    )

    expect(screen.getByTestId('reveal-option-A')).toHaveAttribute('data-correct', 'true')
    expect(screen.getByTestId('reveal-option-B')).toHaveAttribute('data-correct', 'false')
    expect(screen.getByTestId('correct-marker')).toHaveTextContent('Correct')
  })
})

describe('PodiumScreen', () => {
  it('shows top 3 podium entries', () => {
    render(
      <PodiumScreen
        quizTitle="Finals"
        podium={{
          entries: [
            { rank: 1, participantId: 'p1', displayName: 'Alex', score: 100 },
            { rank: 2, participantId: 'p2', displayName: 'Sam', score: 80 },
            { rank: 3, participantId: 'p3', displayName: 'Jo', score: 60 },
          ],
        }}
      />,
    )

    expect(screen.getByTestId('podium-top3')).toBeInTheDocument()
    expect(screen.getByTestId('podium-rank-1')).toHaveTextContent('Alex')
    expect(screen.getByTestId('podium-rank-2')).toHaveTextContent('Sam')
    expect(screen.getByTestId('podium-rank-3')).toHaveTextContent('Jo')
    expect(screen.getByText('Quiz completed')).toBeInTheDocument()
  })
})

describe('LeaderboardScreen', () => {
  it('renders ranks and scores with rank-change hints', () => {
    render(
      <LeaderboardScreen
        leaderboard={[
          { rank: 1, participantId: 'p2', displayName: 'Sam', score: 50 },
          { rank: 2, participantId: 'p1', displayName: 'Alex', score: 40 },
        ]}
        previousRanks={{ p1: 1, p2: 2 }}
      />,
    )

    expect(screen.getByTestId('leaderboard-row-1')).toHaveTextContent('Sam')
    expect(screen.getByTestId('leaderboard-row-1')).toHaveTextContent('50')
    expect(screen.getByTestId('leaderboard-row-2')).toHaveTextContent('Alex')
    expect(screen.getByTestId('leaderboard-row-1')).toHaveAttribute(
      'data-rank-delta',
      '1',
    )
  })
})
