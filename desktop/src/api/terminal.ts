import { getDesktopHost } from '../lib/desktopHost'
import { getAuthToken, getBaseUrl } from './client'

export type TerminalSpawnResult = {
  session_id: number
  shell: string
  cwd: string
}

export type TerminalOutputPayload = {
  session_id: number
  data: string
}

export type TerminalExitPayload = {
  session_id: number
  code: number
  signal?: string | null
}

type Unlisten = () => void

function getTerminalHost() {
  const host = getDesktopHost()
  if (!host.capabilities.terminal) {
    throw new Error('Terminal is available in the desktop app runtime.')
  }
  return host.terminal
}

/**
 * Web 部署模式（浏览器直连服务端、无 Electron）下的终端实现：
 * 通过 /ws/terminal/{sessionId} WebSocket 与服务端 PTY 会话通信，
 * 输出/退出事件走本地事件总线，接口与桌面宿主保持一致。
 */
type WebSession = {
  localId: number
  ws: WebSocket
  cwd?: string
}

const webSessions = new Map<number, WebSession>()
let nextLocalId = 1_000_000
const outputHandlers = new Set<(p: TerminalOutputPayload) => void>()
const exitHandlers = new Set<(p: TerminalExitPayload) => void>()

function buildTerminalWsUrl(wsSessionId: string) {
  const url = new URL(getBaseUrl())
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  const basePath = url.pathname === '/' ? '' : url.pathname.replace(/\/$/, '')
  url.pathname = `${basePath}/ws/terminal/${encodeURIComponent(wsSessionId)}`
  const token = getAuthToken()
  if (token) url.searchParams.set('token', token)
  return url.toString()
}

function webSpawn(input: { cols: number; rows: number; cwd?: string }): Promise<TerminalSpawnResult> {
  return new Promise((resolve, reject) => {
    const wsSessionId =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `t-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    const ws = new WebSocket(buildTerminalWsUrl(wsSessionId))
    const localId = nextLocalId++
    let settled = false
    const timeout = setTimeout(() => {
      if (settled) return
      settled = true
      ws.close()
      reject(new Error('Terminal session timed out.'))
    }, 15_000)

    ws.onmessage = (event) => {
      let msg: { type?: string; shell?: string; data?: string; code?: number; message?: string }
      try {
        msg = JSON.parse(String(event.data))
      } catch {
        return
      }
      if (msg.type === 'ready') {
        clearTimeout(timeout)
        settled = true
        webSessions.set(localId, { localId, ws, cwd: input.cwd })
        resolve({ session_id: localId, shell: msg.shell || 'sh', cwd: input.cwd || '' })
        return
      }
      if (msg.type === 'output' && typeof msg.data === 'string') {
        try {
          const decoded = atob(msg.data)
          const bytes = Uint8Array.from(decoded, (c) => c.charCodeAt(0))
          const text = new TextDecoder().decode(bytes)
          outputHandlers.forEach((h) => h({ session_id: localId, data: text }))
        } catch { /* ignore malformed frame */ }
        return
      }
      if (msg.type === 'exit') {
        webSessions.delete(localId)
        exitHandlers.forEach((h) => h({ session_id: localId, code: msg.code ?? 0 }))
        return
      }
      if (msg.type === 'error' && !settled) {
        clearTimeout(timeout)
        settled = true
        reject(new Error(msg.message || 'Terminal error'))
      }
    }
    ws.onerror = () => {
      if (settled) return
      clearTimeout(timeout)
      settled = true
      reject(new Error('Terminal WebSocket connection failed.'))
    }
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'spawn', cols: input.cols, rows: input.rows, cwd: input.cwd }))
    }
  })
}

function webSend(localId: number, payload: Record<string, unknown>): Promise<void> {
  const session = webSessions.get(localId)
  if (!session || session.ws.readyState !== WebSocket.OPEN) {
    return Promise.reject(new Error('Terminal session is not connected.'))
  }
  session.ws.send(JSON.stringify(payload))
  return Promise.resolve()
}

const webTerminal = {
  spawn: webSpawn,
  write: (id: number, data: string) => webSend(id, { type: 'input', data }),
  resize: (id: number, cols: number, rows: number) => webSend(id, { type: 'resize', cols, rows }),
  kill: (id: number) => webSend(id, { type: 'kill' }),
}

export const terminalApi = {
  // Web 部署模式下通过服务端 WebSocket PTY 提供终端能力
  isAvailable: () => true,

  spawn(input: { cols: number; rows: number; cwd?: string }) {
    if (getDesktopHost().capabilities.terminal) return getTerminalHost().spawn(input)
    return webTerminal.spawn(input)
  },

  write(sessionId: number, data: string) {
    if (webSessions.has(sessionId)) return webTerminal.write(sessionId, data)
    return getTerminalHost().write(sessionId, data)
  },

  resize(sessionId: number, cols: number, rows: number) {
    if (webSessions.has(sessionId)) return webTerminal.resize(sessionId, cols, rows)
    return getTerminalHost().resize(sessionId, cols, rows)
  },

  kill(sessionId: number) {
    if (webSessions.has(sessionId)) return webTerminal.kill(sessionId)
    return getTerminalHost().kill(sessionId)
  },

  async onOutput(handler: (payload: TerminalOutputPayload) => void): Promise<Unlisten> {
    const unlistenNative = getDesktopHost().capabilities.terminal
      ? await getTerminalHost().onOutput(handler)
      : () => {}
    outputHandlers.add(handler)
    return () => {
      unlistenNative()
      outputHandlers.delete(handler)
    }
  },

  async onExit(handler: (payload: TerminalExitPayload) => void): Promise<Unlisten> {
    const unlistenNative = getDesktopHost().capabilities.terminal
      ? await getTerminalHost().onExit(handler)
      : () => {}
    exitHandlers.add(handler)
    return () => {
      unlistenNative()
      exitHandlers.delete(handler)
    }
  },

  getBashPath(): Promise<string | null> {
    if (getDesktopHost().capabilities.terminal) return getTerminalHost().getBashPath()
    return Promise.resolve(null)
  },

  setBashPath(path: string | null): Promise<void> {
    if (getDesktopHost().capabilities.terminal) return getTerminalHost().setBashPath(path)
    return Promise.resolve()
  },
}
