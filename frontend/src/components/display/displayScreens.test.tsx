import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/media-url', () => ({
  mediaContentUrl: (mediaFileId: string) => `/media/${mediaFileId}/content`,
  resolveLiveMediaUrl: ({
    imageUrl,
    mediaFileId,
    token,
  }: {
    imageUrl?: string | null
    mediaFileId?: string | null
    token: string
  }) => {
    if (!token) return null
    if (imageUrl) return `${imageUrl}?token=${token}`
    if (mediaFileId) return `/media/${mediaFileId}/content?token=${token}`
    return null
  },
}))

import { AnswerProgressRing } from '@/components/display/AnswerProgressRing'
import { LeaderboardScreen } from '@/components/display/LeaderboardScreen'
import { PodiumScreen } from '@/components/display/PodiumScreen'
import { QuestionScreen } from '@/components/display/QuestionScreen'
import { RevealScreen } from '@/components/display/RevealScreen'
import { SectionBreakScreen } from '@/components/display/SectionBreakScreen'
import { TimeUpScreen } from '@/components/display/TimeUpScreen'
import { WaitingScreen } from '@/components/display/WaitingScreen'

describe('WaitingScreen', () => {
  it('shows quiz title, room code, QR, and join URL', () => {
    render(
      <WaitingScreen
        quizTitle="Trivia Night"
        roomCode="ABC123"
        participantCount={5}
        connectionStatus="connected"
      />,
    )

    expect(screen.getByText('Trivia Night')).toBeInTheDocument()
    expect(screen.getByTestId('display-room-code')).toHaveTextContent('ABC123')
    expect(screen.getByTestId('join-qr-code')).toBeInTheDocument()
    expect(screen.getByTestId('join-url')).toHaveTextContent('/join/ABC123')
    expect(screen.getByTestId('participant-count')).toHaveTextContent('5')
    expect(screen.getByText('Waiting for host')).toBeInTheDocument()
  })
})

describe('QuestionScreen', () => {
  it('does not show correct markers when question is open', () => {
    render(
      <QuestionScreen
        secretToken="display-token"
        submittedCount={3}
        participantCount={10}
        questionOpenedAt={Date.now() - 5000}
        question={{
          id: 'q1',
          index: 0,
          totalQuestions: 5,
          promptText: 'Capital of France?',
          sectionName: 'Warmup',
          state: 'Open',
          timeLimitSeconds: 30,
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
    expect(screen.getByTestId('question-progress-bar')).toBeInTheDocument()
    expect(screen.getByTestId('answer-progress-ring')).toBeInTheDocument()
    expect(screen.getByTestId('display-timer')).toBeInTheDocument()
  })

  it('renders question media when mediaFileId is present', () => {
    render(
      <QuestionScreen
        secretToken="display-token"
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

    expect(screen.getByTestId('display-media-image')).toBeInTheDocument()
  })

  it('prefers imageUrl from the websocket payload', () => {
    render(
      <QuestionScreen
        secretToken="display-token"
        question={{
          id: 'q1',
          index: 0,
          promptText: 'Look at the image',
          imageUrl: '/api/v1/media/media-99/content',
          mediaFileId: 'media-99',
          state: 'Open',
          options: [{ id: 'a', text: 'Yes', sortOrder: 0 }],
        }}
      />,
    )

    const img = screen.getByTestId('display-media-img')
    expect(img).toHaveAttribute(
      'src',
      '/api/v1/media/media-99/content?token=display-token',
    )
  })
})

describe('TimeUpScreen', () => {
  it('shows time up message', () => {
    render(<TimeUpScreen />)
    expect(screen.getByTestId('time-up-screen')).toBeInTheDocument()
    expect(screen.getByText("Time's Up!")).toBeInTheDocument()
    expect(screen.getByText(/Calculating scores/i)).toBeInTheDocument()
  })
})

describe('RevealScreen', () => {
  it('marks correct options and shows distribution bars', () => {
    render(
      <RevealScreen
        secretToken="display-token"
        optionDistribution={[
          {
            optionId: 'a',
            text: 'Paris',
            selectedCount: 6,
            percent: 75,
            isCorrect: true,
          },
          {
            optionId: 'b',
            text: 'Lyon',
            selectedCount: 2,
            percent: 25,
            isCorrect: false,
          },
        ]}
        explanation="Paris is the capital of France."
        accuracyPercent={75}
        answeredCount={8}
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
    expect(screen.getByTestId('reveal-bar-A')).toBeInTheDocument()
    expect(screen.getByTestId('reveal-explanation')).toHaveTextContent(
      'Paris is the capital of France.',
    )
    expect(screen.getByTestId('accuracy-badge')).toHaveTextContent('75%')
  })
})

describe('SectionBreakScreen', () => {
  it('shows section stats and top 3', () => {
    render(
      <SectionBreakScreen
        section={{ id: 's1', name: 'Round 1' }}
        top3={[
          { rank: 1, participantId: 'p1', displayName: 'Alex', score: 30 },
          { rank: 2, participantId: 'p2', displayName: 'Sam', score: 20 },
        ]}
        sectionStats={{
          questionCount: 5,
          participantCount: 12,
          averageAccuracy: 70,
        }}
        leaderboard={[
          { rank: 1, participantId: 'p1', displayName: 'Alex', score: 30 },
        ]}
      />,
    )

    expect(screen.getByText('Round 1')).toBeInTheDocument()
    expect(screen.getByTestId('section-stats')).toBeInTheDocument()
    expect(screen.getByTestId('section-top3')).toBeInTheDocument()
    expect(screen.getByTestId('section-top-1')).toHaveTextContent('Alex')
  })
})

describe('PodiumScreen', () => {
  it('shows top 3 podium entries and session highlights', () => {
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
        sessionHighlights={{
          averageScore: 55,
          winner: {
            participantId: 'p1',
            displayName: 'Alex',
            score: 100,
            rank: 1,
          },
          fastestAnswer: {
            participantId: 'p2',
            displayName: 'Sam',
            responseTimeMs: 900,
            questionId: 'q1',
            promptText: 'Fast Q',
          },
        }}
      />,
    )

    expect(screen.getByTestId('podium-top3')).toBeInTheDocument()
    expect(screen.getByTestId('podium-rank-1')).toHaveTextContent('Alex')
    expect(screen.getByTestId('podium-rank-2')).toHaveTextContent('Sam')
    expect(screen.getByTestId('podium-rank-3')).toHaveTextContent('Jo')
    expect(screen.getByText('Quiz completed')).toBeInTheDocument()
    expect(screen.getByTestId('quiz-winner')).toHaveTextContent('Alex')
    expect(screen.getByTestId('fastest-answer')).toHaveTextContent('Sam')
  })
})

describe('LeaderboardScreen', () => {
  it('renders ranks and scores with rank-change hints', () => {
    render(
      <LeaderboardScreen
        leaderboard={[
          { rank: 1, participantId: 'p2', displayName: 'Sam', score: 50, streak: 2 },
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
    expect(screen.getByTestId('leaderboard-row-1')).toHaveAttribute(
      'data-biggest-climber',
      'true',
    )
  })
})

describe('AnswerProgressRing', () => {
  it('shows submitted over total', () => {
    render(<AnswerProgressRing submitted={4} total={10} />)
    expect(screen.getByTestId('answer-progress-ring')).toHaveAttribute(
      'aria-label',
      '4 of 10 answered',
    )
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('/ 10')).toBeInTheDocument()
  })
})
