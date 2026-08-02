import type { LiveRoom, RoomState } from '@/types/api'

/** Later stages win when merging REST + WS room snapshots. */
const ROOM_STATE_RANK: Record<RoomState, number> = {
  Setup: 0,
  Lobby: 1,
  Active: 2,
  Paused: 2,
  SectionBreak: 2,
  Completed: 3,
  Closed: 4,
}

export function roomStateRank(state: RoomState | null | undefined): number {
  if (!state) return -1
  return ROOM_STATE_RANK[state] ?? -1
}

/**
 * Pick the freshest room snapshot so stale WS Setup never blocks REST Lobby,
 * and a newer Completed WS never loses to an older Active REST row.
 */
export function preferFreshestRoom(
  primary: LiveRoom | null | undefined,
  secondary: LiveRoom | null | undefined,
): LiveRoom | null {
  if (!primary) return secondary ?? null
  if (!secondary) return primary
  const primaryRank = roomStateRank(primary.state)
  const secondaryRank = roomStateRank(secondary.state)
  if (secondaryRank > primaryRank) {
    return { ...primary, ...secondary }
  }
  if (primaryRank > secondaryRank) {
    return { ...secondary, ...primary }
  }
  // Same lifecycle stage — prefer primary (usually live WS) over secondary REST.
  return { ...secondary, ...primary, state: primary.state }
}

export function canRest(
  state: RoomState,
  action: 'openLobby' | 'start' | 'pause' | 'resume' | 'end' | 'close' | 'skip' | 'toggle',
): boolean {
  switch (action) {
    case 'openLobby':
      return state === 'Setup'
    case 'toggle':
      return state === 'Lobby'
    case 'start':
      return state === 'Lobby'
    case 'pause':
      return state === 'Active'
    case 'resume':
      return state === 'Paused'
    case 'skip':
      return state === 'Active' || state === 'Paused' || state === 'SectionBreak'
    case 'end':
      return state === 'Active' || state === 'Paused' || state === 'SectionBreak'
    case 'close':
      return state === 'Completed' || state === 'Lobby'
    default:
      return false
  }
}
