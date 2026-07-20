import { api } from './client'

export type WorkspaceInfo = {
  defaultWorkspaceDir?: string
  buildDefaultDir?: string
  effectiveDefaultDir: string
  appFile: string
}

export const workspaceApi = {
  get() {
    return api.get<WorkspaceInfo>('/api/workspace')
  },

  update(defaultWorkspaceDir: string) {
    return api.put<{ ok: true } & WorkspaceInfo>('/api/workspace', { defaultWorkspaceDir })
  },
}
