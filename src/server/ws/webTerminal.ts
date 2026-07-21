/**
 * Web Terminal — Web 部署模式下的终端 WebSocket 通道
 *
 * 浏览器直连服务端（无 Electron 宿主）时，通过 /ws/terminal/{sessionId}
 * 提供 PTY 终端能力。
 *
 * 协议（JSON 文本帧）：
 *   客户端 -> 服务端：{ type: 'spawn'|'input'|'resize'|'kill', ... }
 *   服务端 -> 客户端：{ type: 'ready'|'output'(base64)|'exit'|'error', ... }
 */

import type { ServerWebSocket } from 'bun'
import type { WebSocketData } from './handler.js'

type TerminalWebSocket = ServerWebSocket<WebSocketData>

interface TerminalProcess {
  kill: (code?: number) => void
  exited: Promise<number>
}

interface TerminalSession {
  proc: TerminalProcess
  write: (data: string) => void
  resize?: (cols: number, rows: number) => void
  shell: string
}

const sessions = new Map<string, TerminalSession>()

function pickShell(): string {
  if (process.platform === 'win32') return process.env.COMSPEC || 'cmd.exe'
  return process.env.SHELL || '/bin/bash'
}

function encodeOutput(data: string | Uint8Array): string {
  if (typeof data === 'string') return Buffer.from(data, 'utf-8').toString('base64')
  return Buffer.from(data).toString('base64')
}

function send(ws: TerminalWebSocket, payload: Record<string, unknown>) {
  try {
    ws.send(JSON.stringify(payload))
  } catch { /* 连接已关闭 */ }
}

async function pumpStream(ws: TerminalWebSocket, stream: ReadableStream<Uint8Array> | null) {
  if (!stream) return
  const reader = stream.getReader()
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      if (value) send(ws, { type: 'output', data: encodeOutput(value) })
    }
  } catch { /* 流中断 */ }
}

function spawnTerminal(ws: TerminalWebSocket, msg: { cols?: number; rows?: number; cwd?: string }) {
  const sessionId = ws.data.sessionId
  if (sessions.has(sessionId)) {
    send(ws, { type: 'error', message: 'Terminal session already spawned.' })
    return
  }
  const shell = pickShell()
  const cols = typeof msg.cols === 'number' && msg.cols > 0 ? msg.cols : 80
  const rows = typeof msg.rows === 'number' && msg.rows > 0 ? msg.rows : 24
  const cwd = typeof msg.cwd === 'string' && msg.cwd ? msg.cwd : process.cwd()

  try {
    // 优先使用 Bun 的 PTY（terminal）模式
    const proc = Bun.spawn([shell, '-l'], {
      cwd,
      env: { ...process.env, TERM: 'xterm-256color' },
      terminal: {
        cols,
        rows,
        data(_terminal: unknown, data: Uint8Array) {
          send(ws, { type: 'output', data: encodeOutput(data) })
        },
      },
    })
    const session: TerminalSession = {
      proc,
      shell,
      write: (data) => proc.terminal?.write(data),
      resize: (c, r) => proc.terminal?.resize(c, r),
    }
    sessions.set(sessionId, session)
    send(ws, { type: 'ready', shell })
    void proc.exited.then((code) => {
      sessions.delete(sessionId)
      send(ws, { type: 'exit', code })
    })
  } catch {
    // 回退：管道模式（无 PTY，交互能力受限）
    try {
      const proc = Bun.spawn([shell], {
        cwd,
        env: { ...process.env, TERM: 'dumb' },
        stdin: 'pipe',
        stdout: 'pipe',
        stderr: 'pipe',
      })
      sessions.set(sessionId, {
        proc,
        shell,
        write: (data) => {
          proc.stdin.write(data)
          proc.stdin.flush()
        },
      })
      void pumpStream(ws, proc.stdout)
      void pumpStream(ws, proc.stderr)
      send(ws, { type: 'ready', shell })
      void proc.exited.then((code) => {
        sessions.delete(sessionId)
        send(ws, { type: 'exit', code })
      })
    } catch (err) {
      send(ws, { type: 'error', message: err instanceof Error ? err.message : String(err) })
    }
  }
}

export const webTerminalHandler = {
  open(_ws: TerminalWebSocket) {
    // 等待客户端发送 spawn
  },

  message(ws: TerminalWebSocket, rawMessage: string | Buffer) {
    let msg: Record<string, unknown>
    try {
      msg = JSON.parse(typeof rawMessage === 'string' ? rawMessage : rawMessage.toString('utf-8'))
    } catch {
      send(ws, { type: 'error', message: 'Invalid message format.' })
      return
    }
    const session = sessions.get(ws.data.sessionId)
    switch (msg.type) {
      case 'spawn':
        spawnTerminal(ws, msg)
        return
      case 'input':
        if (session && typeof msg.data === 'string') session.write(msg.data)
        return
      case 'resize':
        if (session?.resize && typeof msg.cols === 'number' && typeof msg.rows === 'number') {
          session.resize(msg.cols, msg.rows)
        }
        return
      case 'kill':
        session?.proc.kill()
        sessions.delete(ws.data.sessionId)
        return
      default:
        send(ws, { type: 'error', message: `Unknown message type: ${String(msg.type)}` })
    }
  },

  close(ws: TerminalWebSocket) {
    const session = sessions.get(ws.data.sessionId)
    session?.proc.kill()
    sessions.delete(ws.data.sessionId)
  },
}
