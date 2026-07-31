import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ParticipantSessionProvider, useParticipantSessionContext } from '@/contexts/ParticipantSessionContext'
import { setParticipantSession, getParticipantSession } from '@/lib/participant-session'

const participantPost = vi.fn()
const participantGet = vi.fn()

vi.mock('@/lib/participant-api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/participant-api')>(
    '@/lib/participant-api',
  )
  return {
    ...actual,
    participantPost: (...args: unknown[]) => participantPost(...args),
    participantGet: (...args: unknown[]) => participantGet(...args),
  }
})

function Probe({ onReady }: { onReady: (session: ReturnType<typeof getParticipantSession>) => void }) {
  const { session, isLoading } = useParticipantSessionContext()
  if (!isLoading) onReady(session)
  return <div>{isLoading ? 'loading' : session?.displayName ?? 'none'}</div>
}

describe('participant reconnect restore', () => {
  beforeEach(() => {
    sessionStorage.clear()
    participantPost.mockReset()
    participantGet.mockReset()
  })

  it('restores session via reconnect on mount when token exists', async () => {
    setParticipantSession({
      sessionToken: 'old-tok',
      roomCode: 'ROOM01',
      roomId: 'room-1',
      displayName: 'Old Name',
      email: 'old@example.com',
      quizTitle: 'Old Quiz',
      participantId: 'pid-1',
    })

    participantPost.mockResolvedValue({
      sessionToken: 'new-tok',
      restored: true,
      participant: {
        id: 'pid-1',
        liveRoomId: 'room-1',
        displayName: 'Restored',
        email: 'old@example.com',
        state: 'InLobby',
        connectionStatus: 'connected',
        totalScore: 12,
        streak: 1,
        rank: 2,
        totalCorrect: 1,
        totalIncorrect: 0,
        unansweredCount: 0,
        joinedAt: new Date().toISOString(),
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      },
      room: {
        id: 'room-1',
        roomCode: 'ROOM01',
        state: 'Lobby',
        lobbySubState: 'LobbyOpen',
        quizTitle: 'Restored Quiz',
        codesExpired: false,
      },
    })

    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })

    let seen: ReturnType<typeof getParticipantSession> = null
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ParticipantSessionProvider>
            <Probe onReady={(s) => { seen = s }} />
          </ParticipantSessionProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    await waitFor(() => {
      expect(seen?.displayName).toBe('Restored')
      expect(seen?.sessionToken).toBe('new-tok')
      expect(seen?.quizTitle).toBe('Restored Quiz')
    })

    expect(participantPost).toHaveBeenCalledWith('/participants/reconnect')
    expect(getParticipantSession()?.sessionToken).toBe('new-tok')
  })
})
