import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import net from 'node:net'

function getTerminalWsPort(): number | null {
  const configDir = process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude')
  const portFile = path.join(configDir, 'terminal-ws.json')
  try {
    const data = JSON.parse(fs.readFileSync(portFile, 'utf8')) as { port?: number }
    return typeof data.port === 'number' ? data.port : null
  } catch {
    return null
  }
}

async function isTerminalPortListening(port: number): Promise<boolean> {
  return new Promise<boolean>((resolve) => {
    const sock = net.createConnection(port, '127.0.0.1', () => {
      sock.destroy()
      resolve(true)
    })
    sock.on('error', () => resolve(false))
    sock.setTimeout(1000)
    sock.on('timeout', () => { sock.destroy(); resolve(false) })
  })
}

export async function handleTerminalApi(req: Request, url: URL): Promise<Response> {
  const segments = url.pathname.split('/').filter(Boolean)
  const sub = segments[2]

  if (sub === 'ws-info' && req.method === 'GET') {
    const port = getTerminalWsPort()
    if (!port) {
      return Response.json(
        { error: 'Terminal websocket server is not available' },
        { status: 503 }
      )
    }

    // Build WebSocket URL using the same host the request came in on
    // Always use the public server port (3456) instead of the internal
    // terminal-server random port, so that browsers can reach it through
    // a single exposed port (no Nginx or extra Docker port mapping needed).
    const serverPort = process.env.SERVER_PORT || '3456'
    const forwardedHost = req.headers.get('X-Forwarded-Host')
    const forwardedProto = req.headers.get('X-Forwarded-Proto')
    const host = forwardedHost
      || req.headers.get('Host')
      || `127.0.0.1:${serverPort}`

    const proto = forwardedProto === 'https' ? 'wss' : 'ws'
    const wsHost = host.includes(':') ? host.split(':')[0] : host
    const wsUrl = `${proto}://${wsHost}:${serverPort}/ws/terminal`

    return Response.json({ url: wsUrl, port })
  }

  if (sub === 'status' && req.method === 'GET') {
    const port = getTerminalWsPort()
    if (!port) {
      return Response.json({ available: false })
    }
    const listening = await isTerminalPortListening(port)
    return Response.json({ available: listening, port })
  }

  return Response.json(
    { error: 'Not Found', message: `Unknown terminal endpoint: ${sub}` },
    { status: 404 }
  )
}
