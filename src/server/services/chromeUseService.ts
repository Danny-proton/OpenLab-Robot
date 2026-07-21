/**
 * Chrome Use Service — Openlab Robot Chrome use 环境检查与调试实例管理
 *
 * 检查项：chrome-devtools MCP 安装、Chrome 版本 >= 144、
 * 远程调试端口 9222 可访问（chrome://inspect/#remote-debugging）。
 */

import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'
import { execFileSync, spawn, type ChildProcess } from 'child_process'

export const CHROME_DEBUG_PORT = 9222
export const MIN_CHROME_MAJOR = 144

export interface DebugTarget {
  id: string
  title: string
  url: string
  type: string
  webSocketDebuggerUrl?: string
}

export interface ChromeUseStatus {
  mcpInstalled: boolean
  chromePath?: string
  chromeVersion?: string
  chromeVersionOk: boolean
  remoteDebugging: boolean
  debugPort: number
  minChromeMajor: number
}

const CHROME_CANDIDATES: Record<string, string[]> = {
  darwin: [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  ],
  linux: ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'microsoft-edge'],
  win32: [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  ],
}

function which(cmd: string): string | null {
  try {
    const out = execFileSync(process.platform === 'win32' ? 'where' : 'which', [cmd], {
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'ignore'],
    })
    const first = out.split(/\r?\n/)[0]?.trim()
    return first || null
  } catch {
    return null
  }
}

export function findChrome(): string | null {
  const candidates = CHROME_CANDIDATES[process.platform] ?? CHROME_CANDIDATES.linux
  for (const candidate of candidates) {
    if (candidate.includes(path.sep) || candidate.includes('\\')) {
      if (fs.existsSync(candidate)) return candidate
    } else {
      const found = which(candidate)
      if (found) return found
    }
  }
  return null
}

export function getChromeVersion(chromePath: string): string | null {
  try {
    const out = execFileSync(chromePath, ['--version'], {
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'ignore'],
      timeout: 5000,
    }).trim()
    const match = out.match(/(\d+(?:\.\d+){1,3})/)
    return match ? match[1] : out || null
  } catch {
    return null
  }
}

export function isChromeVersionOk(version: string | null): boolean {
  if (!version) return false
  const major = Number.parseInt(version.split('.')[0] ?? '', 10)
  return Number.isFinite(major) && major >= MIN_CHROME_MAJOR
}

export function checkMcpInstalled(): boolean {
  try {
    const raw = fs.readFileSync(path.join(os.homedir(), '.claude.json'), 'utf-8')
    if (raw.includes('chrome-devtools')) return true
  } catch { /* 无配置文件 */ }
  try {
    execFileSync('npx', ['-y', 'chrome-devtools-mcp@latest', '--help'], {
      stdio: ['ignore', 'ignore', 'ignore'],
      timeout: 20_000,
    })
    return true
  } catch {
    return false
  }
}

export async function checkRemoteDebugging(port = CHROME_DEBUG_PORT): Promise<boolean> {
  try {
    const res = await fetch(`http://127.0.0.1:${port}/json/version`, {
      signal: AbortSignal.timeout(2000),
    })
    return res.ok
  } catch {
    return false
  }
}

let debugChromeProcess: ChildProcess | null = null

export function launchDebugChrome(): { ok: boolean; pid?: number; error?: string } {
  if (debugChromeProcess && debugChromeProcess.exitCode === null) {
    return { ok: true, pid: debugChromeProcess.pid }
  }
  const chromePath = findChrome()
  if (!chromePath) return { ok: false, error: 'Chrome not found' }
  try {
    debugChromeProcess = spawn(
      chromePath,
      [
        `--remote-debugging-port=${CHROME_DEBUG_PORT}`,
        '--remote-allow-origins=*',
        '--no-first-run',
        '--no-default-browser-check',
        `--user-data-dir=${path.join(os.tmpdir(), 'openlab-chrome-debug-profile')}`,
      ],
      { detached: true, stdio: 'ignore' },
    )
    debugChromeProcess.unref()
    return { ok: true, pid: debugChromeProcess.pid }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

export async function listDebugTargets(port = CHROME_DEBUG_PORT): Promise<DebugTarget[]> {
  try {
    const res = await fetch(`http://127.0.0.1:${port}/json/list`, {
      signal: AbortSignal.timeout(3000),
    })
    if (!res.ok) return []
    const list = (await res.json()) as Array<Record<string, unknown>>
    return list
      .filter((t) => typeof t.id === 'string')
      .map((t) => ({
        id: String(t.id),
        title: typeof t.title === 'string' ? t.title : '',
        url: typeof t.url === 'string' ? t.url : '',
        type: typeof t.type === 'string' ? t.type : 'page',
        webSocketDebuggerUrl:
          typeof t.webSocketDebuggerUrl === 'string' ? t.webSocketDebuggerUrl : undefined,
      }))
  } catch {
    return []
  }
}

export async function getChromeUseStatus(): Promise<ChromeUseStatus> {
  const chromePath = findChrome() ?? undefined
  const chromeVersion = chromePath ? getChromeVersion(chromePath) ?? undefined : undefined
  return {
    mcpInstalled: checkMcpInstalled(),
    chromePath,
    chromeVersion,
    chromeVersionOk: isChromeVersionOk(chromeVersion ?? null),
    remoteDebugging: await checkRemoteDebugging(),
    debugPort: CHROME_DEBUG_PORT,
    minChromeMajor: MIN_CHROME_MAJOR,
  }
}
