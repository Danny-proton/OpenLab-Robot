import { api } from './client'

export type BrandInfo = {
  appName: string
  agentName: string
  chatPlaceholder?: string
  systemPromptOverride?: string
  brandFile: string
}

export type BrandUpdate = {
  appName?: string
  agentName?: string
  chatPlaceholder?: string
  systemPromptOverride?: string
}

export const brandApi = {
  get() {
    return api.get<BrandInfo>('/api/brand')
  },

  update(update: BrandUpdate) {
    return api.put<{ ok: true } & BrandInfo>('/api/brand', update)
  },
}
