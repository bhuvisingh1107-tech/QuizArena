import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ParticipantSessionProvider } from '@/contexts/ParticipantSessionContext'
import { getParticipantSession } from '@/lib/participant-session'
import { JoinRoomPage } from '@/pages/participant/JoinRoomPage'

const participantPost = vi.fn()

vi.mock('@/lib/participant-api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/participant-api')>(
    '@/lib/participant-api',
  )
  return {
    ...actual,
    participantPost: (...args: unknown[]) => participantPost(...args),
    participantGet: vi.fn(),
  }
})

function renderJoinRoom() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/join/ABC123']}>
        <ParticipantSessionProvider>
          <Routes>
            <Route path="/join/:roomCode" element={<JoinRoomPage />} />
            <Route path="/lobby" element={<div>Lobby ready</div>} />
            <Route path="/quiz" element={<div>Quiz ready</div>} />
            <Route path="/results" element={<div>Results ready</div>} />
          </Routes>
        </ParticipantSessionProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('JoinRoomPage session persistence', () => {
  beforeEach(() => {
    sessionStorage.clear()
    participantPost.mockReset()
  })

  it('stores participant session on successful join', async () => {
    const user = userEvent.setup()
    participantPost.mockImplementation(async (url: string) => {
      if (url === '/join') {
        return {
          sessionToken: 'tok-1',
          restored: false,
          participant: {
            id: 'p1',
            liveRoomId: 'r1',
            displayName: 'Alex',
            email: 'alex@example.com',
            state: 'InLobby',
            connectionStatus: 'connected',
            totalScore: 0,
            streak: 0,
            rank: null,
            totalCorrect: 0,
            totalIncorrect: 0,
            unansweredCount: 0,
            joinedAt: new Date().toISOString(),
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          },
          room: {
            id: 'r1',
            roomCode: 'ABC123',
            state: 'Lobby',
            lobbySubState: 'LobbyOpen',
            quizTitle: 'Science Night',
            codesExpired: false,
          },
        }
      }
      throw new Error(`Unexpected post ${url}`)
    })

    renderJoinRoom()

    await user.clear(screen.getByLabelText(/display name/i))
    await user.type(screen.getByLabelText(/display name/i), 'Alex')
    await user.type(screen.getByLabelText(/email/i), 'alex@example.com')
    await user.click(screen.getByRole('button', { name: /join room/i }))

    await waitFor(() => {
      expect(screen.getByText(/lobby ready/i)).toBeInTheDocument()
    })

    const session = getParticipantSession()
    expect(session).toMatchObject({
      sessionToken: 'tok-1',
      roomCode: 'ABC123',
      roomId: 'r1',
      displayName: 'Alex',
      email: 'alex@example.com',
      quizTitle: 'Science Night',
      participantId: 'p1',
    })
  })
})
