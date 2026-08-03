/** Centralized WebSocket lifecycle logging (dev + explicit flag). */

const ENABLED =
  import.meta.env.DEV ||
  String(import.meta.env.VITE_WS_DEBUG ?? '').toLowerCase() === 'true'

export type WsDebugPhase =
  | 'create'
  | 'connect'
  | 'acquire'
  | 'reuse'
  | 'open'
  | 'message'
  | 'error'
  | 'close'
  | 'reconnect'
  | 'cleanup'
  | 'release'
  | 'dispose'
  | 'send'
  | 'auth'
  | 'skip'

export function wsDebug(
  role: string,
  phase: WsDebugPhase,
  details: Record<string, unknown> = {},
): void {
  if (!ENABLED) return
  // eslint-disable-next-line no-console -- intentional WS lifecycle diagnostics
  console.debug(`[ws:${role}] ${phase}`, {
    t: new Date().toISOString(),
    ...details,
  })
}
