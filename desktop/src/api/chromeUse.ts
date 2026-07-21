import { api } from './client'

export type ChromeUseStatus = {
  mcpInstalled: boolean
  chromePath?: string
  chromeVersion?: string
  chromeVersionOk: boolean
  remoteDebugging: boolean
  debugPort: number
  minChromeMajor: number
}

export type DebugTarget = {
  id: string
  title: string
  url: string
  type: string
  webSocketDebuggerUrl?: string
}

export const chromeUseApi = {
  status() {
    return api.get<ChromeUseStatus>('/api/chrome-use/status')
  },

  targets() {
    return api.get<{ targets: DebugTarget[] }>('/api/chrome-use/targets')
  },

  launch() {
    return api.post<{ ok: boolean; pid?: number }>('/api/chrome-use/launch')
  },
}
