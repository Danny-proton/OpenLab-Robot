import { api } from './client'

export type SyncScope = 'agentConfig' | 'skill' | 'sessionHistory' | 'memory'

export type SyncRecord = {
  id: string
  scope: SyncScope
  direction: 'upload' | 'download'
  at: string
  url: string
  detail?: string
}

export type SyncState = {
  enabled: boolean
  scopes: SyncScope[]
  history: SyncRecord[]
}

export const syncApi = {
  get() {
    return api.get<SyncState>('/api/sync')
  },

  setScopes(scopes: SyncScope[]) {
    return api.put<{ ok: true } & SyncState>('/api/sync/scopes', { scopes })
  },

  upload(scope: SyncScope, detail?: string) {
    return api.post<{ ok: true; record: SyncRecord }>('/api/sync/upload', { scope, detail })
  },

  download(scope: SyncScope) {
    return api.post<{ ok: true; record: SyncRecord }>('/api/sync/download', { scope })
  },
}
